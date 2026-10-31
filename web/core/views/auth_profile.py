"""Vistas de autenticación, perfil personal, avisos a supervisores y gestión blindada de roles."""
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timesince import timesince
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..forms import LoginForm, RegisterForm
from ..models import AdminNotification, Profile, RouteConsultation
from .helpers import (
    SUPERVISOR_ROLES,
    drf_role_required,
    notifications_queryset_for,
    page_context,
    role_for,
)


def landing(request):
    """Página pública de bienvenida."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html', {'page_title': 'Bienvenido'})


def register_view(request):
    """Registro público de nuevos usuarios con rol operativo mesero."""
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
    """Inicio de sesión con soporte para redirección interna segura."""
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
def profile_view(request):
    """Vista de perfil, edición de datos personales, avisos de supervisión y gestión de roles."""
    context = page_context(request, 'Mi Perfil', 'profile')
    user = request.user
    role = context['role']

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

    user_routes_qs = RouteConsultation.objects.filter(Q(user=user) | Q(assigned_waiter=user))
    total_routes_user = user_routes_qs.count()
    total_completed = user_routes_qs.filter(completed=True).count()
    total_assigned = RouteConsultation.objects.filter(assigned_waiter=user).count()
    assigned_pending_qs = RouteConsultation.objects.select_related('user').filter(
        assigned_waiter=user,
        completed=False,
    ).order_by('-created_at')
    assigned_pending = assigned_pending_qs.count()
    recent_activity = user_routes_qs.select_related('user', 'assigned_waiter').order_by('-created_at')[:8]

    admin_stats = {}
    all_notifications = []
    staff_users = []
    if role in SUPERVISOR_ROLES:
        notif_qs = notifications_queryset_for(user)
        admin_stats = {
            'total_waiters': User.objects.filter(profile__role='mesero').count(),
            'total_routes_system': RouteConsultation.objects.count(),
            'unread_notifications': notif_qs.filter(read=False).count(),
        }
        all_notifications = list(notif_qs.order_by('-created_at')[:12])

    if role == 'admin':
        staff_users = list(User.objects.exclude(id=user.id).select_related('profile').order_by('username'))

    context.update({
        'profile_user': user,
        'total_routes': total_routes_user,
        'total_completed': total_completed,
        'total_assigned': total_assigned,
        'assigned_pending': assigned_pending,
        'pending_assigned_tasks': list(assigned_pending_qs),
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
    """Marca como leída una notificación dirigida al supervisor actual o general."""
    if role_for(request.user) == 'admin':
        notif = get_object_or_404(AdminNotification, pk=pk)
    else:
        notif = get_object_or_404(notifications_queryset_for(request.user), pk=pk)
    notif.read = True
    notif.save(update_fields=['read'])
    unread_remaining = notifications_queryset_for(request.user).filter(read=False).count()
    return Response({'success': True, 'id': notif.id, 'unread_count': unread_remaining})


@login_required
def api_notifications_summary(request):
    """Entrega resumen en tiempo real de notificaciones o tareas urgentes para el topbar."""
    user = request.user
    user_role = role_for(user)
    if user_role in SUPERVISOR_ROLES:
        qs = notifications_queryset_for(user).filter(read=False)
        items = [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'ago': f'{timesince(n.created_at)} atrás',
            }
            for n in qs[:5]
        ]
        return JsonResponse({'role': user_role, 'unread_count': qs.count(), 'items': items})

    pending = RouteConsultation.objects.filter(assigned_waiter=user, completed=False).count()
    return JsonResponse({'role': user_role, 'waiter_pending_count': pending})


@api_view(['POST'])
@drf_role_required('admin')
def api_update_user_role(request, user_id):
    """Permite al Administrador promover o reasignar roles operativos con doble blindaje."""
    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        return Response(
            {'error': 'Por seguridad, no puedes alterar tu propio rol operativo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

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

