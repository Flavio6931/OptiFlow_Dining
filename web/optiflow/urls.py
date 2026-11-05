"""Enrutador principal del proyecto OptiFlow Dining."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Las fotos del salón solo se muestran con sesión iniciada.
urlpatterns += [
    re_path(
        rf"^{settings.MEDIA_URL.strip('/')}/(?P<path>.*)$",
        login_required(serve),
        {'document_root': settings.MEDIA_ROOT},
    ),
]
