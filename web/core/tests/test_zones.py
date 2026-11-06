"""Saturación y permanencia de las zonas."""
import json

from django.urls import reverse

from ..models import Zone
from .base import OperationalTestCase


class ZoneTests(OperationalTestCase):
    """Saturación y permanencia de las zonas."""

    def test_manager_can_update_critical_dwell_time(self):
        """Verifica que el gerente pueda actualizar el tiempo y nivel de congestión de una zona."""
        self.client.force_login(self.manager)
        payload = '{"level":"critica","dwell_minutes":6.3}'
        response = self.client.post(
            reverse('api_update_zone', args=['C']),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['alert'])
        self.assertEqual(Zone.objects.get(code='C').dwell_minutes, 6.3)

    def test_captain_and_waiter_cannot_update_zone(self):
        """Verifica que el jefe de meseros y los meseros no tengan permisos para modificar zonas operativas."""
        for user in (self.captain, self.waiter):
            self.client.force_login(user)
            payload = '{"level":"normal","dwell_minutes":0}'
            response = self.client.post(
                reverse('api_update_zone', args=['C']),
                data=payload,
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)

    def test_strict_zone_dwell_thresholds_validation(self):
        """Verifica la validación estricta de umbrales matemáticos de permanencia en zonas (Req 8)."""
        self.client.force_login(self.manager)

        # 1. Intentar marcar como 'critica' con permanencia <= 4.0 min debe retornar 400
        res_crit = self.client.post(
            reverse('api_update_zone', args=['A']),
            data=json.dumps({'level': 'critica', 'dwell_minutes': 3.5}),
            content_type='application/json',
        )
        self.assertEqual(res_crit.status_code, 400)
        self.assertIn('Crítica', res_crit.json()['error'])

        # 2. Intentar marcar como 'normal' con permanencia > 2.0 min debe retornar 400
        res_norm = self.client.post(
            reverse('api_update_zone', args=['A']),
            data=json.dumps({'level': 'normal', 'dwell_minutes': 2.8}),
            content_type='application/json',
        )
        self.assertEqual(res_norm.status_code, 400)
        self.assertIn('Normal', res_norm.json()['error'])

        # 3. Intentar marcar como 'moderada' con permanencia fuera de (2.0, 4.0] debe retornar 400
        res_mod = self.client.post(
            reverse('api_update_zone', args=['A']),
            data=json.dumps({'level': 'moderada', 'dwell_minutes': 1.2}),
            content_type='application/json',
        )
        self.assertEqual(res_mod.status_code, 400)
        self.assertIn('Moderada', res_mod.json()['error'])

        # 4. Actualización válida dentro de rango debe retornar 200
        res_ok = self.client.post(
            reverse('api_update_zone', args=['A']),
            data=json.dumps({'level': 'critica', 'dwell_minutes': 5.2}),
            content_type='application/json',
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(Zone.objects.get(code='A').level, 'critica')
