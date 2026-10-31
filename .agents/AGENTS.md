# Contexto Embebido del Proyecto — OptiFlow Dining

## 1. Identidad del Proyecto
- **Nombre:** OptiFlow Dining
- **Tipo:** Plataforma Web Modular de Hospitalidad y Optimización Operativa de Salón (Django 5 + DRF + 2 Microservicios FastAPI + OpenCV + AWS S3 opcional)
- **Repositorio GitHub:** `https://github.com/Sofia12-cer/OptiFlow_Dining` (Cuenta vinculada: `Sofia12-cer`)
- **Bóveda Obsidian:** `OptiFlow Dining Vault` (`.obsidian_vault`)

## 2. Arquitectura y Stack Tecnológico
- **Aplicación Principal (`web/` — Puerto `8000`):** Django + Django REST Framework + WhiteNoise + SQLite (compatible con PostgreSQL vía `DATABASE_URL`).
- **Microservicio de Ruteo (`services/routing/` — Puerto `8001`):** FastAPI + Algoritmo Dijkstra con evasión de congestión zonal, bloqueo físico de mesas intermedias y respeto estricto de muros dimensionales (`0..columns-1`, `0..rows-1`).
- **Microservicio de Visión (`services/vision/` — Puerto `8002`):** FastAPI + OpenCV multi-modelo (`HOG` + `Haar Cascades` + `CLAHE` + `NMS`) ejecutado sin bloquear el event loop (`asyncio.to_thread`).
- **Configuración Espacial Compartida (`config/salon.json`):** Topología atómica del salón (`columns`, `rows`, `origins`, `tables`, `zones`).

## 3. Estructura Modular y Archivos Principales
- `iniciar.cmd` / `iniciar.ps1`: Lanzadores automáticos locales en Windows (levantan puertos `8000`, `8001`, `8002` y abren `http://127.0.0.1:8000`).
- `config/salon.json`: Definición viva de dimensiones, zonas (`A`, `B`, `C`), accesos y mesas.
- `web/core/layout.py`: Motor espacial CAD con escritura atómica, muros estrictos de dimensiones, partición dinámica de zonas (`compute_zones_for_columns`), reubicación automática por zona (`suggest_zone_coordinates`), unificación y separación de mesas.
- `web/core/models.py`: Modelos `Profile`, `TableState`, `Zone`, `RouteConsultation`, `VisionAnalysis` y `AdminNotification` (con destinatario `recipient` para supervisores).
- `web/core/views/`: Paquete modularizado (<300 líneas por archivo):
  - `helpers.py`: Permisos por rol (`role_for`, `role_required`, `drf_role_required`), consultas de notificaciones y `page_context`.
  - `auth_profile.py`: Login, registro, perfil, gestión blindada de roles y centro/resumen de avisos.
  - `pages.py`: Vistas de `dashboard`, `routes`, `saturation`, `analytics`, `layout` y `vision`.
  - `api_routing.py`: Cálculo de rutas, despacho seguro a meseros, cierre de tareas con notificación al supervisor y umbrales de saturación.
  - `api_cad_vision.py`: APIs CAD de mesas/dimensiones y pipeline OpenCV + AWS S3.
- `web/static/js/modules/`: Arquitectura cliente desacoplada:
  - `core.js`: Utilidades DOM/CSRF, toasts, campana de notificaciones con sondeo ligero, QR LAN y toggle de contraseñas.
  - `floor_plan.js`: Renderizado vectorial SVG dinámico adaptable a cualquier cuadrícula `columns × rows`.
  - `routing.js`: Trazado de rutas asignadas sin duplicación (`data-path`) y cierre reactivo instantáneo en UI.
  - `cad_tables.js`: Modales CAD, sincronización `Nodo ↔ Zona`, alertas inline de zona llena/límites y KPIs de mesas.
  - `vision_zones.js`: Cámara del Chef en vivo, carga de evidencia OpenCV y mapa de calor de zonas.
- `docs/`:
  - `ARQUITECTURA.md`: Documentación técnica y diagramas de arquitectura.
  - `guias/`: Guías rápidas de ejecución (`INICIAR_AQUI.txt`, `COMANDOS_INICIO.txt`).
  - `preview/`: Prototipo estático autónomo (`vista_previa.html`, `.css`, `.js`).
  - `assets_archive/`: Archivo histórico de bocetos gráficos no requeridos en runtime.

## 4. Módulos y Reglas de Negocio Clave
- **Matriz de Roles:**
  - `mesero`: Panel, Rutas (atención de tareas urgentes y auto-consulta) y Perfil.
  - `capitan` (Jefe de meseros): Panel, Rutas (asignación a meseros), Plano y mesas (estados), Indicadores, Perfil y campana de avisos.
  - `gerente`: Todo lo anterior + edición CAD de mesas/dimensiones, Saturación del salón y Visión OpenCV (sin cambiar roles de personal).
  - `admin`: Control total incluyendo promoción/cambio de roles con doble blindaje.
- **Invariantes Espaciales CAD:**
  - Las dimensiones `columns × rows` actúan como muro estricto: ninguna mesa ni ruta puede ubicarse o cruzar fuera de `0..columns-1` y `0..rows-1`.
  - Cambiar una mesa de Zona la reubica físicamente a una celda libre de esa zona o rechaza con HTTP 400 si la zona está llena.
- **Regla de Estáticos en Testing:**
  - Siempre ejecutar `.venv\Scripts\python.exe web\manage.py collectstatic --noinput` tras crear o renombrar archivos en `web/static/` antes de correr `manage.py test core` (WhiteNoise valida el manifiesto de estáticos).

