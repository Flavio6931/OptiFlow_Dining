"""Vistas HTML de los módulos operativos: Panel, Rutas, Saturación, Indicadores, Plano y Visión."""
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Q, Sum
from django.shortcuts import render

from ..models import RouteConsultation, TableState, VisionAnalysis, Zone
from ..services import get_s3_presigned_url
from .helpers import SUPERVISOR_ROLES, page_context, role_required


@login_required
def dashboard(request):
    """Panel principal con métricas operativas y estado en tiempo real del salón."""
    context = page_context(request, 'Panel principal', 'dashboard')
    routes = RouteConsultation.objects.count()
    completed_routes = RouteConsultation.objects.filter(completed=True).count()
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
        z.saturation_pct = min(100, max(12, int((z.dwell_minutes / 5.0) * 100)))

    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()
    efficiency_rate = round(((routes - recalculated) / routes) * 100, 1) if routes > 0 else 100.0

    user_role = context['role']
    last_routes = list(
        RouteConsultation.objects.select_related('user', 'assigned_waiter').order_by('-created_at')[:8]
    )
    assigned_to_me = []
    if user_role == 'mesero':
        assigned_to_me = list(
            RouteConsultation.objects.select_related('user', 'assigned_waiter')
            .filter(assigned_waiter=request.user, completed=False)
            .order_by('-created_at')
        )

    context.update({
        'total_routes': routes,
        'completed_routes': completed_routes,
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
    """Vista interactiva de cálculo, despacho y atención de rutas en el mapa SVG."""
    context = page_context(request, 'Consultar rutas', 'routes')
    user_role = context['role']
    waiters = []
    assigned_to_me = []

    if user_role in SUPERVISOR_ROLES:
        waiters = list(
            User.objects.filter(profile__role='mesero')
            .exclude(id=request.user.id)
            .order_by('first_name', 'username')
        )
        recent_routes = list(
            RouteConsultation.objects.select_related('user', 'assigned_waiter').order_by('-created_at')[:8]
        )
    else:
        recent_routes = list(
            RouteConsultation.objects.select_related('user', 'assigned_waiter')
            .filter(Q(user=request.user) | Q(assigned_waiter=request.user))
            .order_by('-created_at')[:8]
        )
        assigned_to_me = list(
            RouteConsultation.objects.select_related('user', 'assigned_waiter')
            .filter(assigned_waiter=request.user, completed=False)
            .order_by('-created_at')
        )
        for task in assigned_to_me:
            task.path_json = json.dumps(task.path or [], ensure_ascii=False)

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
        'latest_vision_json': json.dumps(latest_vision_payload, ensure_ascii=False),
    })
    return render(request, 'routes.html', context)


@role_required('gerente')
def saturation_view(request):
    """Vista de monitoreo y calibración de saturación de zonas."""
    context = page_context(request, 'Saturación del salón', 'saturation')
    context['critical_zones'] = Zone.objects.filter(level='critica', dwell_minutes__gt=4)
    return render(request, 'saturation.html', context)


@role_required('gerente', 'capitan')
def analytics_view(request):
    """Vista de indicadores operativos para gerencia y jefatura de meseros."""
    context = page_context(request, 'Indicadores operativos', 'analytics')
    totals = RouteConsultation.objects.count()
    completed = RouteConsultation.objects.filter(completed=True).count()
    recalculated = RouteConsultation.objects.filter(recalculated=True).count()
    direct_routes = max(0, totals - recalculated)
    direct_pct = round((direct_routes / totals * 100), 1) if totals > 0 else 100.0
    completion_rate = round((completed / totals * 100), 1) if totals > 0 else 100.0

    entregas = RouteConsultation.objects.filter(task_type='entrega').count()
    retiros = RouteConsultation.objects.filter(task_type='retiro').count()

    distance_agg = RouteConsultation.objects.aggregate(avg_dist=Avg('distance'), total_dist=Sum('distance'))
    avg_distance = round(distance_agg['avg_dist'] or 0, 1)
    total_distance = distance_agg['total_dist'] or 0

    zones = list(Zone.objects.order_by('code'))
    critical_count = sum(1 for z in zones if z.level == 'critica')
    zones_normal_count = sum(1 for z in zones if z.level == 'normal')
    avg_dwell = round(sum(z.dwell_minutes for z in zones) / len(zones), 1) if zones else 0.0
    for z in zones:
        z.saturation_pct = min(100, max(10, int((z.dwell_minutes / 5.0) * 100)))

    tables = list(TableState.objects.all())
    tables_total = len(tables)
    tables_available = sum(1 for t in tables if t.state == 'disponible')
    tables_occupied = sum(1 for t in tables if t.state == 'ocupada')
    tables_active = sum(1 for t in tables if t.state == 'activa')
    occupancy_pct = round((tables_occupied / tables_total * 100), 1) if tables_total > 0 else 0

    vision_count = VisionAnalysis.objects.count()
    vision_agg = VisionAnalysis.objects.aggregate(total_people=Sum('people_count'))
    total_people_detected = vision_agg['total_people'] or 0
    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()

    base_score = 96.0 - (critical_count * 14.0 if critical_count > 0 else 0.0)
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
        'last_routes': RouteConsultation.objects.select_related('user', 'assigned_waiter').order_by('-created_at')[:8],
    })
    return render(request, 'analytics.html', context)


@role_required('capitan', 'gerente')
def layout_view(request):
    """Vista del plano topológico CAD 2D y control de estado de mesas."""
    context = page_context(request, 'Plano y mesas', 'layout')
    layout = context.get('layout') or {}
    tables_state = context.get('tables_state') or []
    states_dict = {t.code: t.state for t in tables_state}

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
    """Vista de análisis fotográfico de ocupación con OpenCV y resguardo S3."""
    context = page_context(request, 'Análisis con OpenCV', 'vision')
    history = list(VisionAnalysis.objects.order_by('-created_at')[:6])
    for item in history:
        item.presigned_url = get_s3_presigned_url(item.s3_key) if item.s3_key else ''
    context['analysis_history'] = history
    context['s3_enabled'] = bool(settings.AWS_S3_BUCKET)
    context['s3_bucket'] = settings.AWS_S3_BUCKET or ''
    context['aws_region'] = settings.AWS_REGION or ''
    return render(request, 'vision.html', context)
