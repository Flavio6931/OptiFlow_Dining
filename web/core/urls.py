"""Definición de rutas URL de la aplicación web y APIs REST con DRF."""
from django.urls import path

from . import views

urlpatterns = [
    # Vistas de navegación y autenticación
    path('', views.landing, name='landing'),
    path('registro/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel/', views.dashboard, name='dashboard'),
    path('rutas/', views.routes_view, name='routes'),
    path('saturacion/', views.saturation_view, name='saturation'),
    path('indicadores/', views.analytics_view, name='analytics'),
    path('plano/', views.layout_view, name='layout'),
    path('vision/', views.vision_view, name='vision'),
    path('perfil/', views.profile_view, name='profile'),
    # Endpoints de API REST (Django REST Framework)
    path('api/rutas/', views.api_route, name='api_route'),
    path('api/rutas/<int:pk>/finalizar/', views.api_complete, name='api_complete'),
    path('api/zonas/<str:code>/', views.api_update_zone, name='api_update_zone'),
    path('api/mesas/crear/', views.api_create_table, name='api_create_table'),
    path('api/mesas/unificar/', views.api_unify_tables, name='api_unify_tables'),
    path('api/mesas/separar/', views.api_separate_table, name='api_separate_table'),
    path('api/plano/dimensiones/', views.api_update_layout_dimensions, name='api_update_layout_dimensions'),
    path('api/mesas/<str:code>/mover/', views.api_move_table, name='api_move_table'),
    path('api/mesas/<str:code>/', views.api_update_table, name='api_update_table'),
    path('api/vision/', views.api_vision, name='api_vision'),
    path('api/vision/ultima/', views.api_latest_vision, name='api_latest_vision'),
    path('api/notificaciones/resumen/', views.api_notifications_summary, name='api_notifications_summary'),
    path('api/notificaciones/<int:pk>/leer/', views.api_mark_notification_read, name='api_mark_notification_read'),
    path('api/usuarios/<int:user_id>/rol/', views.api_update_user_role, name='api_update_user_role'),
]

