"""Datos iniciales, fotos protegidas y almacenamiento en S3."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from optiflow import urls

from ..models import Profile, TableState, VisionAnalysis, Zone
from .base import S3_DISABLED


class SecurityHardeningTests(TestCase):
    """Pruebas de regresión: admin por defecto, XSS en JSON embebido y estado veraz de AWS S3."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username='gerente_sec', password='Segura-12345-Manager')
        Profile.objects.create(user=cls.manager, role='gerente')
        for code in 'ABC':
            Zone.objects.create(code=code)

    # --- 1. Sin administrador con contraseña fija ---------------------------------------------
    def _seed(self, env):
        from io import StringIO
        from django.core.management import call_command

        with patch.dict('os.environ', env):
            call_command('seed_demo', stdout=StringIO(), stderr=StringIO())

    def test_seed_demo_does_not_create_default_admin(self):
        """seed_demo no debe crear 'admin' si no se define ADMIN_PASSWORD."""
        self._seed({'ADMIN_PASSWORD': ''})
        self.assertFalse(User.objects.filter(username='admin').exists())

    def test_seed_demo_never_resets_existing_admin_password(self):
        """Cada arranque ejecuta seed_demo: no debe sobrescribir la clave de un admin existente."""
        admin = User.objects.create_superuser('admin', 'a@b.c', 'Mi-Clave-Propia-2026')
        self._seed({'ADMIN_PASSWORD': 'Otra-Clave-Distinta-99'})
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('Mi-Clave-Propia-2026'))

    def test_seed_demo_creates_admin_from_env(self):
        """Con ADMIN_PASSWORD robusta se crea el superusuario inicial."""
        self._seed({'ADMIN_PASSWORD': 'Clave-Inicial-Segura-1'})
        admin = User.objects.get(username='admin')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('Clave-Inicial-Segura-1'))

    def test_seed_demo_rejects_short_admin_password(self):
        self._seed({'ADMIN_PASSWORD': '1234'})
        self.assertFalse(User.objects.filter(username='admin').exists())

    def test_login_form_not_prefilled_with_admin(self):
        response = self.client.get(reverse('login'))
        self.assertNotContains(response, 'value="admin"')

    # --- 2. XSS en datos JSON embebidos -------------------------------------------------------
    def test_create_table_rejects_markup_in_code(self):
        from ..layout import LAYOUT_PATH

        original = LAYOUT_PATH.read_text(encoding='utf-8')
        self.client.force_login(self.manager)
        try:
            response = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({'code': '</script><script>alert(1)</script>', 'zone': 'A'}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(LAYOUT_PATH.read_text(encoding='utf-8'), original)
        finally:
            LAYOUT_PATH.write_text(original, encoding='utf-8')

    def test_table_state_json_is_escaped_in_pages(self):
        """Aunque llegue un código malicioso a la BD, no debe poder cerrar el <script> JSON."""
        payload = '</script><script>alert(1)</script>'
        TableState.objects.create(code=payload)
        self.client.force_login(self.manager)
        for name in ('routes', 'layout'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(payload, response.content.decode())

    # --- 4. Estado veraz de AWS S3 ------------------------------------------------------------
    def _upload(self, client_mock=None, bucket='bucket-prueba'):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        from ..services import optional_upload_s3

        tmp = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=Path(tmp), AWS_STORAGE_BUCKET_NAME=bucket, AWS_S3_BUCKET=bucket):
            with patch('core.services._get_s3_client', return_value=client_mock) as factory:
                return optional_upload_s3(b'img', 'foto.jpg', 'image/jpeg'), factory

    def test_s3_upload_success_reports_s3(self):
        from unittest.mock import MagicMock

        client = MagicMock()
        result, _ = self._upload(client)
        self.assertEqual(result['storage'], 's3')
        self.assertTrue(result['key'].startswith('optiflow/analisis/'))
        client.put_object.assert_called_once()

    def test_s3_failure_falls_back_to_local_and_says_so(self):
        from unittest.mock import MagicMock
        from botocore.exceptions import NoCredentialsError

        client = MagicMock()
        client.put_object.side_effect = NoCredentialsError()
        result, _ = self._upload(client)
        self.assertEqual(result['storage'], 'local')
        self.assertEqual(result['error'], 'NoCredentialsError')
        self.assertTrue(result['key'].startswith('local:'))

    def test_no_bucket_means_local_without_calling_aws(self):
        result, factory = self._upload(bucket='')
        factory.assert_not_called()
        self.assertEqual(result['storage'], 'local')
        self.assertEqual(result['error'], '')

    @patch('core.views.analyze_image', return_value=(200, {
        'people_count': 0, 'zone_counts': {'A': 0, 'B': 0, 'C': 0}, 'annotated_image': '',
    }))
    @patch('core.views.optional_upload_s3', return_value={
        'storage': 'local', 'key': 'local:optiflow/analisis/x.jpg', 'bucket': 'mi-bucket',
        'error': 'AccessDenied',
    })
    def test_vision_api_does_not_claim_s3_when_stored_locally(self, _s3, _cv):
        self.client.force_login(self.manager)
        photo = SimpleUploadedFile('salon.jpg', b'fake', content_type='image/jpeg')
        data = self.client.post(reverse('api_vision'), {'file': photo}).json()
        self.assertFalse(data['aws_saved'])
        self.assertNotIn('Guardado en AWS S3', data['s3_status'])
        self.assertIn('AccessDenied', data['aws_warning'])
        self.assertEqual(VisionAnalysis.objects.get().s3_key, 'local:optiflow/analisis/x.jpg')
        with patch('core.views.pages.s3_connection_status', return_value=S3_DISABLED):
            page = self.client.get(reverse('vision'))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'Ver en S3')

    def _s3_check(self, client_mock=None, bucket='bucket-prueba', refresh=True):
        from django.core.cache import cache
        from django.test import override_settings
        from ..services import s3_connection_status

        cache.clear()
        with override_settings(AWS_STORAGE_BUCKET_NAME=bucket, AWS_S3_BUCKET=bucket):
            with patch('core.services._get_s3_client', return_value=client_mock) as factory:
                return s3_connection_status(refresh=refresh), factory

    def test_s3_status_without_bucket_is_disabled_and_skips_aws(self):
        status, factory = self._s3_check(bucket='')
        self.assertEqual(status['state'], 'disabled')
        factory.assert_not_called()

    def test_s3_status_connected_only_after_real_write(self):
        from unittest.mock import MagicMock
        from ..services import S3_HEALTHCHECK_KEY

        client = MagicMock()
        status, _ = self._s3_check(client)
        self.assertEqual(status['state'], 'connected')
        self.assertEqual(client.put_object.call_args.kwargs['Key'], S3_HEALTHCHECK_KEY)

    def test_s3_status_reports_missing_credentials(self):
        """Bucket configurado sin credenciales: no debe decir 'Conectado' (caso real reportado)."""
        from unittest.mock import MagicMock
        from botocore.exceptions import NoCredentialsError

        client = MagicMock()
        client.put_object.side_effect = NoCredentialsError()
        status, _ = self._s3_check(client)
        self.assertEqual(status['state'], 'no_credentials')
        self.assertEqual(status['reason'], 'NoCredentialsError')

    def test_s3_status_reports_access_denied_and_missing_bucket(self):
        from unittest.mock import MagicMock
        from botocore.exceptions import ClientError

        for code, state in (('AccessDenied', 'denied'), ('NoSuchBucket', 'not_found')):
            client = MagicMock()
            client.put_object.side_effect = ClientError({'Error': {'Code': code}}, 'PutObject')
            status, _ = self._s3_check(client)
            self.assertEqual(status['state'], state)

    def test_s3_status_is_cached_until_refresh(self):
        from unittest.mock import MagicMock

        client = MagicMock()
        self._s3_check(client)
        with patch('core.services._get_s3_client') as factory:
            from django.test import override_settings
            from ..services import s3_connection_status

            with override_settings(AWS_STORAGE_BUCKET_NAME='bucket-prueba', AWS_S3_BUCKET='bucket-prueba'):
                self.assertEqual(s3_connection_status()['state'], 'connected')
            factory.assert_not_called()

    def test_vision_page_does_not_claim_connected_without_credentials(self):
        self.client.force_login(self.manager)
        status = {**S3_DISABLED, 'state': 'no_credentials', 'icon': '🔴', 'label': 'Sin credenciales AWS',
                  'bucket': 'mi-bucket', 'reason': 'NoCredentialsError'}
        with patch('core.views.pages.s3_connection_status', return_value=status):
            page = self.client.get(reverse('vision'))
        self.assertContains(page, 'Sin credenciales AWS')
        self.assertNotContains(page, 'Conectado')
        self.assertContains(page, 'solo en este servidor')


class LocalMediaAccessTests(TestCase):
    """Las fotos guardadas en el servidor se abren con sesión iniciada, también sin DEBUG."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / 'foto.jpg').write_bytes(b'imagen')
        patcher = patch.dict(
            next(p for p in urls.urlpatterns if 'media' in str(p.pattern)).default_args,
            {'document_root': self.tmp.name},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_anonymous_user_is_redirected_to_login(self):
        res = self.client.get('/media/foto.jpg')
        self.assertEqual(res.status_code, 302)
        self.assertIn('login', res['Location'])

    def test_logged_in_user_can_open_photo(self):
        self.client.force_login(User.objects.create_user('foto_user', password='x'))
        res = self.client.get('/media/foto.jpg')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b''.join(res.streaming_content), b'imagen')

    def test_path_traversal_is_rejected(self):
        self.client.force_login(User.objects.create_user('foto_user2', password='x'))
        self.assertEqual(self.client.get('/media/../settings.py').status_code, 400)
