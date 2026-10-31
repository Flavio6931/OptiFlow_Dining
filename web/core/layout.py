"""Módulo de carga, validación de límites estrictos y persistencia espacial del salón CAD (Req 6)."""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction

LAYOUT_PATH = Path(__file__).resolve().parents[2] / 'config' / 'salon.json'
VALID_ZONES = ('A', 'B', 'C')


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


def compute_zones_for_columns(columns: int) -> List[Dict[str, Any]]:
    """Particiona las columnas (0..columns-1) en tres sectores contiguos para las Zonas A, B y C."""
    if columns <= 3:
        cols_a, cols_b, cols_c = [0], [1], [2]
    elif columns == 4:
        cols_a, cols_b, cols_c = [0, 1], [2], [3]
    elif columns == 5:
        cols_a, cols_b, cols_c = [0, 1], [2], [3, 4]
    else:
        n_a = max(2, columns // 3)
        n_b = max(2, (columns - n_a) // 2) if columns >= 7 else 2
        cols_a = list(range(0, n_a))
        cols_b = list(range(n_a, n_a + n_b))
        cols_c = list(range(n_a + n_b, columns))

    return [
        {'id': 'A', 'label': 'Zona A', 'columns': cols_a},
        {'id': 'B', 'label': 'Zona B', 'columns': cols_b},
        {'id': 'C', 'label': 'Zona C', 'columns': cols_c},
    ]


def _cols_for_zone(data: Dict[str, Any], zone: str) -> List[int]:
    """Obtiene la lista de columnas válidas asociadas a una zona dentro del plano activo."""
    zone_upper = zone.upper().strip()
    if zone_upper not in VALID_ZONES:
        raise ValueError(f"Zona '{zone}' inválida. Las zonas permitidas son A, B o C.")

    columns = int(data.get('columns', 5))
    zones_cfg = data.get('zones') or compute_zones_for_columns(columns)
    for z in zones_cfg:
        if z.get('id', '').upper() == zone_upper:
            valid = [int(c) for c in z.get('columns', []) if 0 <= int(c) < columns]
            if valid:
                return valid

    for z in compute_zones_for_columns(columns):
        if z['id'] == zone_upper:
            return z['columns']
    return [0]


def _zone_for_x(data: Dict[str, Any], x: int) -> str:
    """Resuelve a qué zona topológica (A, B o C) pertenece una columna X."""
    for z_code in VALID_ZONES:
        if x in _cols_for_zone(data, z_code):
            return z_code
    return 'C'


def _parse_node(node: str) -> Tuple[int, int]:
    """Parsea y valida una coordenada 'X,Y' retornando tupla de enteros no negativos."""
    try:
        parts = [int(p.strip()) for p in node.split(',')]
        if len(parts) != 2 or parts[0] < 0 or parts[1] < 0:
            raise ValueError()
        return parts[0], parts[1]
    except (ValueError, TypeError, AttributeError):
        raise ValueError(
            "Coordenadas de cuadrícula inválidas. Debe tener formato 'X,Y' con números enteros (ej. '1,3')."
        )


def _check_bounds(data: Dict[str, Any], x: int, y: int) -> None:
    """Valida que la coordenada (X,Y) no supere el muro estricto de las dimensiones actuales del salón."""
    max_cols = int(data.get('columns', 5))
    max_rows = int(data.get('rows', 5))
    if x < 0 or x >= max_cols or y < 0 or y >= max_rows:
        raise ValueError(
            f"La posición ({x},{y}) está fuera de los límites del salón ({max_cols}x{max_rows}: "
            f"columnas 0 a {max_cols - 1}, filas 0 a {max_rows - 1}). "
            f"Amplía primero '📐 Dimensiones' si necesitas más espacio."
        )


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


def suggest_zone_coordinates(
    zone: str,
    layout_data: Optional[Dict[str, Any]] = None,
    exclude_table_id: Optional[str] = None,
) -> str:
    """Busca la primera celda libre dentro de las columnas y límites actuales de la zona indicada."""
    data = layout_data or get_layout()
    zone_upper = zone.upper().strip()
    cols = _cols_for_zone(data, zone_upper)
    max_cols = int(data.get('columns', 5))
    max_rows = int(data.get('rows', 5))

    occupied_nodes = {o.get('node', '').strip() for o in data.get('origins', [])}
    for t in data.get('tables', []):
        if exclude_table_id and t.get('id') == exclude_table_id:
            continue
        occupied_nodes.add(t.get('node', '').strip())

    # Priorizar filas de salón (evitando pasillo central y=2 y fila superior y=0 cuando haya alternativa)
    preferred_rows = (
        [y for y in range(1, max_rows) if y != 2]
        + ([0] if max_rows > 0 else [])
        + ([2] if max_rows > 2 else [])
    )
    preferred_cols = [x for x in cols if x > 0] + [x for x in cols if x == 0]

    for y in preferred_rows:
        for x in preferred_cols:
            coord = f"{x},{y}"
            if coord not in occupied_nodes:
                return coord

    raise ValueError(
        f"No hay espacio disponible para otra mesa en la Zona {zone_upper} "
        f"dentro de las dimensiones actuales ({max_cols}x{max_rows})."
    )


def update_dimensions(columns: int, rows: int) -> Dict[str, Any]:
    """Actualiza las dimensiones del salón y recalibra los sectores A/B/C validando límites activos."""
    if columns < 3 or rows < 3:
        raise ValueError("Las dimensiones mínimas del salón son de 3x3.")
    if columns > 30 or rows > 30:
        raise ValueError("Las dimensiones máximas soportadas en el plano CAD son de 30x30.")

    data = get_layout()
    for t in data.get('tables', []):
        tx, ty = _parse_node(t.get('node', '0,0'))
        if tx >= columns or ty >= rows:
            raise ValueError(
                f"No se pueden reducir las dimensiones: la mesa '{t.get('label', t['id'])}' está en ({tx},{ty})."
            )

    for o in data.get('origins', []):
        ox, oy = _parse_node(o.get('node', '0,0'))
        if ox >= columns or oy >= rows:
            raise ValueError(
                f"No se pueden reducir las dimensiones: el punto '{o.get('label', o['id'])}' está en ({ox},{oy})."
            )

    data['columns'] = columns
    data['rows'] = rows
    data['zones'] = compute_zones_for_columns(columns)

    # Sincronizar la etiqueta de zona de cada mesa con su columna en la nueva distribución espacial
    for t in data.get('tables', []):
        tx, _ = _parse_node(t.get('node', '0,0'))
        t['zone'] = _zone_for_x(data, tx)

    save_layout(data)
    return {'columns': columns, 'rows': rows, 'zones': data['zones']}


def add_table(
    code: str,
    label: str,
    seats: int = 4,
    zone: str = 'A',
    node: str = 'auto',
) -> Dict[str, Any]:
    """Registra una nueva mesa respetando estrictamente dimensiones, colisiones y pertenencia a la zona."""
    from .models import TableState

    code = code.lower().strip()
    zone_upper = zone.upper().strip()
    data = get_layout()

    for t in data.get('tables', []):
        if t['id'] == code:
            raise ValueError(f"Ya existe una mesa con el código '{code}'.")

    allowed_cols = _cols_for_zone(data, zone_upper)
    if not node or node.strip().lower() == 'auto':
        resolved_node = suggest_zone_coordinates(zone_upper, data)
    else:
        resolved_node = node.strip()

    x, y = _parse_node(resolved_node)
    _check_bounds(data, x, y)
    if x not in allowed_cols:
        actual_zone = _zone_for_x(data, x)
        cols_txt = ', '.join(str(c) for c in allowed_cols)
        raise ValueError(
            f"La coordenada ({x},{y}) pertenece a la Zona {actual_zone}, no a la Zona {zone_upper} "
            f"(columnas permitidas: {cols_txt}). Usa 'auto' para asignar sitio automáticamente."
        )
    _check_collision(data, f"{x},{y}")

    new_table = {
        'id': code,
        'label': label.strip(),
        'seats': int(seats),
        'zone': zone_upper,
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
    """Reubica físicamente una mesa por coordenadas o cambio de zona respetando muros y capacidad zonal."""
    code = code.lower().strip()
    data = get_layout()

    target_table = None
    for t in data.get('tables', []):
        if t['id'] == code:
            target_table = t
            break

    if not target_table:
        raise ValueError(f"No se encontró la mesa '{code}' en el plano.")

    current_node = target_table.get('node', '1,1').strip()
    current_zone = target_table.get('zone', 'A').upper().strip()
    requested_zone = new_zone.upper().strip() if new_zone else None
    if requested_zone:
        _cols_for_zone(data, requested_zone)

    cleaned_node = new_node.strip() if new_node else ''
    zone_changed = bool(requested_zone and requested_zone != current_zone)

    # Si cambia la zona y el nodo es vacío, 'auto', o sigue siendo la coordenada vieja de otra zona -> reubicar
    if requested_zone and (
        not cleaned_node
        or cleaned_node.lower() == 'auto'
        or (zone_changed and cleaned_node == current_node)
    ):
        resolved_node = suggest_zone_coordinates(requested_zone, data, exclude_table_id=code)
        final_zone = requested_zone
    elif not cleaned_node or cleaned_node.lower() == 'auto':
        target_z = requested_zone or current_zone
        resolved_node = suggest_zone_coordinates(target_z, data, exclude_table_id=code)
        final_zone = target_z
    else:
        resolved_node = cleaned_node
        x_tmp, y_tmp = _parse_node(resolved_node)
        _check_bounds(data, x_tmp, y_tmp)
        inferred_zone = _zone_for_x(data, x_tmp)
        if zone_changed and requested_zone != inferred_zone:
            cols_txt = ', '.join(str(c) for c in _cols_for_zone(data, requested_zone))
            raise ValueError(
                f"La posición ({x_tmp},{y_tmp}) corresponde a la Zona {inferred_zone}, no a la Zona {requested_zone} "
                f"(columnas {cols_txt}). Deja el nodo en 'auto' para moverla automáticamente a la Zona {requested_zone}."
            )
        final_zone = inferred_zone

    x, y = _parse_node(resolved_node)
    _check_bounds(data, x, y)
    _check_collision(data, f"{x},{y}", exclude_table_id=code)

    target_table['node'] = f"{x},{y}"
    target_table['zone'] = final_zone

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

    original_tables = [dict(existing_tables[c]) for c in normalized_codes]
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
        unified_from = target_table.get('unified_from', [])
        original_tables = [
            {
                'id': cid,
                'label': f"Mesa {cid.replace('mesa', '').zfill(2)}",
                'seats': 4,
                'zone': target_table.get('zone', 'A'),
                'node': target_table.get('node', '1,1'),
            }
            for cid in unified_from
        ]

    if not original_tables:
        raise ValueError(f"La mesa '{unified_code}' no es el resultado de una unificación de mesas.")

    other_tables = [t for i, t in enumerate(data['tables']) if i != target_idx]
    occupied_nodes = {t['node']: t.get('label', t['id']) for t in other_tables}
    for o in data.get('origins', []):
        occupied_nodes[o['node']] = o.get('label', o['id'])

    for orig in original_tables:
        orig_node = orig.get('node', '')
        ox, oy = _parse_node(orig_node)
        _check_bounds(data, ox, oy)
        if orig_node in occupied_nodes:
            raise ValueError(
                f"No se puede separar: la posición {orig_node} de '{orig.get('label', orig['id'])}' "
                f"está ocupada por '{occupied_nodes[orig_node]}'."
            )

    data['tables'].pop(target_idx)
    for orig in original_tables:
        ox, _ = _parse_node(orig['node'])
        restored = {
            'id': orig['id'],
            'label': orig['label'],
            'seats': int(orig.get('seats', 4)),
            'zone': _zone_for_x(data, ox),
            'node': orig['node'],
        }
        data['tables'].append(restored)

    with transaction.atomic():
        TableState.objects.filter(code=unified_code).delete()
        for orig in original_tables:
            TableState.objects.get_or_create(code=orig['id'], defaults={'state': 'disponible'})
        save_layout(data)

    return original_tables
