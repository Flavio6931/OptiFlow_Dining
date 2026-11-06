"""Datos que muestran las pantallas y el acceso móvil."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Profile, RouteConsultation, Zone
from ..views.helpers import zones_with_details
from .base import OperationalTestCase


class MobileAccessTests(OperationalTestCase):
    """Datos que muestran las pantallas y el acceso móvil."""

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
        self.assertIn('.nip.io:8000/login/', res.context['lan_url'])
        self.assertIn(res.context['lan_ip'], res.context['lan_direct_url'])

        # 4. Validar que la plantilla HTML renderice el boton de acceso LAN y modal QR
        html = res.content.decode('utf-8')
        self.assertIn('lan-topbar-pill', html)
        self.assertIn('modal-lan-connect', html)


class OperationalScreensTests(TestCase):
    """Los paneles cuentan solo el día actual y muestran datos legibles."""

    def setUp(self):
        Zone.objects.create(code='A', level='normal', dwell_minutes=0.8)
        self.manager = User.objects.create_user('gerente_ops', password='x')
        Profile.objects.update_or_create(user=self.manager, defaults={'role': 'gerente'})
        self.client.force_login(self.manager)

    def _route(self, days_ago=0, **fields):
        route = RouteConsultation.objects.create(
            user=self.manager, origin='cocina', destination='mesa08', distance=5, **fields
        )
        if days_ago:
            RouteConsultation.objects.filter(pk=route.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return route

    def test_dashboard_counts_only_todays_routes(self):
        self._route(completed=True)
        self._route()
        self._route(days_ago=3, completed=True)
        context = self.client.get(reverse('dashboard')).context
        self.assertEqual(context['total_routes'], 2)
        self.assertEqual(context['completed_routes'], 1)
        self.assertEqual(context['open_routes'], 1)

    def test_analytics_counts_only_todays_routes(self):
        self._route(recalculated=True)
        self._route(days_ago=2)
        context = self.client.get(reverse('analytics')).context
        self.assertEqual(context['total_routes'], 1)
        self.assertEqual(context['recalculated'], 1)
        self.assertEqual(context['direct_routes'], 0)

    def test_route_labels_are_readable(self):
        self.assertEqual(RouteConsultation(origin='cocina', destination='mesa08').destination_label, 'Mesa 08')
        self.assertEqual(RouteConsultation(origin='cocina', destination='mesa_01_02').destination_label, 'Mesa 01+02')
        self.assertEqual(RouteConsultation(origin='cocina', destination='mesa08').origin_label, 'Cocina')

    def test_zone_details_use_current_layout_tables(self):
        layout = {'tables': [
            {'id': 'mesa01', 'label': 'Mesa 01', 'zone': 'A'},
            {'id': 'mesa_05_06', 'label': 'Mesa 05+06 (Grupo)', 'zone': 'A'},
            {'id': 'mesa02', 'label': 'Mesa 02', 'zone': 'B'},
        ]}
        zone = zones_with_details(layout)[0]
        self.assertEqual(zone.display_name, 'Salón Jardín')
        self.assertEqual(zone.tables_label, 'Mesas 01, 05+06')
        self.assertEqual(zone.saturation_pct, 16)

    def test_saturation_shows_minutes_with_one_decimal(self):
        html = self.client.get(reverse('saturation')).content.decode()
        self.assertIn('value="0.8"', html)
        self.assertNotIn('0.800000', html)
