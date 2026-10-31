"""Microservicio independiente de ruteo: Algoritmo Dijkstra y evasión de congestión."""
import json
import logging

logger = logging.getLogger("routing")
from heapq import heappop, heappush
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
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


def _in_bounds(node: str, width: int, height: int) -> bool:
    """Verifica que una coordenada 'x,y' esté estrictamente dentro de los límites (0..width-1, 0..height-1)."""
    try:
        x, y = map(int, node.split(','))
        return 0 <= x < width and 0 <= y < height
    except (ValueError, TypeError, AttributeError):
        return False


def neighbors(node: str, width: Optional[int] = None, height: Optional[int] = None) -> Generator[str, None, None]:
    """Genera los nodos adyacentes válidos dentro de la cuadrícula del salón."""
    w = width if width is not None else WIDTH
    h = height if height is not None else HEIGHT
    x, y = map(int, node.split(','))
    # En empates favorecemos circulación horizontal por pasillo principal.
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h:
            yield f'{nx},{ny}'


def shortest(
    start: str,
    end: str,
    avoid_nodes: Set[str],
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[List[str]]:
    """Calcula el camino más corto utilizando el algoritmo Dijkstra dentro de los límites estrictos del salón."""
    w = width if width is not None else WIDTH
    h = height if height is not None else HEIGHT
    if not _in_bounds(start, w, h) or not _in_bounds(end, w, h):
        return None
    if start == end:
        return [start]

    aisle_y = min(2, h - 1)
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
        for v in neighbors(u, width=w, height=h):
            if v in avoid_nodes and v != end:
                continue
            # Preferimos nodos del pasillo central a igualdad de distancia.
            penalty = 0.001 if int(v.split(',')[1]) != aisle_y else 0
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


@app.get('/', include_in_schema=False)
def root() -> RedirectResponse:
    """Redirige automáticamente la raíz al explorador interactivo Swagger UI."""
    return RedirectResponse(url='/docs')


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

    width = int(cur_layout.get('columns', WIDTH))
    height = int(cur_layout.get('rows', HEIGHT))

    start = cur_origins[request.origin]
    end = cur_tables[request.destination]
    if not _in_bounds(start, width, height) or not _in_bounds(end, width, height):
        raise HTTPException(
            status_code=400,
            detail=f'Origen o destino fuera de las dimensiones activas del salón ({width}x{height}).',
        )

    # Mapeo espacial dinámico de nodos neurálgicos por zona dentro de los límites activos
    aisle_y = min(2, height - 1)
    origin_nodes = set(cur_origins.values())
    table_nodes_all = set(cur_tables.values())
    zone_risk_nodes: Dict[str, Set[str]] = {}
    for z in cur_layout.get('zones', []):
        z_id = str(z.get('id', '')).upper()
        z_cols = [int(c) for c in z.get('columns', []) if 0 <= int(c) < width]
        for col in z_cols:
            candidate_node = f'{col},{aisle_y}'
            if candidate_node not in origin_nodes and candidate_node not in table_nodes_all:
                zone_risk_nodes[z_id] = {candidate_node}
                break

    if not zone_risk_nodes:
        zone_risk_nodes = {
            k: {n for n in v if _in_bounds(n, width, height)}
            for k, v in {'A': {'1,2'}, 'B': {'2,2'}, 'C': {'3,2'}}.items()
        }

    risky: Set[str] = set()
    for z_code, z_level in request.zone_levels.items():
        if z_level == 'critica' and z_code in zone_risk_nodes:
            risky.update(zone_risk_nodes[z_code])

    if not risky and any(request.zone_levels.get(zone) == 'critica' for zone in ('B', 'C')):
        risky = {n for n in CONGESTION if _in_bounds(n, width, height)}

    # Mesas intermedias como obstáculos físicos estrictos: nunca caminar sobre otras mesas ni salir de límites
    other_tables = {
        node for t_id, node in cur_tables.items()
        if t_id != request.destination and _in_bounds(node, width, height)
    }
    avoid_nodes = set(other_tables)
    if request.avoid_congestion:
        avoid_nodes.update(risky)

    path = shortest(start, end, avoid_nodes, width=width, height=height)
    if path is None and request.avoid_congestion:
        # Si esquivar congestión obstruye todos los pasillos, mantener bloqueo de mesas intermedias dentro del mapa
        path = shortest(start, end, other_tables, width=width, height=height)

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
