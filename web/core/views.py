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
from django.db.models import Avg, Count, Sum
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
from .models import Profile, RouteConsultation, TableState, VisionAnalysis, Zone
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
    return {
        'page_title': page_title,
        'active': active,
        'role': role_for(user),
        'display_name': full_name,
        'layout': layout,
        'layout_json': json.dumps(layout, ensure_ascii=False),
        'zones': list(Zone.objects.order_by('code')),
        'tables_state': list(TableState.objects.order_by('code')),
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
        'last_routes': RouteConsultation.objects.select_related('user').order_by('-created_at')[:4],
        'recent_vision': recent_vision,
        'recent_people_count': recent_vision.people_count if recent_vision else 0,
    })
    return render(request, 'dashboard.html', context)


@role_required('mesero', 'capitan')
def routes_view(request):
    """Vista de consulta interactiva de rutas."""
    context = page_context(request, 'Consultar rutas', 'routes')
    context['recent_routes'] = RouteConsultation.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'routes.html', context)


@role_required('capitan', 'gerente')
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


@role_required('capitan')
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


@role_required('capitan')
def vision_view(request):
    """Vista de análisis fotográfico de ocupación con OpenCV."""
    context = page_context(request, 'Análisis con OpenCV', 'vision')
    context['analysis_history'] = VisionAnalysis.objects.order_by('-created_at')[:6]
    context['s3_enabled'] = bool(settings.AWS_S3_BUCKET)
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
@drf_role_required('mesero', 'capitan')
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

    record = RouteConsultation.objects.create(
        user=request.user,
        origin=origin,
        destination=destination,
        task_type=task_type,
        path=result['path'],
        distance=result['distance'],
        recalculated=avoid,
        congested=result['congested'],
    )
    result['route_id'] = record.id
    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@drf_role_required('mesero', 'capitan')
def api_complete(request, pk):
    """API DRF para marcar una consulta de ruta como finalizada."""
    record = get_object_or_404(RouteConsultation, pk=pk, user=request.user)
    record.completed = True
    record.save(update_fields=['completed'])
    return Response(
        {'success': True, 'message': 'Tarea finalizada correctamente'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@drf_role_required('capitan')
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

    zone.level = level
    zone.dwell_minutes = minutes
    zone.save()
    return Response({
        'success': True,
        'code': zone.code,
        'level': zone.level,
        'dwell_minutes': minutes,
        'alert': level == 'critica' and minutes > 4,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@drf_role_required('capitan')
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
@drf_role_required('capitan')
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

    VisionAnalysis.objects.create(
        user=request.user,
        filename=uploaded.name[:180],
        people_count=result['people_count'],
        zone_counts=result['zone_counts'],
        s3_key=s3_key,
    )
    result['aws_saved'] = bool(s3_key)
    return Response(result, status=status.HTTP_200_OK)
