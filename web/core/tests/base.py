"""Datos compartidos por las pruebas."""
from django.contrib.auth.models import User
from django.test import TestCase

from ..models import Profile, TableState, Zone

NO_STORAGE = {'storage': 'none', 'key': '', 'bucket': '', 'error': ''}
S3_DISABLED = {'state': 'disabled', 'icon': '⚪', 'label': 'No configurado', 'bucket': '', 'region': '', 'reason': ''}


class OperationalTestCase(TestCase):
    """Usuarios con cada rol y catálogo inicial de mesas y zonas."""

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
