"""Microservicio independiente de ruteo: Algoritmo Dijkstra y evasión de congestión."""
import json
import logging

logger = logging.getLogger("routing")
from heapq import heappop, heappush
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title='OptiFlow · Ruteo operativo',
    version='1.0.0',
    description='Cálculo de trayectos óptimos y recalculo dinámico ante zonas críticas.',
)

CONFIG_PATH = (
    Path('/app/config/salon.json')
    if Path('/app/config/salon.json').exists()
    else Path(__file__).resolve().parents[2] / 'config' / 'salon.json'
)
LAYOUT: Dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
ORIGINS: Dict[str, str] = {o['id']: o['node'] for o in LAYOUT['origins']}
TABLES: Dict[str, str] = {t['id']: t['node'] for t in LAYOUT['tables']}
WIDTH: int = LAYOUT['columns']
HEIGHT: int = LAYOUT['rows']
CONGESTION: Set[str] = set(LAYOUT['demo_congestion_nodes'])


class RouteRequest(BaseModel):
    """Esquema de solicitud de cálculo de ruta."""
    origin: str = Field(default='cocina', description='Identificador del punto de partida.')
    destination: str = Field(default='mesa08', description='Identificador de la mesa destino.')
    task_type: str = Field(default='entrega', description='Tipo de servicio (entrega o retiro).')
    avoid_congestion: bool = Field(default=False, description='Si es True, evade nodos congestionados.')
    zone_levels: Dict[str, str] = Field(default_factory=dict, description='Niveles actuales de zonas.')


def neighbors(node: str) -> Generator[str, None, None]:
    """Genera los nodos adyacentes válidos dentro de la cuadrícula del salón."""
    x, y = map(int, node.split(','))
    # En empates favorecemos circulación horizontal por pasillo principal.
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
            yield f'{nx},{ny}'


def shortest(start: str, end: str, avoid_nodes: Set[str]) -> Optional[List[str]]:
    """Calcula el camino más corto utilizando el algoritmo Dijkstra con penalización heurística.

    Args:
        start: Coordenada 'x,y' inicial.
        end: Coordenada 'x,y' final.
        avoid_nodes: Conjunto de coordenadas 'x,y' a esquivar si es posible.

    Returns:
        Lista de coordenadas que forman la ruta, o None si no hay trayecto disponible.
    """
    if start == end:
        return [start]

    heap: List[tuple] = [(0, 0, start)]
    previous: Dict[str, str] = {}
    best: Dict[str, float] = {start: 0}
    serial = 1

    while heap:
        cost, _, u = heappop(heap)
        if cost != best[u]:
            continue
        if u == end:
            break
        for v in neighbors(u):
            if v in avoid_nodes and v != end:
                continue
            # Preferimos nodos del pasillo central (y=2) a igualdad de distancia.
            penalty = 0.001 if int(v.split(',')[1]) != 2 else 0
            candidate = cost + 1 + penalty
            if candidate < best.get(v, float('inf')):
                best[v] = candidate
                previous[v] = u
                heappush(heap, (candidate, serial, v))
                serial += 1

    if end not in best:
        return None

    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    return list(reversed(path))


@app.get('/health')
def health() -> Dict[str, str]:
    """Endpoint de verificación de estado y liveness del microservicio."""
    return {'status': 'ok', 'service': 'routing'}


def get_current_layout() -> Dict[str, Any]:
    """Carga dinámicamente la configuración estructural para reflejar mesas creadas, movidas o unificadas (ECC)."""
    try:
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.warning("Fallo al leer topología desde %s: %s. Utilizando layout base.", CONFIG_PATH, exc)
        return LAYOUT


@app.get('/layout')
def layout() -> Dict[str, Any]:
    """Retorna la configuración estructural y geométrica del salón en tiempo real."""
    return get_current_layout()


@app.post('/route')
def route(request: RouteRequest) -> Dict[str, Any]:
    """Calcula la ruta óptima entre dos puntos, considerando la congestión operativa y topología dinámica."""
    cur_layout = get_current_layout()
    cur_origins = {o['id']: o['node'] for o in cur_layout.get('origins', [])}
    cur_tables = {t['id']: t['node'] for t in cur_layout.get('tables', [])}

    if request.origin not in cur_origins or request.destination not in cur_tables:
        raise HTTPException(status_code=400, detail='Origen o mesa no disponibles')
    if request.task_type not in ('entrega', 'retiro'):
        raise HTTPException(status_code=400, detail='Tipo de servicio inválido')

    start = cur_origins[request.origin]
    end = cur_tables[request.destination]

    # Mapeo espacial de nodos neurálgicos por zona topológica:
    zone_risk_nodes: Dict[str, Set[str]] = {
        'A': {'1,2'},
        'B': {'2,2'},
        'C': {'3,2'},
    }
    risky: Set[str] = set()
    for z_code, z_level in request.zone_levels.items():
        if z_level == 'critica' and z_code in zone_risk_nodes:
            risky.update(zone_risk_nodes[z_code])

    # Si no se especificó nivel por zona, usar la congestión demo si B o C tienen alerta
    if not risky and any(request.zone_levels.get(zone) == 'critica' for zone in ('B', 'C')):
        risky = set(CONGESTION)

    path = shortest(start, end, risky if request.avoid_congestion else set())
    if path is None:
        raise HTTPException(
            status_code=404,
            detail='No se encontró una ruta disponible. Recalcular o volver al panel.',
        )

    crossed = sorted(set(path) & risky)
    notice = (
        'Ruta alternativa para evitar los nodos congestionados.'
        if request.avoid_congestion
        else 'Se detectó congestión en el trayecto: puedes recalcular la ruta.'
        if crossed
        else 'Ruta recomendada disponible, sin congestión en el trayecto.'
    )

    return {
        'origin': request.origin,
        'destination': request.destination,
        'path': path,
        'distance': len(path) - 1,
        'congested': bool(crossed),
        'congested_nodes': crossed,
        'alternative': request.avoid_congestion,
        'notice': notice,
    }
