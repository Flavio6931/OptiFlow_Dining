"""Paquete modular de vistas HTML y APIs REST de OptiFlow Dining."""
from ..services import (
    ServiceUnavailable,
    analyze_image,
    calculate_route,
    optional_upload_s3,
)
from .api_cad_vision import (
    api_create_table,
    api_latest_vision,
    api_move_table,
    api_separate_table,
    api_unify_tables,
    api_update_layout_dimensions,
    api_update_table,
    api_vision,
)
from .api_routing import api_complete, api_route, api_update_zone
from .auth_profile import (
    api_mark_notification_read,
    api_notifications_summary,
    api_update_user_role,
    landing,
    login_view,
    logout_view,
    profile_view,
    register_view,
)
from .helpers import drf_role_required, page_context, role_for, role_required
from .pages import (
    analytics_view,
    dashboard,
    layout_view,
    routes_view,
    saturation_view,
    vision_view,
)

__all__ = [
    'ServiceUnavailable',
    'analyze_image',
    'calculate_route',
    'optional_upload_s3',
    'role_for',
    'role_required',
    'drf_role_required',
    'page_context',
    'landing',
    'register_view',
    'login_view',
    'logout_view',
    'profile_view',
    'dashboard',
    'routes_view',
    'saturation_view',
    'analytics_view',
    'layout_view',
    'vision_view',
    'api_route',
    'api_complete',
    'api_update_zone',
    'api_update_table',
    'api_create_table',
    'api_move_table',
    'api_unify_tables',
    'api_separate_table',
    'api_update_layout_dimensions',
    'api_vision',
    'api_latest_vision',
    'api_mark_notification_read',
    'api_notifications_summary',
    'api_update_user_role',
]

