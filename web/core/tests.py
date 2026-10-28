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



    def test_strict_zone_dwell_thresholds_validation(self):
        """Verifica la validación estricta de umbrales matemáticos de permanencia en zonas (Req 8)."""
        self.client.force_login(self.captain)

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

    def test_user_can_update_personal_data_without_changing_role(self):
        """Verifica que un usuario pueda actualizar sus datos personales pero no auto-escalar su rol (Req 7)."""
        self.client.force_login(self.waiter)
        response = self.client.post(
            reverse('profile'),
            data={
                'first_name': 'Camilo Editado',
                'last_name': 'Perez',
                'email': 'camilo.editado@test.local',
                'role': 'admin',  # Intento de escalamiento malicioso
            },
        )
        self.assertRedirects(response, reverse('profile'))
        self.waiter.refresh_from_db()
        self.assertEqual(self.waiter.first_name, 'Camilo Editado')
        self.assertEqual(self.waiter.last_name, 'Perez')
        self.assertEqual(self.waiter.email, 'camilo.editado@test.local')
        # Su rol debe permanecer como mesero inmutable
        self.assertEqual(self.waiter.profile.role, 'mesero')

    def test_admin_can_update_staff_role_and_security_shields(self):
        """Verifica la asignación de rol de Jefe de Meseros por Admin y el blindaje de seguridad (Req 5 & 7)."""
        admin = User.objects.create_superuser(username='superadmin', password='123', email='sa@test.com')
        other_admin = User.objects.create_superuser(username='otheradmin', password='123', email='oa@test.com')
        self.client.force_login(admin)

        # 1. Admin promueve exitosamente al mesero camilo a 'capitan' (Jefe de meseros)
        promote_res = self.client.post(
            reverse('api_update_user_role', args=[self.waiter.id]),
            data=json.dumps({'role': 'capitan'}),
            content_type='application/json',
        )
        self.assertEqual(promote_res.status_code, 200)
        self.waiter.profile.refresh_from_db()
        self.assertEqual(self.waiter.profile.role, 'capitan')
        self.assertIn('Jefe de meseros', promote_res.json()['new_role_display'])

        # 2. Blindaje 1: Admin no puede alterar su propio rol
        self_res = self.client.post(
            reverse('api_update_user_role', args=[admin.id]),
            data=json.dumps({'role': 'mesero'}),
            content_type='application/json',
        )
        self.assertEqual(self_res.status_code, 400)
        self.assertIn('propio rol', self_res.json()['error'])

        # 3. Blindaje 2: Admin no puede degradar a otro superusuario
        other_admin_res = self.client.post(
            reverse('api_update_user_role', args=[other_admin.id]),
            data=json.dumps({'role': 'mesero'}),
            content_type='application/json',
        )
        self.assertEqual(other_admin_res.status_code, 403)
        self.assertIn('otros administradores', other_admin_res.json()['error'])

    def test_waiter_cannot_call_update_role_api(self):
        """Verifica que un mesero reciba 403 Forbidden al intentar invocar la API de asignación de roles."""
        self.client.force_login(self.waiter)
        response = self.client.post(
            reverse('api_update_user_role', args=[self.waiter.id]),
            data=json.dumps({'role': 'admin'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_move_and_unify_cad_tables(self):
        """Verifica la creación, reubicación y unificación dinámica de mesas CAD por Admin (Req 6)."""
        from .layout import LAYOUT_PATH
        original_json = LAYOUT_PATH.read_text(encoding='utf-8')
        admin = User.objects.create_superuser(username='cad_admin', password='123', email='cad@test.com')
        self.client.force_login(admin)

        try:
            # 1. Crear nueva mesa 'mesa99' en zona A, nodo 1,4
            create_res = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa99',
                    'label': 'Mesa 99',
                    'seats': 6,
                    'zone': 'A',
                    'node': '1,4',
                }),
                content_type='application/json',
            )
            self.assertEqual(create_res.status_code, 201)
            self.assertTrue(TableState.objects.filter(code='mesa99').exists())

            # 2. Reubicar mesa99 a nodo 2,4
            move_res = self.client.post(
                reverse('api_move_table', args=['mesa99']),
                data=json.dumps({'node': '2,4', 'zone': 'B'}),
                content_type='application/json',
            )
            self.assertEqual(move_res.status_code, 200)
            self.assertEqual(move_res.json()['table']['node'], '2,4')

            # 3. Unificar mesa99 y mesa01 para grupo grande
            unify_res = self.client.post(
                reverse('api_unify_tables'),
                data=json.dumps({
                    'table_codes': ['mesa01', 'mesa99'],
                    'unified_code': 'mesa_vip_grupo',
                    'unified_label': 'Mesa VIP Consolidada',
                }),
                content_type='application/json',
            )
            self.assertEqual(unify_res.status_code, 200)
            data = unify_res.json()
            self.assertTrue(TableState.objects.filter(code='mesa_vip_grupo').exists())
            self.assertEqual(data['unified_table']['seats'], 10)  # 4 de mesa01 + 6 de mesa99

        finally:
            # Restaurar estado original de salon.json
            LAYOUT_PATH.write_text(original_json, encoding='utf-8')

    def test_waiter_cannot_modify_cad_layout(self):
        """Verifica que un mesero no tenga permisos para crear, mover o fusionar mesas CAD."""
        self.client.force_login(self.waiter)
        res_create = self.client.post(
            reverse('api_create_table'),
            data=json.dumps({'code': 'm_fake', 'label': 'Fake', 'node': '0,0'}),
            content_type='application/json',
        )
        self.assertEqual(res_create.status_code, 403)

        res_move = self.client.post(
            reverse('api_move_table', args=['mesa01']),
            data=json.dumps({'node': '0,0'}),
            content_type='application/json',
        )
        self.assertEqual(res_move.status_code, 403)

        res_unify = self.client.post(
            reverse('api_unify_tables'),
            data=json.dumps({'table_codes': ['mesa01', 'mesa02']}),
            content_type='application/json',
        )
        self.assertEqual(res_unify.status_code, 403)

    def test_lan_multidevice_context_and_settings(self):
        """Verifica la inyeccion de IP/URL de red local en contexto y la compatibilidad con dispositivos moviles/tablets."""
        from django.conf import settings
        self.client.force_login(self.manager)

        # 1. Verificar que ALLOWED_HOSTS permita host '*' o la IP del host
        # Blindaje ECC: ALLOWED_HOSTS no debe contener comodín '*' y debe incluir hosts válidos
        self.assertNotIn('*', settings.ALLOWED_HOSTS)
        self.assertTrue(len(settings.ALLOWED_HOSTS) > 0)

        # 2. Navegar al dashboard simulando una Tablet / iPad
        res = self.client.get(
            reverse('dashboard'),
            HTTP_USER_AGENT='Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
        )
        self.assertEqual(res.status_code, 200)

        # 3. Validar presencia de lan_ip y lan_url en el contexto de la plantilla
        self.assertIn('lan_ip', res.context)
        self.assertIn('lan_url', res.context)
        self.assertTrue(res.context['lan_url'].startswith('http://'))
        self.assertIn(':8000', res.context['lan_url'])

        # 4. Validar que la plantilla HTML renderice el boton de acceso LAN y modal QR
        html = res.content.decode('utf-8')
        self.assertIn('lan-topbar-pill', html)
        self.assertIn('modal-lan-connect', html)
