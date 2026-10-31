"""APIs REST de ruteo Dijkstra, ciclo de vida de tareas asignadas y saturación de zonas."""
import logging

from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

import core.views as views_pkg

from ..models import AdminNotification, RouteConsultation, Zone
from ..serializers import RouteRequestSerializer, ZoneUpdateSerializer
from .helpers import SUPERVISOR_ROLES, drf_role_required, role_for

logger = logging.getLogger(__name__)


@api_view(['POST'])
@drf_role_required('mesero', 'capitan', 'gerente')
def api_route(request):
    """Calcula la ruta óptima con Dijkstra, permite asignación por supervisores y auto-desvío seguro."""
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
        http_code, result = views_pkg.calculate_route({
            'origin': origin,
            'destination': destination,
            'task_type': task_type,
            'avoid_congestion': avoid,
            'zone_levels': zone_levels,
        })
    except views_pkg.ServiceUnavailable as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if http_code != 200:
        return Response(
            {'error': result.get('detail', 'No existe una ruta disponible')},
            status=http_code,
        )

    assigned_waiter_id = data.get('assigned_waiter')
    assigned_waiter = None
    if assigned_waiter_id and role_for(request.user) in SUPERVISOR_ROLES:
        assigned_waiter = User.objects.filter(id=assigned_waiter_id).first()

    auto_safe_reroute = False
    if assigned_waiter and result.get('congested') and not avoid:
        try:
            http_code_safe, safe_result = views_pkg.calculate_route({
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
        except views_pkg.ServiceUnavailable:
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
    result['is_assigned'] = bool(assigned_waiter)
    result['status_label'] = 'Pendiente' if assigned_waiter else 'En curso'
    result['assigned_waiter_name'] = (
        assigned_waiter.get_full_name() or assigned_waiter.username
        if assigned_waiter else ''
    )
    return Response(result, status=status.HTTP_200_OK)


@api_view(['POST'])
@drf_role_required('mesero', 'capitan', 'gerente')
def api_complete(request, pk):
    """Marca una ruta como finalizada, actualiza contadores y notifica al supervisor que la asignó."""
    if role_for(request.user) in SUPERVISOR_ROLES:
        record = get_object_or_404(
            RouteConsultation.objects.select_related('user', 'assigned_waiter'),
            pk=pk,
        )
    else:
        record = get_object_or_404(
            RouteConsultation.objects.select_related('user', 'assigned_waiter'),
            Q(pk=pk) & (Q(user=request.user) | Q(assigned_waiter=request.user)),
        )

    was_completed = record.completed
    record.completed = True
    record.save(update_fields=['completed'])

    notified_supervisor = False
    if not was_completed and record.assigned_waiter_id and record.user_id != record.assigned_waiter_id:
        waiter_user = record.assigned_waiter
        waiter_name = waiter_user.get_full_name() or waiter_user.username
        if role_for(record.user) in SUPERVISOR_ROLES:
            AdminNotification.objects.create(
                recipient=record.user,
                title=f'✓ Ruta atendida · {record.destination.upper()}',
                message=(
                    f'El mesero {waiter_name} (@{waiter_user.username}) finalizó la ruta asignada '
                    f'({record.get_task_type_display()}: {record.origin.upper()} ➔ {record.destination.upper()}).'
                ),
            )
            notified_supervisor = True

    target_waiter = record.assigned_waiter or request.user
    pending_assigned_count = RouteConsultation.objects.filter(
        assigned_waiter=target_waiter,
        completed=False,
    ).count()

    msg = (
        'Tarea finalizada correctamente. Se notificó al supervisor.'
        if notified_supervisor
        else 'Tarea finalizada correctamente'
    )
    return Response(
        {
            'success': True,
            'route_id': record.id,
            'completed': True,
            'was_assigned': bool(record.assigned_waiter_id),
            'notified_supervisor': notified_supervisor,
            'pending_assigned_count': pending_assigned_count,
            'status_label': 'Finalizada',
            'message': msg,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@drf_role_required('gerente')
def api_update_zone(request, code):
    """Actualiza el nivel de congestión y tiempo de permanencia de una zona validando umbrales."""
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

