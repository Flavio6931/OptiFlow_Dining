"""Análisis de fotos con OpenCV y su evidencia."""
import base64
import json
import os
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from optiflow import urls

from ..models import Profile, VisionAnalysis, Zone
from ..services import ServiceUnavailable, latest_vision_path
from .base import NO_STORAGE, OperationalTestCase


class VisionTests(OperationalTestCase):
    """Análisis de fotos con OpenCV y su evidencia."""

    @patch('core.views.optional_upload_s3', return_value=NO_STORAGE)
    @patch('core.views.analyze_image')
    def test_vision_pipeline_records_metadata(self, mocked_analyze, _mocked_s3):
        """Verifica la respuesta del endpoint DRF de visión con mock de OpenCV (Gerente/Admin)."""
        self.client.force_login(self.manager)
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

    @patch('core.views.optional_upload_s3', return_value=NO_STORAGE)
    @patch('core.views.analyze_image')
    def test_vision_propagates_to_zone_and_dijkstra(self, mocked_analyze, _mocked_s3):
        """Verifica que OpenCV propague la densidad detectada a los niveles de zona y a Dijkstra."""
        self.client.force_login(self.manager)
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


class VisionLiveTests(TestCase):
    """Detección en vivo de la cámara: reenvía el fotograma y no guarda nada."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username='gerente_live', password='Segura-12345-Live')
        Profile.objects.create(user=cls.manager, role='gerente')
        cls.waiter = User.objects.create_user(username='mesero_live', password='Segura-12345-Live')
        Profile.objects.create(user=cls.waiter, role='mesero')

    def _post(self, data=b'jpeg', content_type='image/jpeg'):
        frame = SimpleUploadedFile('frame.jpg', data, content_type=content_type)
        return self.client.post(reverse('api_vision_live'), {'file': frame})

    @patch('core.views.optional_upload_s3')
    @patch('core.views.detect_live_frame', return_value=(200, {
        'people_count': 2, 'zone_counts': {'A': 1, 'B': 1, 'C': 0},
        'boxes': [[0.1, 0.2, 0.1, 0.3, 0.9], [0.5, 0.2, 0.1, 0.3, 0.8]],
    }))
    def test_manager_gets_boxes_and_nothing_is_stored(self, mocked_detect, mocked_s3):
        self.client.force_login(self.manager)
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['people_count'], 2)
        self.assertEqual(len(response.json()['boxes']), 2)
        mocked_detect.assert_called_once()
        mocked_s3.assert_not_called()
        self.assertEqual(VisionAnalysis.objects.count(), 0)

    def test_waiter_cannot_use_live_detection(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self._post().status_code, 403)

    def test_rejects_missing_wrong_type_and_oversized_frames(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse('api_vision_live'), {}).status_code, 400)
        self.assertEqual(self._post(content_type='text/plain').status_code, 400)
        self.assertEqual(self._post(data=b'x' * (1024 * 1024 + 1)).status_code, 413)

    @patch('core.views.detect_live_frame', side_effect=ServiceUnavailable('caído'))
    def test_service_down_returns_503(self, _mocked):
        self.client.force_login(self.manager)
        self.assertEqual(self._post().status_code, 503)


class LatestVisionEvidenceTests(TestCase):
    """La foto analizada llega a todas las cuentas; sin análisis no se muestra ninguna imagen."""

    PHOTO = b'foto-analizada-por-opencv-' * 4

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.tmp.name)
        media_override.enable()
        self.addCleanup(media_override.disable)
        route = next(p for p in urls.urlpatterns if 'media' in str(p.pattern))
        serve_patch = patch.dict(route.default_args, {'document_root': self.tmp.name})
        serve_patch.start()
        self.addCleanup(serve_patch.stop)

    def _user(self, name, role):
        user = User.objects.create_user(name, password='x')
        Profile.objects.update_or_create(user=user, defaults={'role': role})
        return user

    def _analyze(self, manager, photo=None):
        encoded = base64.b64encode(photo or self.PHOTO).decode()
        result = {
            'people_count': 4,
            'zone_counts': {'A': 0, 'B': 1, 'C': 3},
            'annotated_image': f'data:image/jpeg;base64,{encoded}',
        }
        upload = SimpleUploadedFile('salon.jpg', b'x', content_type='image/jpeg')
        self.client.force_login(manager)
        with patch('core.views.analyze_image', return_value=(200, result)), \
                patch('core.views.optional_upload_s3', return_value=NO_STORAGE):
            response = self.client.post(reverse('api_vision'), {'file': upload})
        self.assertEqual(response.status_code, 200)

    def test_without_analysis_there_is_no_image_or_invented_data(self):
        self.client.force_login(self._user('mesero_v', 'mesero'))
        data = self.client.get(reverse('api_latest_vision')).json()
        self.assertEqual(data['image_url'], '')
        self.assertEqual(data['people_count'], 0)
        self.assertEqual(data['zone_counts'], {})

    def test_analyzed_photo_reaches_every_role(self):
        self._analyze(self._user('gerente_v', 'gerente'))
        for name, role in (('mesero_v', 'mesero'), ('capitan_v', 'capitan'), ('gerente_v2', 'gerente')):
            self.client.force_login(self._user(name, role))
            data = self.client.get(reverse('api_latest_vision')).json()
            self.assertEqual(data['people_count'], 4)
            photo = self.client.get(data['image_url'])
            self.assertEqual(photo.status_code, 200, role)
            self.assertEqual(b''.join(photo.streaming_content), self.PHOTO, role)

    def test_routes_page_embeds_the_latest_photo(self):
        self._analyze(self._user('gerente_v', 'gerente'))
        self.client.force_login(self._user('mesero_v', 'mesero'))
        html = self.client.get(reverse('routes')).content.decode()
        self.assertIn('/media/vision/latest_capture.jpg?v=', html)

    def test_new_analysis_replaces_photo_and_changes_url(self):
        manager = self._user('gerente_v', 'gerente')
        self._analyze(manager)
        os.utime(latest_vision_path(), ns=(1, 1))
        first = self.client.get(reverse('api_latest_vision')).json()['image_url']
        second_photo = b'otra-foto-del-salon-' * 6
        self._analyze(manager, second_photo)
        second = self.client.get(reverse('api_latest_vision')).json()['image_url']
        self.assertNotEqual(first, second)
        self.assertEqual(latest_vision_path().read_bytes(), second_photo)

    def test_anonymous_user_cannot_open_photo(self):
        self._analyze(self._user('gerente_v', 'gerente'))
        url = self.client.get(reverse('api_latest_vision')).json()['image_url']
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
