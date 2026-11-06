"""Comando de gestión Django para inicializar mesas, zonas y usuarios demo."""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Profile, TableState, Zone


class Command(BaseCommand):
    """Comando para sembrar datos iniciales de zonas, mesas y cuentas demo."""
    help = 'Crea zonas/mesas iniciales y, solo si se solicita, usuarios de prueba.'

    def handle(self, *args, **options):
        initial_zones = [
            ('A', 'normal', 0.8),
            ('B', 'moderada', 2.4),
            ('C', 'critica', 4.6),
        ]
        for code, level, dwell in initial_zones:
            Zone.objects.get_or_create(
                code=code,
                defaults={'level': level, 'dwell_minutes': dwell},
            )

        for n in range(1, 9):
            TableState.objects.get_or_create(code=f'mesa{n:02d}')

        self._ensure_admin()

        if os.environ.get('ENABLE_DEMO_USERS', '0') == '1':
            password = os.environ.get('DEMO_PASSWORD', '')
            if len(password) < 12 or password == 'REEMPLAZAR_POR_CONTRASENA_SEGURA':
                self.stderr.write(
                    'No se crearon usuarios demo: DEMO_PASSWORD debe tener al menos 12 caracteres.'
                )
                return

            demo_roles = [
                ('mesero_demo', 'mesero'),
                ('capitan_demo', 'capitan'),
                ('gerente_demo', 'gerente'),
            ]
            for name, role in demo_roles:
                user, created = User.objects.get_or_create(
                    username=name,
                    defaults={'email': f'{name}@example.invalid'},
                )
                if created:
                    user.set_password(password)
                    user.save()
                Profile.objects.get_or_create(user=user, defaults={'role': role})

        self.stdout.write(self.style.SUCCESS('OptiFlow preparado: mesas y zonas inicializadas.'))

    def _ensure_admin(self):
        """Crea el superusuario inicial solo si se define ADMIN_PASSWORD; nunca cambia uno existente.

        Este comando se ejecuta en cada arranque, así que jamás debe fijar
        ni restablecer contraseñas: si el administrador ya existe, se respeta su clave.
        """
        username = os.environ.get('ADMIN_USERNAME', 'admin').strip() or 'admin'
        existing = User.objects.filter(username=username).first()
        if existing:
            if existing.check_password('1234'):
                self.stderr.write(self.style.WARNING(
                    f"ATENCIÓN: el usuario '{username}' aún usa la contraseña insegura '1234'. "
                    f'Cámbiala con: python manage.py changepassword {username}'
                ))
            return

        password = os.environ.get('ADMIN_PASSWORD', '')
        if not password:
            if not User.objects.filter(is_superuser=True).exists():
                self.stdout.write(
                    'No hay administrador. Crea uno con "python manage.py createsuperuser" '
                    'o define ADMIN_PASSWORD (mín. 12 caracteres) en .env y reinicia.'
                )
            return
        if len(password) < 12 or password == 'REEMPLAZAR_POR_CONTRASENA_SEGURA':
            self.stderr.write('No se creó el administrador: ADMIN_PASSWORD debe tener al menos 12 caracteres.')
            return

        User.objects.create_superuser(
            username=username,
            email=os.environ.get('ADMIN_EMAIL', 'admin@optiflow.local'),
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Administrador '{username}' creado desde ADMIN_PASSWORD."))

