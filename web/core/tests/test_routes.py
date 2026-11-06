"""Cálculo, asignación y cierre de rutas."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from ..models import RouteConsultation
from .base import OperationalTestCase


class RouteTests(OperationalTestCase):
    """Cálculo, asignación y cierre de rutas."""

    @patch('core.views.calculate_route')
    def test_route_api_records_task(self, mocked_calculate):
        """Verifica el cálculo y guardado de rutas en la API de Django REST Framework."""
        self.client.force_login(self.waiter)
        mocked_calculate.return_value = (
            200,
            {
                'origin': 'cocina',
                'destination': 'mesa08',
                'path': ['0,2', '1,2', '2,2', '3,2', '4,2', '4,3'],
                'distance': 5,
                'congested': True,
                'congested_nodes': ['2,2'],
                'alternative': False,
                'notice': 'Atención',
            },
        )
        payload = (
            '{"origin":"cocina","destination":"mesa08","task_type":"entrega",'
            '"avoid_congestion":false}'
        )
        response = self.client.post(
            reverse('api_route'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RouteConsultation.objects.count(), 1)
        self.assertTrue(RouteConsultation.objects.first().congested)

        complete_response = self.client.post(
            reverse('api_complete', args=[response.json()['route_id']])
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertTrue(RouteConsultation.objects.first().completed)

    @patch('core.views.calculate_route')
    def test_route_assignment_and_waiter_completion(self, mocked_calculate):
        """Verifica que una ruta asignada por capitán pueda ser completada por el mesero asignado."""
        mocked_calculate.return_value = (
            200,
            {
                'origin': 'cocina',
                'destination': 'mesa04',
                'path': ['0,2', '1,2', '2,2', '3,2'],
                'distance': 3,
                'congested': False,
                'congested_nodes': [],
                'alternative': False,
                'notice': 'Ruta despejada',
            },
        )
        # El capitán crea y asigna la ruta al mesero camilo
        self.client.force_login(self.captain)
        payload = (
            f'{{"origin":"cocina","destination":"mesa04","task_type":"entrega",'
            f'"avoid_congestion":false,"assigned_waiter":{self.waiter.id}}}'
        )
        response = self.client.post(reverse('api_route'), data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        route_id = response.json()['route_id']
        consultation = RouteConsultation.objects.get(id=route_id)
        self.assertEqual(consultation.assigned_waiter, self.waiter)
        self.assertFalse(consultation.completed)

        # El mesero camilo completa la ruta asignada
        self.client.force_login(self.waiter)
        complete_res = self.client.post(reverse('api_complete', args=[route_id]))
        self.assertEqual(complete_res.status_code, 200)
        consultation.refresh_from_db()
        self.assertTrue(consultation.completed)

    @patch('core.views.calculate_route')
    def test_auto_safe_reroute_on_assigned_waiter(self, mocked_calculate):
        """Verifica que si una ruta asignada a mesero presenta congestión, se recalcule el desvío seguro (Req 3 & 8)."""
        self.client.force_login(self.captain)

        congested_res = {
            'origin': 'cocina',
            'destination': 'mesa08',
            'path': ['0,2', '1,2', '2,2', '3,2', '4,2'],
            'distance': 4,
            'congested': True,
            'congested_nodes': ['2,2'],
            'alternative': False,
            'notice': 'Atención: nodo congestionado detectado.',
        }
        safe_detour_res = {
            'origin': 'cocina',
            'destination': 'mesa08',
            'path': ['0,2', '0,1', '1,1', '2,1', '3,1', '4,1', '4,2'],
            'distance': 6,
            'congested': False,
            'congested_nodes': [],
            'alternative': True,
            'notice': 'Desvío seguro calculado para evitar zonas críticas.',
        }

        mocked_calculate.side_effect = [
            (200, congested_res),
            (200, safe_detour_res),
        ]

        payload = {
            'origin': 'cocina',
            'destination': 'mesa08',
            'task_type': 'entrega',
            'avoid_congestion': False,
            'assigned_waiter': self.waiter.id,
        }

        response = self.client.post(
            reverse('api_route'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['recalculated'])
        self.assertTrue(data['auto_safe_reroute'])
        self.assertFalse(data['congested'])
        self.assertEqual(data['distance'], 6)

        record = RouteConsultation.objects.get(id=data['route_id'])
        self.assertTrue(record.recalculated)
        self.assertFalse(record.congested)
        self.assertEqual(record.assigned_waiter, self.waiter)

    @patch('core.views.calculate_route')
    def test_assigned_task_lifecycle_and_supervisor_notifications(self, mocked_calculate):
        """Verifica el ciclo completo de rutas asignadas y la notificación al supervisor (Capitán y Gerente)."""
        from ..models import AdminNotification

        mocked_calculate.return_value = (
            200,
            {
                'origin': 'entrada',
                'destination': 'mesa04',
                'path': ['0,4', '1,4', '2,4', '3,4', '4,4', '4,2', '4,1'],
                'distance': 6,
                'congested': False,
                'congested_nodes': [],
                'alternative': False,
                'notice': 'Ruta despejada',
            },
        )

        # 1. Capitán asigna ruta a camilo
        self.client.force_login(self.captain)
        r1 = self.client.post(
            reverse('api_route'),
            data=json.dumps({
                'origin': 'entrada',
                'destination': 'mesa04',
                'task_type': 'entrega',
                'avoid_congestion': False,
                'assigned_waiter': self.waiter.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()['status_label'], 'Pendiente')
        route1_id = r1.json()['route_id']

        # 2. Gerente también asigna ruta a camilo
        self.client.force_login(self.manager)
        r2 = self.client.post(
            reverse('api_route'),
            data=json.dumps({
                'origin': 'cocina',
                'destination': 'mesa03',
                'task_type': 'retiro',
                'avoid_congestion': False,
                'assigned_waiter': self.waiter.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(r2.status_code, 200)
        route2_id = r2.json()['route_id']

        # 3. Mesero camilo ve 2 tareas urgentes y data-path listo para trazar sin duplicar
        self.client.force_login(self.waiter)
        routes_page = self.client.get(reverse('routes'))
        self.assertEqual(routes_page.context['waiter_pending_assigned_count'], 2)
        self.assertIn('data-path=', routes_page.content.decode('utf-8'))

        # 4. Camilo finaliza la tarea 1 -> contador baja a 1 y Capitán recibe notificación exclusiva
        comp1 = self.client.post(reverse('api_complete', args=[route1_id]))
        self.assertEqual(comp1.status_code, 200)
        self.assertEqual(comp1.json()['pending_assigned_count'], 1)
        self.assertTrue(comp1.json()['notified_supervisor'])
        self.assertTrue(
            AdminNotification.objects.filter(recipient=self.captain, read=False, message__icontains='camilo').exists()
        )
        self.assertFalse(
            AdminNotification.objects.filter(recipient=self.manager, read=False).exists()
        )

        # 5. Camilo finaliza la tarea 2 -> contador llega a 0 y Gerente recibe notificación en campana y perfil
        comp2 = self.client.post(reverse('api_complete', args=[route2_id]))
        self.assertEqual(comp2.status_code, 200)
        self.assertEqual(comp2.json()['pending_assigned_count'], 0)
        self.assertTrue(
            AdminNotification.objects.filter(recipient=self.manager, read=False, message__icontains='camilo').exists()
        )

        self.client.force_login(self.manager)
        mgr_summary = self.client.get(reverse('api_notifications_summary'))
        self.assertEqual(mgr_summary.status_code, 200)
        self.assertGreaterEqual(mgr_summary.json()['unread_count'], 1)


class RoutingLayoutSyncTests(TestCase):
    """El microservicio de rutas debe recibir siempre el plano vigente desde Django."""

    @patch('core.services.requests.post')
    def test_calculate_route_sends_current_layout(self, mocked_post):
        from ..layout import get_layout
        from ..services import calculate_route

        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {'path': [], 'distance': 0, 'congested': False}
        calculate_route({'origin': 'cocina', 'destination': 'mesa08'})

        sent = mocked_post.call_args.kwargs['json']
        self.assertEqual(sent['layout'], get_layout())
        self.assertEqual(sent['origin'], 'cocina')
