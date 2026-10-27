import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Profile, RouteConsultation, TableState, VisionAnalysis, Zone


class OptiFlowTests(TestCase):
    """Suite de pruebas unitarias para flujos de autenticación, roles y APIs REST."""

    @classmethod
    def setUpTestData(cls):
        """Inicializa usuarios de prueba con roles operativos y catálogo inicial de mesas y zonas."""
        cls.waiter = User.objects.create_user(
            username='camilo',
            password='Segura-12345-Waiter',
        )
        cls.captain = User.objects.create_user(
            username='capitan',
            password='Segura-12345-Captain',
        )
        cls.manager = User.objects.create_user(
            username='gerente',
            password='Segura-12345-Manager',
        )

        Profile.objects.create(user=cls.waiter, role='mesero')
        Profile.objects.create(user=cls.captain, role='capitan')
        Profile.objects.create(user=cls.manager, role='gerente')

        for code in 'ABC':
            Zone.objects.create(
                code=code,
                level='critica' if code == 'C' else 'normal',
                dwell_minutes=4.5 if code == 'C' else 0.5,
            )

        for i in range(1, 9):
            TableState.objects.create(code=f'mesa{i:02d}')

    def test_register_user_is_waiter_and_logged_in(self):
        """Verifica que un registro público asigne automáticamente rol mesero e inicie sesión."""
        response = self.client.post(
            reverse('register'),
            {
                'first_name': 'Nora',
                'last_name': 'Rivera',
                'username': 'norita',
                'email': 'nora@example.test',
                'password1': 'Clave-Fuerte-238*!',
                'password2': 'Clave-Fuerte-238*!',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(Profile.objects.get(user__username='norita').role, 'mesero')

    def test_role_is_not_escallatable_via_registration(self):
        """Verifica que el parámetro role inyectado en registro sea ignorado."""
        response = self.client.post(
            reverse('register'),
            {
                'first_name': 'Eva',
                'last_name': 'Mora',
                'username': 'evamora',
                'email': 'eva@example.test',
                'password1': 'Clave-Fuerte-238*!',
                'password2': 'Clave-Fuerte-238*!',
                'role': 'admin',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Profile.objects.get(user__username='evamora').role, 'mesero')

    def test_login_required(self):
        """Verifica que las vistas operativas redirijan a login si no hay sesión."""
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        self.assertEqual(self.client.get(reverse('vision')).status_code, 302)

    def test_default_admin_login(self):
        """Verifica el flujo de inicio de sesión exitoso con credenciales válidas."""
        admin = User.objects.create_superuser(
            username='admin',
            password='1234',
            email='admin@optiflow.local',
        )
        response = self.client.post(
            reverse('login'),
            {'username': 'admin', 'password': '1234'},
        )
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), admin.pk)

    def test_roles_limit_pages(self):
        """Verifica la restricción de páginas HTML según el rol operativo del usuario."""
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('routes')).status_code, 200)
        self.assertEqual(self.client.get(reverse('saturation')).status_code, 403)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 403)

        self.client.force_login(self.captain)
        self.assertEqual(self.client.get(reverse('vision')).status_code, 200)
        self.assertEqual(self.client.get(reverse('layout')).status_code, 200)

        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 200)
        self.assertEqual(self.client.get(reverse('routes')).status_code, 403)

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

    def test_captain_can_update_critical_dwell_time(self):
        """Verifica que un capitán pueda actualizar el tiempo y nivel de congestión de una zona."""
        self.client.force_login(self.captain)
        payload = '{"level":"critica","dwell_minutes":6.3}'
        response = self.client.post(
            reverse('api_update_zone', args=['C']),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['alert'])
        self.assertEqual(Zone.objects.get(code='C').dwell_minutes, 6.3)

    def test_waiter_cannot_update_zone(self):
        """Verifica que un mesero no tenga permisos para modificar zonas operativas."""
        self.client.force_login(self.waiter)
        payload = '{"level":"normal","dwell_minutes":0}'
        response = self.client.post(
            reverse('api_update_zone', args=['C']),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    @patch('core.views.optional_upload_s3', return_value='')
    @patch('core.views.analyze_image')
    def test_vision_pipeline_records_metadata(self, mocked_analyze, _mocked_s3):
        """Verifica la respuesta del endpoint DRF de visión con mock de OpenCV."""
        self.client.force_login(self.captain)
        mocked_analyze.return_value = (
            200,
            {
                'people_count': 2,
                'zone_counts': {'A': 1, 'B': 1, 'C': 0},
                'annotated_image': 'data:image/jpeg;base64,abc',
                'disclaimer': 'estimación',
            },
        )
        photo = SimpleUploadedFile('test.jpg', b'fakejpg', content_type='image/jpeg')
        response = self.client.post(reverse('api_vision'), {'file': photo})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisionAnalysis.objects.count(), 1)
        self.assertEqual(VisionAnalysis.objects.first().people_count, 2)

    def test_registration_creates_admin_notification(self):
        """Verifica que el registro de un nuevo mesero genere automáticamente una notificación para admin."""
        from .models import AdminNotification
        initial_count = AdminNotification.objects.count()
        response = self.client.post(
            reverse('register'),
            {
                'first_name': 'Carlos',
                'last_name': 'Santana',
                'username': 'csantana',
                'email': 'csantana@restaurant.local',
                'password1': 'Clave-Segura-2026*!',
                'password2': 'Clave-Segura-2026*!',
            },
        )
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(AdminNotification.objects.count(), initial_count + 1)
        notif = AdminNotification.objects.latest('id')
        self.assertIn('csantana', notif.message)
        self.assertFalse(notif.read)

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

    def test_profile_view_and_notification_read_api(self):
        """Verifica la carga del perfil y el marcado reactivo de notificaciones."""
        from .models import AdminNotification
        notif = AdminNotification.objects.create(title='Aviso Test', message='Mensaje de prueba')
        self.client.force_login(self.captain)

        # Ver perfil
        profile_res = self.client.get(reverse('profile'))
        self.assertEqual(profile_res.status_code, 200)

        # Marcar notificación leída
        read_res = self.client.post(reverse('api_mark_notification_read', args=[notif.id]))
        self.assertEqual(read_res.status_code, 200)
        notif.refresh_from_db()
        self.assertTrue(notif.read)

    @patch('core.views.optional_upload_s3', return_value='')
    @patch('core.views.analyze_image')
    def test_vision_propagates_to_zone_and_dijkstra(self, mocked_analyze, _mocked_s3):
        """Verifica que OpenCV propague la densidad detectada a los niveles de zona y a Dijkstra."""
        self.client.force_login(self.captain)
        # Simulamos 4 personas detectadas en Zona B (Pasillo Central)
        mocked_analyze.return_value = (
            200,
            {
                'people_count': 4,
                'zone_counts': {'A': 0, 'B': 4, 'C': 0},
                'annotated_image': 'data:image/jpeg;base64,mockedimg',
                'disclaimer': 'estimación',
            },
        )
        photo = SimpleUploadedFile('chef_cam_snapshot.jpg', b'fakejpgdata', content_type='image/jpeg')
        response = self.client.post(reverse('api_vision'), {'file': photo})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verificamos que la Zona B se actualice automáticamente a 'critica'
        zone_b = Zone.objects.get(code='B')
        self.assertEqual(zone_b.level, 'critica')
        self.assertGreaterEqual(zone_b.dwell_minutes, 4.5)

        # Verificamos que la respuesta contenga el feedback de sincronización y estado S3
        self.assertIn('sync_notice', data)
        self.assertIn('s3_status', data)
        self.assertEqual(len(data['updated_zones']), 3)

        # Verificamos que el ruteo Dijkstra reciba la zona B en crítica y desvíe la ruta si avoid=True
        route_payload = {
            'origin': 'cocina',
            'destination': 'mesa08',
            'task_type': 'entrega',
            'avoid_congestion': True,
        }
        with patch('core.views.calculate_route') as mocked_calc:
            mocked_calc.return_value = (
                200,
                {
                    'origin': 'cocina',
                    'destination': 'mesa08',
                    'path': ['0,2', '0,1', '1,1', '2,1', '3,1', '4,1', '4,2', '4,3'],
                    'distance': 7,
                    'congested': False,
                    'congested_nodes': [],
                    'alternative': True,
                    'notice': 'Ruta alternativa para evitar los nodos congestionados.',
                },
            )
            r_res = self.client.post(reverse('api_route'), data=json.dumps(route_payload), content_type='application/json')
            self.assertEqual(r_res.status_code, 200)
            mocked_calc.assert_called_once()
            call_args = mocked_calc.call_args[0][0]
            self.assertEqual(call_args['zone_levels']['B'], 'critica')


