"""Configuración del panel de administración nativo de Django."""
from django.contrib import admin
from .models import (
    AdminNotification,
    Profile,
    RouteConsultation,
    TableState,
    VisionAnalysis,
    Zone,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Administración de perfiles y roles operativos."""
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(TableState)
class TableStateAdmin(admin.ModelAdmin):
    """Administración de estado operativo de las mesas."""
    list_display = ('code', 'state', 'assigned_to', 'updated_at')
    list_filter = ('state',)


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    """Administración de zonas y niveles de saturación."""
    list_display = ('code', 'level', 'dwell_minutes', 'updated_at')
    list_filter = ('level',)


@admin.register(RouteConsultation)
class RouteConsultationAdmin(admin.ModelAdmin):
    """Auditoría y registro histórico de consultas de rutas."""
    list_display = (
        'user',
        'assigned_waiter',
        'origin',
        'destination',
        'recalculated',
        'congested',
        'completed',
        'created_at',
    )
    list_filter = ('recalculated', 'congested', 'completed')


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    """Notificaciones para administradores."""
    list_display = ('title', 'recipient', 'read', 'created_at')
    list_filter = ('read',)


admin.site.register(VisionAnalysis)
admin.site.site_header = 'OptiFlow Dining · Administración'

