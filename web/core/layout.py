"""Módulo de carga y lectura de la configuración espacial del salón."""
import json
from pathlib import Path

LAYOUT_PATH = Path(__file__).resolve().parents[2] / 'config' / 'salon.json'


def get_layout():
    """Lee y deserializa el esquema JSON topológico del restaurante."""
    with LAYOUT_PATH.open(encoding='utf-8') as f:
        return json.load(f)

