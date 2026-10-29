"""Páginas Django y APIs REST protegidas con sesión, CSRF y permisos por rol."""
import json
import logging
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .forms import LoginForm, RegisterForm
from .layout import get_layout
from .models import (
    AdminNotification,
    Profile,
    RouteConsultation,
    TableState,
    VisionAnalysis,
    Zone,
)
from .serializers import (
    RouteConsultationSerializer,
    RouteRequestSerializer,
    TableStateSerializer,
    TableStateUpdateSerializer,
    VisionAnalysisSerializer,
    VisionUploadSerializer,
    ZoneSerializer,
    ZoneUpdateSerializer,
)
from .services import (
    ServiceUnavailable,
    analyze_image,
    calculate_route,
    optional_upload_s3,
)

logger = logging.getLogger(__name__)


def role_for(user):
    """Determina el rol operativo del usuario actual."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    profile = Profile.objects.filter(user=user).first()
    return profile.role if profile else 'mesero'


def role_required(*allowed):
    """Decorador para restringir el acceso a vistas según el rol del usuario."""
    def decorator(func):
        @login_required
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            if role_for(request.user) not in set(allowed) | {'admin'}:
                return HttpResponseForbidden('No tienes permisos para acceder a esta función.')
            return func(request, *args, **kwargs)
        return wrapped
    return decorator


def page_context(request, page_title, active):
    """Genera el diccionario de contexto común para las plantillas."""
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
        if user_role in ('admin', 'capitan'):
            unread_notifications_count = AdminNotification.objects.filter(read=False).count()
            notifications = list(AdminNotification.objects.filter(read=False)[:5])
        elif user_role == 'mesero':
            waiter_pending_assigned_count = RouteConsultation.objects.filter(
                assigned_waiter=user,
                completed=False,
            ).count()

    lan_ip = '127.0.0.1'
    try:
        import socket
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
        lan_candidates = [ip for ip in ips if not ip.startswith('127.') and not ip.startswith('192.168.56.')]
        lan_ip = lan_candidates[0] if lan_candidates else (ips[0] if ips else '127.0.0.1')
    except Exception:
        pass
    lan_url = f"http://{lan_ip}:8000"

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
        'lan_url': lan_url,
    }


def landing(request):
    """Página pública de bienvenida."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html', {'page_title': 'Bienvenido'})


def register_view(request):
    """Registro de nuevos usuarios meseros."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.create(user=user, role='mesero')
        login(request, user)
        messages.success(request, 'Tu cuenta se creó correctamente. Bienvenido a OptiFlow.')
        return redirect('dashboard')
    return render(request, 'register.html', {'form': form, 'page_title': 'Crear cuenta'})


def login_view(request):
    """Inicio de sesión con soporte para redirección segura."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            nxt = request.POST.get('next') or request.GET.get('next')
            if nxt and nxt.startswith('/') and not nxt.startswith('//'):
                return redirect(nxt)
            return redirect('dashboard')
    else:
        form = LoginForm(request, initial={'username': 'admin'})
    return render(
        request,
        'login.html',
        {
            'form': form,
            'page_title': 'Iniciar sesión',
            'next': request.GET.get('next', ''),
        },
    )


@login_required
@require_POST
def logout_view(request):
    """Cierre de sesión de usuario."""
    logout(request)
    return redirect('landing')


@login_required
def dashboard(request):
    """Panel principal con métricas ejecutivas, operativas y estado en vivo del salón."""
    context = page_context(request, 'Panel principal', 'dashboard')
    routes = RouteConsultation.objects.count()
    recalculated = RouteConsultation.objects.filter(recalculated=True).count()
    congestion = Zone.objects.filter(level='critica').count()

    tables = list(TableState.objects.all())
    tables_total = len(tables)
    tables_available = sum(1 for t in tables if t.state == 'disponible')
    tables_active = sum(1 for t in tables if t.state == 'activa')
    tables_occupied = sum(1 for t in tables if t.state == 'ocupada')
    occupancy_pct = round((tables_occupied / tables_total * 100), 1) if tables_total > 0 else 0

    zones = list(Zone.objects.order_by('code'))
    zones_normal = sum(1 for z in zones if z.level == 'normal')
    for z in zones:
        # Calcular porcentaje visual de saturación respecto al umbral de 5.0 minutos
        z.saturation_pct = min(100, max(12, int((z.dwell_minutes / 5.0) * 100)))

    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()
    efficiency_rate = round(((routes - recalculated) / routes) * 100, 1) if routes > 0 else 100.0

    user_role = context['role']
    last_routes = list(RouteConsultation.objects.select_related('user', 'assigned_waiter').order_by('-created_at')[:8])
    assigned_to_me = []
    if user_role == 'mesero':
        assigned_to_me = list(RouteConsultation.objects.select_related('user', 'assigned_waiter').filter(
            assigned_waiter=request.user,
            completed=False,
        ).order_by('-created_at')[:6])

    context.update({
        'total_routes': routes,
        'recalculated': recalculated,
        'route_efficiency': efficiency_rate,
        'congestion_count': congestion,
        'zones_normal_count': zones_normal,
        'zones': zones,
        'tables_total': tables_total,
        'tables_available': tables_available,
        'tables_active': tables_active,
        'tables_occupied': tables_occupied,
        'occupancy_pct': occupancy_pct,
        'last_routes': last_routes,
        'assigned_to_me': assigned_to_me,
        'recent_vision': recent_vision,
        'recent_people_count': recent_vision.people_count if recent_vision else 0,
    })
    return render(request, 'dashboard.html', context)


@role_required('mesero', 'capitan', 'gerente')
def routes_view(request):
    """Vista de consulta interactiva de rutas."""
    context = page_context(request, 'Consultar rutas', 'routes')
    user_role = context['role']
    waiters = []
    assigned_to_me = []

    if user_role in ('capitan', 'gerente', 'admin'):
        waiters = list(User.objects.filter(
            Q(profile__role='mesero') | Q(is_superuser=False)
        ).exclude(id=request.user.id).order_by('first_name', 'username'))
        recent_routes = list(RouteConsultation.objects.select_related('user', 'assigned_waiter').order_by('-created_at')[:8])
    else:
        recent_routes = list(RouteConsultation.objects.select_related('user', 'assigned_waiter').filter(
            Q(user=request.user) | Q(assigned_waiter=request.user)
        ).order_by('-created_at')[:8])
        assigned_to_me = list(RouteConsultation.objects.select_related('user', 'assigned_waiter').filter(
            assigned_waiter=request.user,
            completed=False,
        ).order_by('-created_at'))

    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()
    latest_vision_payload = {
        'image_url': '/static/img/latest_vision_capture.jpg',
        'people_count': recent_vision.people_count if recent_vision else 1,
        'zone_counts': recent_vision.zone_counts if recent_vision else {'A': 0, 'B': 1, 'C': 0},
        'filename': recent_vision.filename if recent_vision else 'captura_salon.jpg',
        'created_at': recent_vision.created_at.strftime('%d/%m/%Y %H:%M') if recent_vision else '',
    }

    context.update({
        'waiters': waiters,
        'recent_routes': recent_routes,
        'assigned_to_me': assigned_to_me,
        'latest_vision_json': json.dumps(latest_vision_payload),
    })
    return render(request, 'routes.html', context)


@role_required('gerente')
def saturation_view(request):
    """Vista de monitoreo y ajuste de saturación de zonas."""
    context = page_context(request, 'Saturación del salón', 'saturation')
    context['critical_zones'] = Zone.objects.filter(level='critica', dwell_minutes__gt=4)
    return render(request, 'saturation.html', context)


@role_required('gerente', 'capitan')
def analytics_view(request):
    """Vista de analítica e indicadores avanzados para gerencia y capitanes."""
    context = page_context(request, 'Indicadores operativos', 'analytics')
    totals = RouteConsultation.objects.count()
    completed = RouteConsultation.objects.filter(completed=True).count()
    recalculated = RouteConsultation.objects.filter(recalculated=True).count()
    direct_routes = max(0, totals - recalculated)
    direct_pct = round((direct_routes / totals * 100), 1) if totals > 0 else 100.0
    completion_rate = round((completed / totals * 100), 1) if totals > 0 else 100.0

    # Desglose de tareas operativas
    entregas = RouteConsultation.objects.filter(task_type='entrega').count()
    retiros = RouteConsultation.objects.filter(task_type='retiro').count()

    # Métricas de distancia
    distance_agg = RouteConsultation.objects.aggregate(avg_dist=Avg('distance'), total_dist=Sum('distance'))
    avg_distance = round(distance_agg['avg_dist'] or 0, 1)
    total_distance = distance_agg['total_dist'] or 0

    # Telemetría de zonas
    zones = list(Zone.objects.order_by('code'))
    critical_count = sum(1 for z in zones if z.level == 'critica')
    zones_normal_count = sum(1 for z in zones if z.level == 'normal')
    avg_dwell = round(sum(z.dwell_minutes for z in zones) / len(zones), 1) if zones else 0.0
    for z in zones:
        z.saturation_pct = min(100, max(10, int((z.dwell_minutes / 5.0) * 100)))

    # Mesas y capacidad
    tables = list(TableState.objects.all())
    tables_total = len(tables)
    tables_available = sum(1 for t in tables if t.state == 'disponible')
    tables_occupied = sum(1 for t in tables if t.state == 'ocupada')
    tables_active = sum(1 for t in tables if t.state == 'activa')
    occupancy_pct = round((tables_occupied / tables_total * 100), 1) if tables_total > 0 else 0

    # Visión computacional OpenCV
    vision_count = VisionAnalysis.objects.count()
    vision_agg = VisionAnalysis.objects.aggregate(total_people=Sum('people_count'))
    total_people_detected = vision_agg['total_people'] or 0
    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()

    # Índice de eficiencia de servicio global (0 a 100)
    base_score = 96.0
    if critical_count > 0:
        base_score -= (critical_count * 14.0)
    if totals > 0:
        optiflow_score = min(100.0, max(50.0, round(base_score - 10.0 + (direct_routes / totals) * 10.0, 1)))
    else:
        optiflow_score = round(max(60.0, base_score), 1)

    context.update({
        'total_routes': totals,
        'completed': completed,
        'recalculated': recalculated,
        'direct_routes': direct_routes,
        'direct_pct': direct_pct,
        'completion_rate': completion_rate,
        'critical_count': critical_count,
        'zones_normal_count': zones_normal_count,
        'zones': zones,
        'avg_dwell': avg_dwell,
        'entregas_count': entregas,
        'retiros_count': retiros,
        'avg_distance': avg_distance,
        'total_distance': total_distance,
        'tables_total': tables_total,
        'tables_available': tables_available,
        'tables_occupied': tables_occupied,
        'tables_active': tables_active,
        'occupancy_pct': occupancy_pct,
        'vision_count': vision_count,
        'total_people_detected': total_people_detected,
        'recent_vision': recent_vision,
        'optiflow_score': optiflow_score,
        'last_routes': RouteConsultation.objects.select_related('user').order_by('-created_at')[:8],
    })
    return render(request, 'analytics.html', context)


@role_required('capitan', 'gerente')
def layout_view(request):
    """Vista de edición de estado de mesas y distribución espacial del salón."""
    context = page_context(request, 'Plano y mesas', 'layout')
    layout = context.get('layout') or {}
    tables_state = context.get('tables_state') or []

    # Diccionario rápido de estados actuales en base de datos
    states_dict = {t.code: t.state for t in tables_state}

    # Mesas combinadas con datos topológicos de salon.json
    enriched_tables = []
    total_capacity = 0
    available_count = 0
    active_count = 0
    occupied_count = 0

    for t in layout.get('tables', []):
        t_id = t['id']
        state = states_dict.get(t_id, 'disponible')
        seats = int(t.get('seats', 4))
        total_capacity += seats

        if state == 'disponible':
            available_count += 1
        elif state == 'activa':
            active_count += 1
        elif state == 'ocupada':
            occupied_count += 1

        enriched_tables.append({
            'code': t_id,
            'label': t.get('label', f"Mesa {t_id[-2:]}"),
            'state': state,
            'seats': seats,
            'zone': t.get('zone', 'A'),
            'node': t.get('node', '0,0'),
            'is_unified': bool(t.get('original_tables') or t.get('unified_from')),
        })

    total_tables = len(enriched_tables)
    occupancy_pct = round(((active_count + occupied_count) / max(total_tables, 1)) * 100)

    context.update({
        'enriched_tables': enriched_tables,
        'tables_map_json': json.dumps(states_dict, ensure_ascii=False),
        'total_capacity': total_capacity,
        'available_count': available_count,
        'active_count': active_count,
        'occupied_count': occupied_count,
        'occupancy_pct': occupancy_pct,
    })
    return render(request, 'layout.html', context)


@role_required('gerente')
def vision_view(request):
    """Vista de análisis fotográfico de ocupación con OpenCV."""
    from .services import get_s3_presigned_url

    context = page_context(request, 'Análisis con OpenCV', 'vision')
    history = list(VisionAnalysis.objects.order_by('-created_at')[:6])
    for item in history:
        item.presigned_url = get_s3_presigned_url(item.s3_key) if item.s3_key else ''
    context['analysis_history'] = history
    context['s3_enabled'] = bool(settings.AWS_S3_BUCKET)
    context['s3_bucket'] = settings.AWS_S3_BUCKET or ''
    context['aws_region'] = settings.AWS_REGION or ''
    return render(request, 'vision.html', context)


def drf_role_required(*allowed):
    """Decorador para vistas DRF que valida permisos de rol y autenticación."""
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


@api_view(['POST'])
@drf_role_required('mesero', 'capitan', 'gerente')
def api_route(request):
    """API DRF para calcular la ruta óptima evitando congestión si se solicita."""
    serializer = RouteRequestSerializer(data=request.data)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        return Response(
            {'error': err_msg, 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    origin = data['origin']
    destination = data['destination']
    task_type = data['task_type']
    avoid = data['avoid_congestion']

    zone_levels = {z.code: z.level for z in Zone.objects.all()}
    try:
        http_code, result = calculate_route({
            'origin': origin,
            'destination': destination,
            'task_type': task_type,
            'avoid_congestion': avoid,
            'zone_levels': zone_levels,
        })
    except ServiceUnavailable as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if http_code != 200:
        return Response(
            {'error': result.get('detail', 'No existe una ruta disponible')},
            status=http_code,
        )

    assigned_waiter_id = data.get('assigned_waiter')
    assigned_waiter = None
    if assigned_waiter_id and role_for(request.user) in ('admin', 'capitan'):
        assigned_waiter = User.objects.filter(id=assigned_waiter_id).first()

    # Si se asigna la ruta a un mesero y la trayectoria inicial presenta congestión,
    # se recalcula automáticamente la trayectoria óptima y segura vía Dijkstra para esquivar cuellos de botella (Req 3 & 8).
    auto_safe_reroute = False
    if assigned_waiter and result.get('congested') and not avoid:
        try:
            http_code_safe, safe_result = calculate_route({
                'origin': origin,
                'destination': destination,
                'task_type': task_type,
                'avoid_congestion': True,
                'zone_levels': zone_levels,
            })
            if http_code_safe == 200:
                result = safe_result
                avoid = True
                auto_safe_reroute = True
        except ServiceUnavailable:
            logger.warning('No se pudo calcular desvío seguro automático al asignar ruta a mesero.')

    record = RouteConsultation.objects.create(
        user=request.user,
        assigned_waiter=assigned_waiter,
        origin=origin,
        destination=destination,
        task_type=task_type,
        path=result['path'],
        distance=result['distance'],
        recalculated=avoid,
        congested=result['congested'],
    )
    result['route_id'] = record.id
    result['created_at'] = record.created_at.strftime('%d/%m/%Y %H:%M')
    result['task_type_display'] = record.get_task_type_display()
    result['destination_label'] = destination.upper()
    result['recalculated'] = avoid
    result['auto_safe_reroute'] = auto_safe_reroute
    result['assigned_waiter_name'] = (
        assigned_waiter.get_full_name() or assigned_waiter.username
        if assigned_waiter else ''
    )
    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@drf_role_required('mesero', 'capitan', 'gerente')
def api_complete(request, pk):
    """API DRF para marcar una consulta de ruta como finalizada."""
    if role_for(request.user) in ('admin', 'capitan', 'gerente'):
        record = get_object_or_404(RouteConsultation, pk=pk)
    else:
        record = get_object_or_404(
            RouteConsultation,
            Q(pk=pk) & (Q(user=request.user) | Q(assigned_waiter=request.user)),
        )
    record.completed = True
    record.save(update_fields=['completed'])
    return Response(
        {'success': True, 'message': 'Tarea finalizada correctamente'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@drf_role_required('gerente')
def api_update_zone(request, code):
    """API DRF para actualizar el nivel de congestión y permanencia de una zona."""
    zone = get_object_or_404(Zone, code=code.upper())
    serializer = ZoneUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        return Response(
            {'error': err_msg, 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    level = serializer.validated_data['level']
    minutes = serializer.validated_data['dwell_minutes']

    # Validación estricta de umbrales matemáticos de permanencia (Req 8):
    # - Normal: permanencia <= 2.0 min
    # - Moderada: permanencia entre 2.1 y 4.0 min
    # - Crítica: permanencia > 4.0 min
    if level == 'critica' and minutes <= 4.0:
        return Response(
            {'error': 'Una zona solo puede clasificarse como Crítica si su tiempo de permanencia supera los 4.0 minutos.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if level == 'normal' and minutes > 2.0:
        return Response(
            {'error': 'Una zona con tiempo de permanencia superior a 2.0 minutos no puede clasificarse como Normal.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if level == 'moderada' and (minutes <= 2.0 or minutes > 4.0):
        return Response(
            {'error': 'Una zona Moderada debe registrar un tiempo de permanencia entre 2.1 y 4.0 minutos.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    zone.level = level
    zone.dwell_minutes = minutes
    zone.save()
    return Response({
        'success': True,
        'code': zone.code,
        'level': zone.level,
        'level_display': zone.get_level_display(),
        'dwell_minutes': minutes,
        'alert': level == 'critica' and minutes > 4,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@drf_role_required('capitan', 'gerente')
def api_update_table(request, code):
    """API DRF para actualizar el estado operativo de una mesa."""
    table = get_object_or_404(TableState, code=code)
    serializer = TableStateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        return Response(
            {'error': err_msg, 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    state_val = serializer.validated_data['state']
    table.state = state_val
    table.save(update_fields=['state', 'updated_at'])
    return Response(
        {'success': True, 'code': table.code, 'state': state_val},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@drf_role_required('gerente')
@parser_classes([MultiPartParser, FormParser])
def api_vision(request):
    """API DRF para procesamiento de imágenes con OpenCV y resguardo opcional en S3."""
    serializer = VisionUploadSerializer(data=request.FILES)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if 'supera' in err_msg
            else status.HTTP_400_BAD_REQUEST
        )
        return Response({'error': err_msg}, status=status_code)

    uploaded = serializer.validated_data['file']
    raw = uploaded.read()
    if len(raw) > 5 * 1024 * 1024:
        return Response(
            {'error': 'Archivo demasiado grande.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    try:
        http_code, result = analyze_image(uploaded.name, raw, uploaded.content_type)
    except ServiceUnavailable as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if http_code != 200:
        return Response(
            {'error': result.get('detail', 'Imagen inválida')},
            status=http_code,
        )

    try:
        s3_key = optional_upload_s3(raw, uploaded.name, uploaded.content_type)
    except Exception as s3_err:
        logger.warning("Fallo al subir evidencia a S3 (%s)", s3_err)
        s3_key = ''
        result['aws_warning'] = 'No se pudo guardar la imagen en AWS S3. Revisa el bucket y los permisos IAM.'

    # Propagación automática de afluencia OpenCV a niveles de saturación de zonas (Req 3 & 8)
    updated_zones_info = []
    zone_counts = result.get('zone_counts', {})
    for code, count in zone_counts.items():
        zone_obj = Zone.objects.filter(code=code.upper()).first()
        if zone_obj:
            if count >= 3:
                zone_obj.level = 'critica'
                zone_obj.dwell_minutes = max(zone_obj.dwell_minutes, 4.5)
            elif count >= 1:
                if zone_obj.level != 'critica':
                    zone_obj.level = 'moderada'
                    zone_obj.dwell_minutes = max(zone_obj.dwell_minutes, 2.5)
            else:
                if zone_obj.dwell_minutes <= 2.0:
                    zone_obj.level = 'normal'
            zone_obj.save(update_fields=['level', 'dwell_minutes', 'updated_at'])
            updated_zones_info.append({
                'code': zone_obj.code,
                'level': zone_obj.level,
                'level_display': zone_obj.get_level_display(),
                'dwell_minutes': round(zone_obj.dwell_minutes, 1),
                'people_count': count,
            })

    VisionAnalysis.objects.create(
        user=request.user,
        filename=uploaded.name[:180],
        people_count=result['people_count'],
        zone_counts=zone_counts,
        s3_key=s3_key,
    )
    result['aws_saved'] = bool(s3_key)
    result['s3_key'] = s3_key
    if s3_key:
        result['s3_status'] = f'Evidencia archivada en AWS S3 ({s3_key})'
    elif result.get('aws_warning'):
        result['s3_status'] = 'Almacenamiento local (falló conexión a AWS S3)'
    else:
        result['s3_status'] = 'Almacenamiento local (AWS S3 no configurado)'

    # Guardar copia de la última imagen anotada en estáticos para alertas del sistema
    annotated_b64 = result.get('annotated_image', '')
    if annotated_b64 and ',' in annotated_b64:
        try:
            import base64
            b64_part = annotated_b64.split(',', 1)[1]
            if len(b64_part) > 40:
                b64_part += '=' * (-len(b64_part) % 4)
                img_bytes = base64.b64decode(b64_part)
                target_path = settings.BASE_DIR / 'static' / 'img' / 'latest_vision_capture.jpg'
                target_path.write_bytes(img_bytes)
        except Exception as write_err:
            logger.debug("No se pudo escribir latest_vision_capture.jpg: %s", write_err)

    result['updated_zones'] = updated_zones_info
    result['sync_notice'] = (
        'Saturación de zonas sincronizada con OpenCV. El ruteo Dijkstra esquivará '
        'automáticamente los pasillos con mayor aglomeración.'
    )
    return Response(result, status=status.HTTP_200_OK)


@login_required
def api_latest_vision(request):
    """Retorna los datos del último análisis de visión y la URL de evidencia para alertas."""
    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()
    return JsonResponse({
        'image_url': '/static/img/latest_vision_capture.jpg',
        'people_count': recent_vision.people_count if recent_vision else 1,
        'zone_counts': recent_vision.zone_counts if recent_vision else {'A': 0, 'B': 1, 'C': 0},
        'filename': recent_vision.filename if recent_vision else 'captura_salon.jpg',
        'created_at': recent_vision.created_at.strftime('%d/%m/%Y %H:%M') if recent_vision else '',
    })


@login_required
def profile_view(request):
    """Vista de perfil, edición de datos personales y gestión blindada de personal (Req 5 & 7)."""
    context = page_context(request, 'Mi Perfil', 'profile')
    user = request.user
    role = context['role']

    # Actualización libre de datos personales (nombre, correo) con blindaje de rol
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()

        if not first_name:
            messages.error(request, 'El nombre no puede estar vacío.')
        elif email and '@' not in email:
            messages.error(request, 'Por favor, proporciona un correo electrónico válido.')
        else:
            user.first_name = first_name
            user.last_name = last_name
            if email:
                user.email = email
            user.save(update_fields=['first_name', 'last_name', 'email'])
            messages.success(request, 'Tus datos personales se han actualizado correctamente.')
        return redirect('profile')

    # Estadísticas operativas del usuario actual
    total_completed = RouteConsultation.objects.filter(
        Q(user=user) | Q(assigned_waiter=user),
        completed=True,
    ).count()

    total_assigned = RouteConsultation.objects.filter(assigned_waiter=user).count()
    assigned_pending = RouteConsultation.objects.filter(assigned_waiter=user, completed=False).count()
    recent_activity = RouteConsultation.objects.select_related('user', 'assigned_waiter').filter(
        Q(user=user) | Q(assigned_waiter=user),
    ).order_by('-created_at')[:6]

    admin_stats = {}
    all_notifications = []
    staff_users = []
    if role in ('admin', 'capitan'):
        admin_stats = {
            'total_waiters': User.objects.filter(profile__role='mesero').count(),
            'total_routes_system': RouteConsultation.objects.count(),
            'unread_notifications': AdminNotification.objects.filter(read=False).count(),
        }
        all_notifications = list(AdminNotification.objects.order_by('-created_at')[:10])

    if role == 'admin':
        staff_users = list(User.objects.exclude(id=user.id).select_related('profile').order_by('username'))

    context.update({
        'profile_user': user,
        'total_completed': total_completed,
        'total_assigned': total_assigned,
        'assigned_pending': assigned_pending,
        'recent_activity': recent_activity,
        'admin_stats': admin_stats,
        'all_notifications': all_notifications,
        'staff_users': staff_users,
        'available_roles': Profile.ROLE_CHOICES,
    })
    return render(request, 'profile.html', context)


@api_view(['POST'])
@drf_role_required('capitan', 'gerente')
def api_mark_notification_read(request, pk):
    """API para marcar una notificación administrativa como leída."""
    notif = get_object_or_404(AdminNotification, pk=pk)
    notif.read = True
    notif.save(update_fields=['read'])
    return Response({'success': True, 'id': notif.id})


@api_view(['POST'])
@drf_role_required('admin')
def api_update_user_role(request, user_id):
    """API para que el Administrador promueva o asigne roles de personal de forma blindada (Req 5 & 7)."""
    target_user = get_object_or_404(User, id=user_id)

    # Blindaje 1: No auto-modificación de rol propio
    if target_user.id == request.user.id:
        return Response(
            {'error': 'Por seguridad, no puedes alterar tu propio rol operativo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Blindaje 2: No degradar a otros superusuarios / administradores
    if target_user.is_superuser:
        return Response(
            {'error': 'No está permitido modificar el rol de otros administradores del sistema.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    new_role = request.data.get('role', '').lower().strip()
    valid_roles = dict(Profile.ROLE_CHOICES)
    if new_role not in valid_roles:
        return Response(
            {'error': f'Rol inválido. Roles válidos: {", ".join(valid_roles.keys())}.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile, _ = Profile.objects.get_or_create(user=target_user)
    profile.role = new_role
    profile.save(update_fields=['role'])

    return Response({
        'success': True,
        'message': f'Rol de @{target_user.username} actualizado a {profile.get_role_display()}.',
        'user_id': target_user.id,
        'username': target_user.username,
        'new_role': profile.role,
        'new_role_display': profile.get_role_display(),
    }, status=status.HTTP_200_OK)



@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_create_table(request):
    """API DRF para crear una nueva mesa en el plano topológico CAD (Req 6)."""
    from .layout import add_table

    code = request.data.get('code', '').strip().lower()
    label = request.data.get('label', '').strip()
    seats = request.data.get('seats', 4)
    zone = request.data.get('zone', 'A').strip().upper()
    node = request.data.get('node', '').strip()

    if not code:
        return Response({'error': 'El código de la mesa es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
    if not label:
        label = f"Mesa {code.replace('mesa', '').zfill(2)}"
    if not node:
        return Response({'error': 'Las coordenadas de la mesa (nodo X,Y) son requeridas.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        seats_num = int(seats)
        if seats_num <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return Response({'error': 'La capacidad de comensales debe ser un número entero positivo.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        new_table = add_table(code=code, label=label, seats=seats_num, zone=zone, node=node)
        return Response({
            'success': True,
            'table': new_table,
            'message': f"Mesa '{new_table['label']}' creada exitosamente en el salón.",
        }, status=status.HTTP_201_CREATED)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_move_table(request, code):
    """API DRF para reubicar las coordenadas o zona de una mesa en el plano CAD (Req 6)."""
    from .layout import move_table

    new_node = request.data.get('node', '').strip() or None
    new_zone = request.data.get('zone', '').strip().upper() or None

    if not new_node and not new_zone:
        return Response({'error': 'Se requiere al menos el nuevo nodo (X,Y) o la nueva zona de reubicación.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        updated = move_table(code=code, new_node=new_node, new_zone=new_zone)
        return Response({
            'success': True,
            'table': updated,
            'message': f"Mesa '{updated['label']}' reubicada exitosamente a posición {updated['node']} (Zona {updated['zone']}).",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_unify_tables(request):
    """API DRF para unificar dos o más mesas contiguas para grupos grandes (Req 6)."""
    from .layout import unify_tables

    table_codes = request.data.get('table_codes', [])
    unified_code = request.data.get('unified_code', '').strip().lower()
    unified_label = request.data.get('unified_label', '').strip()

    if not isinstance(table_codes, list) or len(table_codes) < 2:
        return Response({'error': 'Debes seleccionar al menos 2 mesas para fusionar.'}, status=status.HTTP_400_BAD_REQUEST)

    if not unified_code:
        unified_code = f"mesa_{'_'.join(c.replace('mesa', '') for c in table_codes)}"
    if not unified_label:
        unified_label = f"Mesa {'+'.join(c.replace('mesa', '') for c in table_codes)} (Grupo)"

    try:
        unified = unify_tables(
            table_codes=table_codes,
            unified_code=unified_code,
            unified_label=unified_label,
        )
        return Response({
            'success': True,
            'unified_table': unified,
            'message': f"Mesas fusionadas exitosamente en '{unified['label']}' (Capacidad: {unified['seats']} personas).",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_separate_table(request):
    """API DRF para separar/desunificar una mesa previamente combinada restaurando las originales."""
    from .layout import separate_table

    code = request.data.get('code', '').strip().lower()
    if not code:
        return Response({'error': 'El código de la mesa a separar es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        restored = separate_table(unified_code=code)
        return Response({
            'success': True,
            'restored_tables': restored,
            'message': f"Mesa '{code}' separada exitosamente. Se restauraron {len(restored)} mesas originales.",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_update_layout_dimensions(request):
    """API DRF para redimensionar la cuadrícula CAD del plano del salón."""
    from .layout import update_dimensions

    try:
        columns = int(request.data.get('columns', 0))
        rows = int(request.data.get('rows', 0))
    except (ValueError, TypeError):
        return Response({'error': 'Las columnas y filas deben ser números enteros.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dims = update_dimensions(columns=columns, rows=rows)
        return Response({
            'success': True,
            'dimensions': dims,
            'message': f"Dimensiones del salón actualizadas a {dims['columns']}x{dims['rows']}.",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)
