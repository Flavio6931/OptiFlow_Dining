"""Utilidades de autorización por rol, contexto común de plantillas y resolución de avisos."""
import json
import socket
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from rest_framework import status
from rest_framework.response import Response

from ..layout import get_layout
from ..models import AdminNotification, Profile, RouteConsultation, TableState, Zone

SUPERVISOR_ROLES = ('admin', 'capitan', 'gerente')


def role_for(user):
    """Determina el rol operativo activo del usuario autenticado."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    profile = Profile.objects.filter(user=user).first()
    return profile.role if profile else 'mesero'


def role_required(*allowed):
    """Decorador para restringir el acceso a vistas HTML según el rol del usuario."""
    def decorator(func):
        @login_required
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            if role_for(request.user) not in set(allowed) | {'admin'}:
                return HttpResponseForbidden('No tienes permisos para acceder a esta función.')
            return func(request, *args, **kwargs)
        return wrapped
    return decorator


def drf_role_required(*allowed):
    """Decorador para vistas DRF que valida autenticación y permisos por rol."""
    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'Autenticación requerida para acceder a este recurso.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if role_for(request.user) not in set(allowed) | {'admin'}:
                return Response(
                    {'error': 'No tienes permisos para acceder a esta función.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return func(request, *args, **kwargs)
        return wrapped
    return decorator


def notifications_queryset_for(user):
    """Retorna el queryset de avisos dirigidos al supervisor actual o globales de administración."""
    return AdminNotification.objects.filter(Q(recipient=user) | Q(recipient__isnull=True))


def resolve_lan_ip() -> str:
    """Obtiene la IP privada Wi-Fi/LAN prioritaria del host para acceso móvil directo."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('10.255.255.255', 1))
            primary_ip = sock.getsockname()[0]
            if primary_ip and not primary_ip.startswith('127.') and not primary_ip.startswith('192.168.56.'):
                return primary_ip
    except OSError:
        pass
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
        candidates = [ip for ip in ips if not ip.startswith('127.') and not ip.startswith('192.168.56.')]
        return candidates[0] if candidates else (ips[0] if ips else '127.0.0.1')
    except OSError:
        return '127.0.0.1'


def page_context(request, page_title: str, active: str) -> dict:
    """Construye el contexto transversal compartido por todas las plantillas operativas."""
    user = request.user
    full_name = user.get_full_name() or user.username
    layout = get_layout()
    tables_state = list(TableState.objects.order_by('code'))
    states_dict = {t.code: t.state for t in tables_state}
    user_role = role_for(user)

    unread_notifications_count = 0
    notifications = []
    waiter_pending_assigned_count = 0

    if user.is_authenticated:
        if user_role in SUPERVISOR_ROLES:
            qs = notifications_queryset_for(user).filter(read=False)
            unread_notifications_count = qs.count()
            notifications = list(qs[:5])
        elif user_role == 'mesero':
            waiter_pending_assigned_count = RouteConsultation.objects.filter(
                assigned_waiter=user,
                completed=False,
            ).count()

    lan_ip = resolve_lan_ip()
    return {
        'page_title': page_title,
        'active': active,
        'role': user_role,
        'display_name': full_name,
        'layout': layout,
        'layout_json': json.dumps(layout, ensure_ascii=False),
        'zones': list(Zone.objects.order_by('code')),
        'tables_state': tables_state,
        'tables_map_json': json.dumps(states_dict, ensure_ascii=False),
        'unread_notifications_count': unread_notifications_count,
        'notifications': notifications,
        'waiter_pending_assigned_count': waiter_pending_assigned_count,
        'lan_ip': lan_ip,
        'lan_url': f'http://{lan_ip}:8000/login/',
    }

