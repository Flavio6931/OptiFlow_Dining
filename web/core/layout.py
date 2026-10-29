"""Módulo de carga, lectura y persistencia de la configuración espacial del salón (Req 6)."""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction

LAYOUT_PATH = Path(__file__).resolve().parents[2] / 'config' / 'salon.json'


def get_layout() -> Dict[str, Any]:
    """Lee y deserializa el esquema JSON topológico del restaurante."""
    with LAYOUT_PATH.open(encoding='utf-8') as f:
        return json.load(f)


def save_layout(data: Dict[str, Any]) -> None:
    """Serializa y guarda la configuración espacial del salón de forma atómica (ECC)."""
    dir_path = LAYOUT_PATH.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=dir_path, delete=False, encoding='utf-8') as tf:
        temp_name = tf.name
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
    os.replace(temp_name, LAYOUT_PATH)


def _parse_node(node: str) -> Tuple[int, int]:
    """Parsea y valida una coordenada 'X,Y' retornando tupla de enteros."""
    try:
        parts = [int(p.strip()) for p in node.split(',')]
        if len(parts) != 2 or parts[0] < 0 or parts[1] < 0:
            raise ValueError()
        return parts[0], parts[1]
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Coordenadas de cuadrícula inválidas. Debe tener formato 'X,Y' con números positivos (ej. '1,3').")


def _check_collision(data: Dict[str, Any], node: str, exclude_table_id: Optional[str] = None) -> None:
    """Verifica colisiones con mesas existentes, cocina o accesos en el plano (CAD)."""
    x, y = _parse_node(node)
    node_str = f"{x},{y}"

    for o in data.get('origins', []):
        if o.get('node', '').strip() == node_str:
            name = o.get('label') or o.get('id', 'origen')
            raise ValueError(f"La posición ({x}, {y}) ya está ocupada por '{name}'.")

    for t in data.get('tables', []):
        if exclude_table_id and t.get('id') == exclude_table_id:
            continue
        if t.get('node', '').strip() == node_str:
            name = t.get('label') or t.get('id', 'otra mesa')
            raise ValueError(f"La posición ({x}, {y}) ya está ocupada por la mesa '{name}'.")


def suggest_zone_coordinates(zone: str, layout_data: Optional[Dict[str, Any]] = None) -> str:
    """Calcula y sugiere la primera posición disponible en cuadrícula para una zona dada."""
    data = layout_data or get_layout()
    zone_upper = zone.upper().strip()

    # Determinar columnas asociadas a la zona en el layout
    cols: List[int] = []
    for z in data.get('zones', []):
        if z.get('id', '').upper() == zone_upper:
            cols = z.get('columns', [])
            break

    if not cols:
        cols = [0, 1] if zone_upper == 'A' else ([2] if zone_upper == 'B' else [3, 4])

    occupied_nodes = {o.get('node', '').strip() for o in data.get('origins', [])}
    occupied_nodes.update(t.get('node', '').strip() for t in data.get('tables', []))

    max_rows = data.get('rows', 5)
    # Buscar celda desocupada en las columnas de la zona
    for y in range(1, max_rows):
        for x in cols:
            coord = f"{x},{y}"
            if coord not in occupied_nodes:
                return coord

    # Si todo el rango está ocupado, sugerir fila siguiente en la primera columna de la zona
    return f"{cols[0]},{max_rows}"


def update_dimensions(columns: int, rows: int) -> Dict[str, Any]:
    """Actualiza las dimensiones del salón validando que ninguna mesa existente quede fuera."""
    if columns < 3 or rows < 3:
        raise ValueError("Las dimensiones mínimas del salón son de 3x3.")
    if columns > 30 or rows > 30:
        raise ValueError("Las dimensiones máximas soportadas en el plano CAD son de 30x30.")

    data = get_layout()
    for t in data.get('tables', []):
        tx, ty = _parse_node(t.get('node', '0,0'))
        if tx >= columns or ty >= rows:
            raise ValueError(f"No se pueden reducir las dimensiones: la mesa '{t.get('label', t['id'])}' está en ({tx},{ty}).")

    for o in data.get('origins', []):
        ox, oy = _parse_node(o.get('node', '0,0'))
        if ox >= columns or oy >= rows:
            raise ValueError(f"No se pueden reducir las dimensiones: el punto '{o.get('label', o['id'])}' está en ({ox},{oy}).")

    data['columns'] = columns
    data['rows'] = rows
    save_layout(data)
    return {'columns': columns, 'rows': rows}


def add_table(
    code: str,
    label: str,
    seats: int = 4,
    zone: str = 'A',
    node: str = '1,4',
) -> Dict[str, Any]:
    """Registra una nueva mesa en el plano topológico y en la base de datos con detección de colisiones y auto-expansión."""
    from .models import TableState

    code = code.lower().strip()
    data = get_layout()

    # Verificar si el código ya existe
    for t in data.get('tables', []):
        if t['id'] == code:
            raise ValueError(f"Ya existe una mesa con el código '{code}'.")

    x, y = _parse_node(node)
    _check_collision(data, f"{x},{y}")

    # Auto-expansión dinámica del plano si se coloca fuera de los límites actuales
    if x >= data.get('columns', 5):
        data['columns'] = x + 1
    if y >= data.get('rows', 5):
        data['rows'] = y + 1

    new_table = {
        'id': code,
        'label': label.strip(),
        'seats': int(seats),
        'zone': zone.upper().strip(),
        'node': f"{x},{y}",
    }
    data['tables'].append(new_table)
    with transaction.atomic():
        TableState.objects.get_or_create(code=code, defaults={'state': 'disponible'})
        save_layout(data)
    return new_table


def move_table(
    code: str,
    new_node: Optional[str] = None,
    new_zone: Optional[str] = None,
) -> Dict[str, Any]:
    """Actualiza las coordenadas de cuadrícula y/o zona de una mesa con prevención de colisiones."""
    code = code.lower().strip()
    data = get_layout()

    target_table = None
    for t in data.get('tables', []):
        if t['id'] == code:
            target_table = t
            break

    if not target_table:
        raise ValueError(f"No se encontró la mesa '{code}' en el plano.")

    # Si se cambia de zona y no se suministra nodo (o es 'auto'), sugerir coordenada en nueva zona
    if new_zone and (not new_node or new_node.strip().lower() == 'auto'):
        new_node = suggest_zone_coordinates(new_zone, data)
    elif not new_node:
        new_node = target_table.get('node', '1,1')

    x, y = _parse_node(new_node)
    _check_collision(data, f"{x},{y}", exclude_table_id=code)

    # Auto-expansión si la nueva posición excede el tamaño actual
    if x >= data.get('columns', 5):
        data['columns'] = x + 1
    if y >= data.get('rows', 5):
        data['rows'] = y + 1

    target_table['node'] = f"{x},{y}"
    if new_zone:
        target_table['zone'] = new_zone.upper().strip()

    save_layout(data)
    return target_table


def unify_tables(
    table_codes: List[str],
    unified_code: str,
    unified_label: str,
) -> Dict[str, Any]:
    """Fusiona 2 o más mesas contiguas preservando los datos de origen para posterior separación."""
    from .models import TableState

    data = get_layout()
    existing_tables = {t['id']: t for t in data.get('tables', [])}

    normalized_codes = [c.lower().strip() for c in table_codes]
    if len(normalized_codes) < 2:
        raise ValueError("Se requieren al menos 2 mesas para realizar una unificación.")

    for c in normalized_codes:
        if c not in existing_tables:
            raise ValueError(f"La mesa '{c}' no existe en el plano.")

    # Copiar estado íntegro de las mesas originales para permitir desunificación exacta
    original_tables = [dict(existing_tables[c]) for c in normalized_codes]

    # Calcular capacidad combinada y nodo/zona primaria
    combined_seats = sum(int(existing_tables[c].get('seats', 4)) for c in normalized_codes)
    primary_table = existing_tables[normalized_codes[0]]
    node = primary_table['node']
    zone = primary_table['zone']

    unified_code = unified_code.lower().strip()
    unified_table = {
        'id': unified_code,
        'label': unified_label.strip(),
        'seats': combined_seats,
        'zone': zone,
        'node': node,
        'unified_from': normalized_codes,
        'original_tables': original_tables,
    }

    # Filtrar las mesas unificadas y añadir la nueva mesa consolidada
    data['tables'] = [t for t in data['tables'] if t['id'] not in normalized_codes]
    data['tables'].append(unified_table)
    with transaction.atomic():
        TableState.objects.get_or_create(code=unified_code, defaults={'state': 'disponible'})
        save_layout(data)
    return unified_table


def separate_table(unified_code: str) -> List[Dict[str, Any]]:
    """Desunifica una mesa compuesta, restaurando sus mesas originales en sus coordenadas y estados."""
    from .models import TableState

    unified_code = unified_code.lower().strip()
    data = get_layout()

    target_idx = None
    target_table = None
    for idx, t in enumerate(data.get('tables', [])):
        if t['id'] == unified_code:
            target_idx = idx
            target_table = t
            break

    if target_table is None or target_idx is None:
        raise ValueError(f"No se encontró la mesa '{unified_code}' en el plano.")

    original_tables = target_table.get('original_tables')
    if not original_tables and 'unified_from' in target_table:
        # Fallback de reconstrucción si faltase la clave explícita
        unified_from = target_table.get('unified_from', [])
        original_tables = [
            {'id': cid, 'label': f"Mesa {cid.replace('mesa', '').zfill(2)}", 'seats': 4, 'zone': target_table.get('zone', 'A'), 'node': target_table.get('node', '1,1')}
            for cid in unified_from
        ]

    if not original_tables:
        raise ValueError(f"La mesa '{unified_code}' no es el resultado de una unificación de mesas.")

    # Verificar que las posiciones originales no hayan sido ocupadas
    other_tables = [t for i, t in enumerate(data['tables']) if i != target_idx]
    occupied_nodes = {t['node']: t.get('label', t['id']) for t in other_tables}
    for o in data.get('origins', []):
        occupied_nodes[o['node']] = o.get('label', o['id'])

    for orig in original_tables:
        orig_node = orig.get('node', '')
        if orig_node in occupied_nodes:
            raise ValueError(
                f"No se puede separar: la posición {orig_node} de '{orig.get('label', orig['id'])}' está ocupada por '{occupied_nodes[orig_node]}'."
            )

    # Eliminar la mesa unificada y restaurar mesas originales
    data['tables'].pop(target_idx)
    for orig in original_tables:
        restored = {
            'id': orig['id'],
            'label': orig['label'],
            'seats': int(orig.get('seats', 4)),
            'zone': orig.get('zone', 'A'),
            'node': orig['node'],
        }
        data['tables'].append(restored)

    with transaction.atomic():
        TableState.objects.filter(code=unified_code).delete()
        for orig in original_tables:
            TableState.objects.get_or_create(code=orig['id'], defaults={'state': 'disponible'})
        save_layout(data)

    return original_tables
