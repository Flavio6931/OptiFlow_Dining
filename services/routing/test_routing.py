"""Pruebas unitarias para el algoritmo Dijkstra y desvío de congestión (ECC)."""
import unittest

from fastapi import HTTPException

from services.routing.main import RouteRequest, route, shortest


class RoutingServiceTests(unittest.TestCase):
    """Pruebas unitarias del microservicio de ruteo."""

    def test_normal_path(self):
        """Verifica el cálculo de distancia y ruta directa en condiciones normales."""
        result = route(
            RouteRequest(
                origin='cocina',
                destination='mesa08',
                zone_levels={'C': 'normal'},
            )
        )
        self.assertEqual(result['path'][0], '0,2')
        self.assertEqual(result['path'][-1], '4,3')
        self.assertEqual(result['distance'], 5)

    def test_reroute_avoids_critical_zone_nodes(self):
        """Verifica que el recálculo por congestión evite los nodos neurálgicos de la zona crítica."""
        # 1. Cuando la Zona C está crítica, evita el nodo '3,2'
        result_c = route(
            RouteRequest(
                origin='cocina',
                destination='mesa08',
                zone_levels={'C': 'critica'},
                avoid_congestion=True,
            )
        )
        self.assertFalse(result_c['congested'])
        self.assertNotIn('3,2', result_c['path'])

        # 2. Cuando tanto Zona B como Zona C están críticas, evita ambos nodos {'2,2', '3,2'}
        result_bc = route(
            RouteRequest(
                origin='cocina',
                destination='mesa08',
                zone_levels={'B': 'critica', 'C': 'critica'},
                avoid_congestion=True,
            )
        )
        self.assertFalse(result_bc['congested'])
        self.assertFalse(set(result_bc['path']) & {'2,2', '3,2'})

    def test_invalid_destination(self):
        """Verifica que un destino inexistente retorne HTTP 400 Bad Request."""
        with self.assertRaises(HTTPException) as ctx:
            route(RouteRequest(destination='mesa999_inexistente'))
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
