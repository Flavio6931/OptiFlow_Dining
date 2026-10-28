"""Módulo de carga, lectura y persistencia de la configuración espacial del salón (Req 6)."""
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
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


def add_table(
    code: str,
    label: str,
    seats: int = 4,
    zone: str = 'A',
    node: str = '1,4',
) -> Dict[str, Any]:
    """Registra una nueva mesa en el plano topológico y en la base de datos."""
    from .models import TableState

    code = code.lower().strip()
    data = get_layout()

    # Verificar si el código ya existe
    for t in data.get('tables', []):
        if t['id'] == code:
            raise ValueError(f"Ya existe una mesa con el código '{code}'.")

    new_table = {
        'id': code,
        'label': label.strip(),
        'seats': int(seats),
        'zone': zone.upper().strip(),
        'node': node.strip(),
    }
    data['tables'].append(new_table)
    with transaction.atomic():
        TableState.objects.get_or_create(code=code, defaults={'state': 'disponible'})
        save_layout(data)
    return new_table


def move_table(
    code: str,
    new_node: str,
    new_zone: Optional[str] = None,
) -> Dict[str, Any]:
    """Actualiza las coordenadas de cuadrícula y/o zona de una mesa existente."""
    code = code.lower().strip()
    data = get_layout()

    found = False
    updated_table = {}
    for t in data.get('tables', []):
        if t['id'] == code:
            t['node'] = new_node.strip()
            if new_zone:
                t['zone'] = new_zone.upper().strip()
            updated_table = t
            found = True
            break

    if not found:
        raise ValueError(f"No se encontró la mesa '{code}' en el plano.")

    save_layout(data)
    return updated_table


def unify_tables(
    table_codes: List[str],
    unified_code: str,
    unified_label: str,
) -> Dict[str, Any]:
    """Fusiona 2 o más mesas contiguas para atención de grupos grandes con capacidad combinada."""
    from .models import TableState

    data = get_layout()
    existing_tables = {t['id']: t for t in data.get('tables', [])}

    normalized_codes = [c.lower().strip() for c in table_codes]
    if len(normalized_codes) < 2:
        raise ValueError("Se requieren al menos 2 mesas para realizar una unificación.")

    for c in normalized_codes:
        if c not in existing_tables:
            raise ValueError(f"La mesa '{c}' no existe en el plano.")

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
    }

    # Filtrar las mesas unificadas y añadir la nueva mesa consolidada
    data['tables'] = [t for t in data['tables'] if t['id'] not in normalized_codes]
    data['tables'].append(unified_table)
    with transaction.atomic():
        TableState.objects.get_or_create(code=unified_code, defaults={'state': 'disponible'})
        save_layout(data)
    return unified_table
