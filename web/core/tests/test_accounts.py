"""Registro, inicio de sesión, permisos, perfil y avisos."""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse

from ..models import Profile
from .base import S3_DISABLED, OperationalTestCase


class AccountsTests(OperationalTestCase):
    """Registro, inicio de sesión, permisos, perfil y avisos."""

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
        """Verifica la restricción de páginas HTML según la matriz estricta de roles operativos."""
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('routes')).status_code, 200)
        self.assertEqual(self.client.get(reverse('saturation')).status_code, 403)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 403)

        self.client.force_login(self.captain)
        # Jefe de meseros (Capitán): Bloqueado de visión y saturación
        self.assertEqual(self.client.get(reverse('vision')).status_code, 403)
        self.assertEqual(self.client.get(reverse('saturation')).status_code, 403)
        # Acceso permitido a rutas, layout y analítica
        self.assertEqual(self.client.get(reverse('routes')).status_code, 200)
        self.assertEqual(self.client.get(reverse('layout')).status_code, 200)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 200)

        self.client.force_login(self.manager)
        # Gerente general: Acceso completo a todas las áreas operativas
        self.assertEqual(self.client.get(reverse('routes')).status_code, 200)
        self.assertEqual(self.client.get(reverse('saturation')).status_code, 200)
        self.assertEqual(self.client.get(reverse('analytics')).status_code, 200)
        self.assertEqual(self.client.get(reverse('layout')).status_code, 200)
        with patch('core.views.pages.s3_connection_status', return_value=S3_DISABLED):
            self.assertEqual(self.client.get(reverse('vision')).status_code, 200)

    def test_registration_creates_admin_notification(self):
        """Verifica que el registro de un nuevo mesero genere automáticamente una notificación para admin."""
        from ..models import AdminNotification
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

    def test_profile_view_and_notification_read_api(self):
        """Verifica la carga del perfil y el marcado reactivo de notificaciones."""
        from ..models import AdminNotification
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

    def test_manager_permissions_matrix(self):
        """Verifica que el Gerente General tenga acceso a plano, visión y saturación, pero NO a mutar roles."""
        self.client.force_login(self.manager)

        # 1. Gerente puede actualizar saturación de zonas
        sat_res = self.client.post(
            reverse('api_update_zone', args=['A']),
            data=json.dumps({'level': 'moderada', 'dwell_minutes': 2.8}),
            content_type='application/json',
        )
        self.assertEqual(sat_res.status_code, 200)

        # 2. Gerente NO puede cambiar roles de empleados -> 403 Forbidden
        role_res = self.client.post(
            reverse('api_update_user_role', args=[self.waiter.id]),
            data=json.dumps({'role': 'capitan'}),
            content_type='application/json',
        )
        self.assertEqual(role_res.status_code, 403)
