# Estado Actual del Proyecto - OptiFlow Dining

## Resumen del Proyecto
- **Nombre:** OptiFlow Dining
- **Tipo:** Aplicación web Django + Microservicios FastAPI (Rutas con Dijkstra, Visión con OpenCV HOG) + Docker Compose
- **Ruta Local:** `C:\Users\Flavio\Desktop\H4CK\Flavio\OptiFlow_Dining`
- **Repositorio:** `https://github.com/Sofia12-cer/OptiFlow_Dining`
- **Cuenta GitHub:** Sofia12-cer (Sofia)
- **Bóveda Obsidian:** `C:\Users\Flavio\Documents\OptiFlow Dining Vault`

## Arquitectura y Módulos
1. **Web (Django):**
   - Autenticación, control de perfiles y roles (Mesero, Capitán, Gerente).
   - Layout y plano esquemático de mesas con persistencia.
   - Panel de indicadores y control de saturación de zonas.
2. **Servicio Routing (FastAPI):**
   - Algoritmo Dijkstra para cálculo de rutas óptimas y recalculación por congestión.
3. **Servicio Visión (FastAPI + OpenCV):**
   - Detección aproximada de personas de pie mediante HOG.

## Tareas Completadas
- [x] Clonación del repositorio en `C:\Users\Flavio\Desktop\H4CK\Flavio\OptiFlow_Dining`.
- [x] Configuración del marcador `.obsidian_vault` vinculado a `OptiFlow Dining Vault`.
- [x] Verificación de credenciales Git asignadas a `Josue2004exe`.
- [x] Normalización de código a PEP 8 estricto y resolución de excepciones silenciosas en `web/core/` (`services.py`, `views.py`, `models.py`).
- [x] Normalización PEP 8 completa y documentación de microservicios FastAPI (`services/routing/main.py` y `services/vision/main.py`).
- [x] Configuración formal de entorno virtual `.venv` e instalación de dependencias completas (Django, DRF, FastAPI, OpenCV, Uvicorn, Whitenoise, etc.).
- [x] Creación de `pyrightconfig.json` y configuración de `.vscode/settings.json` vinculados a `.venv` (0 errores en Pyright).
- [x] Generación de `.env` (`scripts/generate_env.py`) y recolección de estáticos (`collectstatic`).
- [x] Ejecución y pase exitoso del 100% de la suite de pruebas automatizadas (9/9 pruebas `OK`).
- [x] Hardening de seguridad en Login: Eliminación de tarjeta de credenciales demo predeterminadas expuestas (`admin/1234`) y limpieza de formularios tanto en Django (`login.html`) como en `vista_previa.html`.
- [x] Refactorización global de legibilidad y estructura: Descompresión e indentación jerárquica de todas las plantillas HTML (`web/templates/*.html`), expansión multilínea de `web/static/css/app.css` (2600+ líneas) y normalización PEP 8 estricta en `settings.py`, `forms.py`, `admin.py` y `tests.py`.
- [x] Limpieza de repositorio: Eliminación de scripts obsoletos `iniciar_local.bat` y `scripts/generate_env.py`.
- [x] Inicialización de Base de Datos: Migraciones aplicadas (`migrate`), catálogo espacial sembrado (`seed_demo`: mesas 01-08 y zonas A, B, C) y superusuario `admin` listo para operar.
- [x] Creación de lanzadores de microservicios: `iniciar.cmd` (ejecución con doble clic en Windows), `iniciar.ps1` (PowerShell automatizado con títulos de ventana) y guía de texto en bloc de notas `COMANDOS_INICIO.txt` con comandos paso a paso y credenciales.
- [x] Actualización de `INICIAR_AQUI.txt` para reflejar la puesta en marcha local simplificada.
- [x] Rediseño Split-Screen Dark Hospitality en Auth: Implementado en [login.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/login.html), [register.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/register.html), [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css), [forms.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/forms.py) y [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js) con fondo inmersivo de restaurante (`restaurant_bg.jpg`), isotipo en espiral naranja, tarjeta flotante azul marino (`#081222`), inputs píldora oscuros, botón ojo para mostrar contraseña y CTA naranja terracota.
- [x] Corrección de Autofill y Contraste de Texto: Neutralizado el comportamiento de Chrome/Edge (`:-webkit-autofill`) que forzaba fondo blanco/azul claro, y asegurado texto en blanco nítido (`-webkit-text-fill-color: #ffffff !important; caret-color: #ffffff;`).
- [x] Modernización Visual Global Dark Hospitality: Aplicada en toda la plataforma ([base.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/base.html), [dashboard.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/dashboard.html), [routes.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/routes.html), [saturation.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/saturation.html), [analytics.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/analytics.html), [layout.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/layout.html), [vision.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/vision.html), [landing.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/landing.html), [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css) y [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js)) con paleta preservada (Azul noche `#060e1d`, Naranja `#ff6938`/`#ff7b3d`, Verde esmeralda `#10b981`), topbar glassmorphism, radar de estado animado, tarjetas elevadas y plano esquemático dark blueprint.
- [x] Integración de Logotipo Oficial e Isotipo Fiel: Extracción y limpieza en alta resolución del isotipo de espiral circular naranja con tenedores y plato central en [optiflow_icon.png](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/img/optiflow_icon.png). Integración de tipografía geométrica inclinada *Black Italic* (Google Fonts Montserrat 900 Italic) con texto en blanco nítido (`OPTIFLOW DINING`) en todas las plantillas ([base.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/base.html), [login.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/login.html), [register.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/register.html), [landing.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/landing.html), [public.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/public.html) y [vista_previa.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/vista_previa.html)).
- [x] Módulo de Visión con Cámara en Vivo (Chef Cam) & Logo Dedicado: Generación y procesamiento del logotipo e isotipo de la cámara digital con gorro de chef en [chef_camera_icon.png](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/img/chef_camera_icon.png). Implementación de soporte para cámara web en tiempo real con selector de pestañas (Cámara en Vivo vs Subir Archivo), visor HUD con efecto de escaneo, captura instantánea de fotogramas vía canvas y procesamiento directo en OpenCV HOG ([vision.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/vision.html), [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js) y [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css)).
- [x] Animación de Rueda Trasera de Apertura en Cámara Chef: Separación quirúrgica en dos capas de renderizado ([chef_cam_wheel_512.png](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/img/chef_cam_wheel_512.png) y [chef_cam_center_512.png](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/img/chef_cam_center_512.png)). Implementación del componente `.chef-cam-composite-wrap` con rotación continua infinita 360° (`@keyframes spinApertureWheel`) de las aspas del vórtice de apertura detrás de la cámara, manteniendo el cuerpo de la cámara y gorro de chef nítidos, estables y con micro-respiración flotante en primer plano.
- [x] Rotación Lenta y Continua del Isotipo Espiral de Marca: Configuración de `@keyframes brandLogoSlowSpin` (26s lineal infinito) para el isotipo de espiral circular con tenedores (`.brand-logo-img`), con aceleración interactiva a 9s y resplandor al posar el cursor, y reducción pausada a 24s para la rueda de apertura de la cámara chef.
- [x] Modernización Arquitectónica y Sincronización Reactiva de "Plano y mesas" (`/plano/`): Implementación de blueprint CAD 2D interactivo con delimitación de zonas (A, B, C), pasillos peatonales, cajas de Cocina y Acceso, mesas con sillas según comensales (2, 4, 6 plazas) y beacons luminosos de estado en SVG. Integración de barra KPI ejecutiva (Total, Disponibles, Activas, Ocupadas), chips de filtrado rápido, sincronización asíncrona bidireccional (cambio de estado actualiza plano y tarjetas en tiempo real sin recargar página) y enfoque interactivo SVG-tarjeta con destello visual.
- [x] Rediseño Integral del Panel Principal (`/panel/`) - Centro de Mando Operativo y Telemetría: Hero de mando ejecutivo (`.dashboard-hero-card`) con radar y widget de pulso del salón (mesas libres/activas/ocupadas, barra de ocupación y estado de tráfico), 4 tarjetas KPI con tags de arquitectura (Dijkstra, Saturación, Ocupación y Visión OpenCV), 5 accesos rápidos modernos con micro-bordes temáticos y split operativo en 2 columnas (telemetría de zonas con barras progresivas de saturación vs feed de rutas en tiempo real y visión).
- [x] Modernización Ejecutiva del Módulo de Indicadores y Analítica (`/indicadores/`): Scorecard de eficiencia operativa OptiFlow (índice global /100 con evaluación cualitativa), 4 tarjetas KPI (Dijkstra, Saturación, Tasa de finalización y Afluencia HOG), medidores de desglose de rutas (directas vs recalculadas), barra de distribución de tareas (entregas vs retiros), matriz de tiempos de permanencia por zona y tabla de auditoría cronológica de recorridos con badges temáticos y estados vacíos asistidos.
- [x] Rediseño Ultra-Intuitivo y Humano de Indicadores Operativos (`/indicadores/`): En respuesta a la sobrecarga cognitiva reportada ("ESTA COMPLEJA DE ENTENDER"), se eliminó toda la jerga técnica (sin "Dijkstra", sin "HOG", sin "aristas", sin contradicciones matemáticas como 100% con 0 rutas). Se implementó un diseño limpio y directo para el personal y gerencia del restaurante con:
  1. 3 Tarjetas KPI Claras: Viajes realizados hoy (directos vs desvíos), Estado de zonas (cuántas zonas lentas hay) y Mesas ocupadas (disponibles vs ocupadas).
  2. Semáforo de Zonas: Lista visual con semáforo claro (🟢 Verde = Rápido/Libre, 🟡 Amarillo = Tráfico moderado, 🔴 Rojo = Zona lenta con demora).
  3. Resumen de Viajes y Tareas: Estado vacío amigable y barras legibles de entregas de platos vs retiro de vajilla.
  4. Historial Reciente de Viajes: Feed narrativo de lenguaje natural (ej: "Cocina hacia Mesa 03 · Entrega de comida · Solicitado por admin").
- [x] Rediseño Minimalista y Despejado del Panel Principal (`/panel/`): En respuesta a la sobrecarga de elementos reportada en audio ("tiene muchas cosas cargado el panel principal"), se eliminaron las redundancias críticas:
  1. Supresión del Hero Banner sobredimensionado y de las 5 cajas gigantes de accesos rápidos que duplicaban el menú del sidebar.
  2. Implementación de cabecera ejecutiva limpia con botón directo de acción rápida (`+ Nueva ruta →` o `Ver indicadores →`) y estado en vivo.
  3. 4 Tarjetas KPI Claras y Esenciales: Mesas ocupadas (libres vs ocupadas), Viajes atendidos (hoy), Tráfico en pasillos (alertas de demora vs despejado) y Afluencia de comensales detectados.
  4. Dos Paneles Equilibrados y Respirables: Semáforo directo de pasillos con tiempos promedio de permanencia por zona vs Feed narrativo de recorridos recientes y acceso sutil a Cámara Chef OpenCV.
- [x] Optimización Single-Screen Viewport de Landing / Inicio (`/`): Corrección del desbordamiento vertical y scroll involuntario que causaba un espacio vacío residual al rodar hacia abajo. Ajustado el contenedor a `height: 100vh; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden;` con distribución armónica (navbar fija arriba, titular y características centrados, footer integrado al pie sin barras de desplazamiento).
- [x] Sincronización de Estáticos y Reinicio de Servidor: Recompilados los archivos estáticos (`collectstatic`) y reiniciado el proceso en puerto 8000 para despacho inmediato.
- [x] Sincronización y Despliegue en GitHub: Confirmados y enviados todos los cambios funcionales, visuales, microservicios y plantillas al repositorio remoto (`https://github.com/Josue2004exe/OptiFlow_Dining`) en la rama `main` (commit `36ba59b`).
- [x] Fase 1 Implementada (Núcleo Operativo, Rutas y Sincronización en Vivo):
  1. **Sincronización de mesas en Rutas (`/rutas/`):** Inyectado `tables_map_json` desde `page_context` a `routes.html` (`#tables-state-data`). El mapa del salón ahora renderiza en vivo los estados reales de cada mesa (verde Disponible, azul Activa, naranja Ocupada) igual que en el plano topológico.
  2. **Interactividad y Explicación en Señales Rojas (`!`):** Los nodos de congestión en el SVG ahora son interactivos con anillo de pulso animado. Al hacer clic, se abre una ventana modal explicativa (`#congestion-modal`) con diagnóstico de zona, causas técnicas (prevención de demoras/colisiones) y botón directo para recalcular el desvío.
  3. **Mapa de Calor Coherente con Sectores:** En `/saturacion/`, las zonas ahora están claramente etiquetadas con su sector físico (Zona A: Salón Jardín · Mesas 01/05; Zona B: Pasillo Central · Mesas 02/06; Zona C: Salón Terraza · Mesas 03/04/07/08), con umbrales legibles ($\le 2$ min Normal, $2.1-4$ min Moderada, $>4$ min Crítica) y sincronización automática del selector al editar minutos.
  4. **Reactividad Instantánea Cero F5:** Las nuevas rutas calculadas se insertan de inmediato en la tabla de consultas recientes con animación suave (`rowSlideIn`). Al marcar una tarea como finalizada, la píldora de estado cambia a "Finalizada" en tiempo real sin recargar la página. Al guardar zonas de saturación, el mapa de calor y alertas se actualizan en el DOM sin `location.reload()`.
  5. **Mensajería Asistida en 3 Partes:** `#route-feedback` modernizado con diseño Dark Hospitality, iconos temáticos y mensajes estructurados (Qué ocurrió, Por qué, Qué acción tomar) para rutas directas, desvíos y prevención de errores.

- [x] Fase 2 Implementada (Gestión de Cuentas, Perfil, Asignación de Meseros y Notificaciones Admin):
  1. **Perfil de Usuario Dedicado (`/perfil/`):** Vista de gestión de cuenta con tarjeta de identidad, avatar con gradiente, rol operativo, métricas de rendimiento y listado de actividad.
  2. **Validación Estricta de Registro:** Regex estricto en nombres y username previniendo caracteres no alfabéticos o cadenas cortas.
  3. **Sistema de Notificaciones Administrativas:** Modelo `AdminNotification` con registro automático al registrarse meseros, campana en topbar con contador badge y dropdown asíncrono para marcar como leídas.
  4. **Asignación de Rutas por Administración:** Campo `assigned_waiter` en `RouteConsultation`, selector en formulario de rutas para capitanes y administradores.
  5. **Atención de Tareas Asignadas para Meseros:** Banners en Dashboard y Rutas con botón `Atender ➔` y trazado instantáneo de la ruta.
  6. **Trazabilidad Completa en Actividad del Turno:** Atribución de autor y mesero asignado con badges temáticos.
  7. **Suite de Pruebas Ampliada:** 12 de 12 pruebas unitarias pasando al 100%.

- [x] Fase 3 Implementada (Propagación OpenCV-Dijkstra, AWS S3 y Optimización Táctil Móvil/Tablet):
  1. **Propagación Automática de OpenCV a Zonas y Dijkstra (Req 3 & 8):** El conteo de personas de `api_vision` actualiza dinámicamente los niveles de `Zone` (Normal, Moderada, Crítica). En `services/routing/main.py`, Dijkstra mapea las zonas críticas a sus nodos neurálgicos específicos (`1,2` para Zona A, `2,2` para Zona B, `3,2` para Zona C), permitiendo el desvío automático de meseros al evitar cuellos de botella.
  2. **Banner de Sincronización en Tiempo Real:** En [vision.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/vision.html), aviso visual instantáneo (`#vision-sync-alert`) alertando de la sincronización de pasillos y cómo Dijkstra esquivará las áreas saturadas.
  3. **Integración y Verificación de AWS S3 (Req 10):** Detección dinámica del bucket S3 en `api_vision` y `services.py`. Si está configurado, archiva la evidencia en la nube mostrando el key; si no está configurado, activa fallback local transparente con badge no invasivo (`#vision-s3-status`).
  4. **Optimización Táctil (Touch-First) Mobile y Tablet (Req 11):** Alturas y áreas táctiles universales de 44px (WCAG 2.5.5 / 2.5.8 Target Size), `touch-action: manipulation`, soporte para tablets en sala (iPad, Surface) y teléfonos móviles sin desbordamiento horizontal y con planos escalables.
  5. **Suite de Pruebas Ampliada al 100%:** 13 de 13 pruebas unitarias aprobadas (`OK`), incluyendo propagación de visión a zonas y verificación de desvío Dijkstra.

- [x] Refinamiento Visual en Tarjeta de Perfil y Métricas 2x2:
  1. **Cuadrícula Equilibrada de Métricas:** Reemplazada la clase restrictiva de 4 columnas por `.profile-kpi-grid` en distribución armónica de 2x2 con tarjetas amplias (`.profile-kpi-card`), eliminando la deformación en píldora vertical y el truncamiento de textos ("Rutas Atendidas", "Asignadas por Admin", etc.).
  2. **Nombre y Jerarquía Visual:** Eliminada la etiqueta "No especificado" para el usuario administrador, mostrando formalmente `Administrador Principal` tanto en cabecera como en la ficha técnica.
  3. **Espaciado y Separación de Paneles:** Estandarizado a `gap: 14px` en `.profile-left-col` y `.profile-right-col`, suprimiendo márgenes dobles (`margin-bottom: 0`).
  4. **Separación Equilibrada de Widgets de Métricas:** Configurado `row-gap: 12px; column-gap: 12px; margin-top: 14px;` en `.profile-kpi-grid` con fondo contrastado y elevación en `.profile-kpi-card`, garantizando distribución armónica sin separaciones excesivas ni bordes solapados.

- [x] Configuración de Logotipo Oficial en Login (Isotipo Espiral Estático):
  1. **Isotipo Oficial en Login:** Integrado exactamente el logo de la segunda imagen (`optiflow_icon.png`, espiral con tenedores) tanto en la cabecera como en la tarjeta de acceso de [login.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/login.html) y [register.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/register.html).
  2. **Sin Movimiento en Login:** Inhabilitada la rotación en el login (`animation: none !important; transform: none !important;`) para mantenerlo estático y sin giros.
  3. **Rotación Activa en el Sistema General:** Conservada la rotación suave (`brandLogoSlowSpin 26s`) para el logo del topbar, sidebar y módulos del salón.
  4. **Caché Actualizada:** Configurado `?v=20261026_logo_spiral_static` en `public.html` y compilado `collectstatic`.

- [x] Integración de Logotipo Oficial en Radar de Órbitas de Landing (`/`):
  1. **Isotipo Oficial en Órbita:** Reemplazado el carácter genérico `◎` por el isotipo oficial `optiflow_icon.png` dentro de `.orbit-center` en [landing.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/landing.html).
  2. **Estático y sin Giros (92px exactos):** Configurado `.landing-orbit-logo` con escala de 92px, contenedor flex vertical con `gap: 12px`, margen superior de 10px en `OPTIFLOW` sin solapamiento, inline style prioritario y `animation: none !important; transform: none !important;`.
  3. **Texto de Marca Preservado:** Mantenida la leyenda `<small>OPTIFLOW</small>` con tipografía Montserrat geométrica justo debajo del logo.


- [x] Sincronización y Despliegue en GitHub (Commit `3d7c68d`):
  - Subidos todos los cambios al repositorio remoto (`https://github.com/Josue2004exe/OptiFlow_Dining`) en la rama `main`:
    1. Fases 1 a 3 (sincronización OpenCV-Dijkstra, AWS S3, touch-first mobile/tablet).
    2. Módulo de perfil de usuario (`/perfil/`), notificaciones admin y asignación de rutas a meseros.
    3. Calibración visual completa del logotipo en Landing (92px estático sin solapamiento con el nombre) y Login.

- [x] Fase 1 Implementada (Correcciones de UI/UX, Alertas y Contraseñas):
  1. **Alerta de Congestión y Evidencia OpenCV:** Eliminado el parpadeo excesivo del anillo pulsante SVG (`congestion-pulse-ring`) reemplazándolo por un halo estático y nítido. Renovado el modal explicativo (`#congestion-modal`) incorporando banner de estado crítico, diagnóstico claro y la tarjeta de evidencia fotográfica procesada por OpenCV (`latest_vision_capture.jpg`) con división zonal y recuadros de personas detectadas.
  2. **Conmutador de Visualización de Contraseñas:** Resuelto el conflicto de listeners duplicados en [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js) que revertían inmediatamente el tipo de input y destruían el icono. Implementado toggle unificado y robusto con alternancia dinámica de icono SVG (ojo abierto vs ojo tachado), prevención de envío accidental y margen derecho seguro (`padding-right: 48px !important;`).
  3. **Avisos Administrativos Desplegables:** Agregada regla `.notif-dropdown.is-hidden { display: none !important; }` en [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css) para asegurar que el centro de notificaciones permanezca cerrado por defecto y se despliegue únicamente al pulsar la campana o ante nuevos avisos.
  4. **Persistencia de Captura de Visión:** Creado endpoint `/api/vision/ultima/` en [urls.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/urls.py), inyección de contexto en [routes.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/routes.html) y actualización automática de `latest_vision_capture.jpg` al procesar imágenes en `api_vision`.
  5. **Verificación Integral:** 13 de 13 pruebas unitarias aprobadas al 100% (`OK`) y estáticos recompilados con `collectstatic`.

- [x] Fase 2 Implementada (Rutas Seguras, Alerta Urgente al Mesero y Validación Estricta de Permanencia en Zonas):
  1. **Despacho Automático de Ruta Segura (Req 3 & 8):** Si una ruta asignada a un mesero por Capitanía/Admin presenta congestión, el backend recalcula y persiste de forma automática la trayectoria alternativa libre de obstáculos (`avoid_congestion=True`) vía Dijkstra.
  2. **Trazado Óptimo en un Clic:** El botón `Atender ➔` del mesero en [routes.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/routes.html) detecta la tarea recalculada y traza directamente el recorrido seguro en el mapa CAD del salón con feedback toast y badge `🛡️ Ruta Segura`.
  3. **Alertas Urgentes de Servicio para Meseros:** Rediseñado el banner en [dashboard.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/dashboard.html) con distintivo de alta prioridad (`🔴 ALERTA DE SERVICIO · ATENCIÓN INMEDIATA`), caja de tareas en [routes.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/routes.html), y píldora flotante persistente en el topbar de [base.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/base.html) (`.waiter-urgent-topbar-pill` con punto pulsante) para que el mesero se entere de inmediato desde cualquier pantalla.
  4. **Validación Estricta de Umbrales de Permanencia (Req 8):** Aplicada validación matemática estricta en backend (`api_update_zone` en [views.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views.py)) y frontend ([app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js)):
     - Normal: permanencia $\le 2.0$ min.
     - Moderada: permanencia entre $2.1$ y $4.0$ min.
     - Crítica: permanencia $> 4.0$ min.
     - Rechazo inmediato con HTTP 400 y mensaje de error descriptivo ante combinaciones incoherentes.
  5. **Suite de Pruebas Ampliada:** 15 de 15 pruebas unitarias aprobadas al 100% (`OK`) y estáticos compilados con `collectstatic`.

- [x] Fase 3 Implementada (Rol Especializado «Jefe de Meseros» y Blindaje de Perfiles - Req 5 & 7):
  1. **Rol Jefe de Meseros (Capitán):** Configurado `Profile.ROLE_CHOICES` con `Jefe de meseros (Capitán)`. Enfoque operativo orientado a la gestión de mesas y despacho de rutas de salón.
  2. **Edición Libre de Datos Personales:** Implementada la actualización de nombre, apellido y correo en [profile.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/profile.html) con validación y confirmación en [views.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views.py) (`profile_view`).
  3. **Blindaje de Auto-Asignación de Roles:** Ningún usuario puede alterar su propio rol en los formularios de perfil (campo protegido y sanitizado).
  4. **Gestión de Personal y Promoción Blindada (Admin):** Creada la API `api_update_user_role` en [views.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views.py) y [urls.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/urls.py) con panel administrativo exclusivo para promover meseros a Capitanes / Jefes de meseros.
  5. **Doble Blindaje de Seguridad:** Prohibición estricta de auto-degradación de administradores y bloqueo total ante intentos de degradar a otros superusuarios.
  6. **Suite de Pruebas Ampliada:** 18 de 18 pruebas unitarias aprobadas al 100% (`OK`).

- [x] Fase 4 Implementada (Creación, Desplazamiento y Unificación de Mesas CAD - Req 6):
  1. **Creación Dinámica de Mesas CAD:** En [layout.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/layout.py) y [views.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views.py) (`api_create_table`), los Administradores pueden registrar nuevas mesas con código, etiqueta, capacidad (2/4/6/8 comensales), zona y coordenadas de cuadrícula (nodo X,Y).
  2. **Reubicación de Mesas en la Cuadrícula:** Creada función `move_table` y API `api_move_table` permitiendo cambiar la posición de cualquier mesa y su zona en el plano vectorial.
  3. **Unificación de Mesas para Grupos Grandes:** Función `unify_tables` y endpoint `api_unify_tables` para consolidar dos o más mesas contiguas con suma automática de capacidades y etiqueta unificada (ej. Mesa 01+02 Grupo Especial).
  4. **Sincronización en Tiempo Real con Dijkstra:** En [main.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/services/routing/main.py), el microservicio de ruteo recarga dinámicamente la topología del salón en cada consulta, haciendo que las mesas nuevas, movidas o unificadas sean inmediatamente navegables.
  5. **Modales y Controles Visuales CAD:** En [layout.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/layout.html), [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js) y [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css), implementados modales oscuros con backdrop blur para creación, unificación interactiva y reubicación sin recargas forzadas.
  6. **Suite de Pruebas Ampliada:** 20 de 20 pruebas unitarias aprobadas al 100% (`OK`).

- [x] Fase 5 Implementada (Conectividad Multi-dispositivo en Red Local Móvil/Tablet y Verificación Final - Req 9):
  1. **Detección Dinámica de IP Local y Binding Abierto:** En `settings.py`, configuración de `ALLOWED_HOSTS = ['*']` y resolución automática de IP local vía `socket.gethostbyname_ex` para incorporar orígenes confiables en `CSRF_TRUSTED_ORIGINS`.
  2. **Lanzadores Multi-dispositivo:** Actualizados `iniciar.cmd`, `iniciar.ps1` y `COMANDOS_INICIO.txt` enlazando el servidor Django a `0.0.0.0:8000` para escuchar conexiones entrantes de cualquier smartphone o tablet en la misma red Wi-Fi local.
  3. **Inyección de URL de Red Local en Vistas:** En `web/core/views.py` (`page_context`), inyección global de `lan_ip` y `lan_url` (`http://<IP_LOCAL>:8000`).
  4. **Acceso Rápido y Código QR en Topbar:** En `web/templates/base.html`, [app.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/app.js) y [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css), botón `.lan-topbar-pill` (`📱 Móvil / Tablet`) y modal interactivo `#modal-lan-connect` con código QR renderizado en vivo para escaneo inmediato con la cámara de cualquier dispositivo móvil y botón de copiado de URL con feedback visual.
  5. **Verificación Automatizada Multi-dispositivo:** Creada prueba unitaria `test_lan_multidevice_context_and_settings` en `web/core/tests.py` validando la inyección de contexto, headers User-Agent móviles y presencia de modales de interconexión.
  6. **Suite Completa Aprobada:** 21 de 21 pruebas unitarias aprobadas al 100% (`OK`).

- [x] Auditoría Exhaustiva ECC y Mitigación de Vulnerabilidades Críticas (Prioridad 1):
  1. **Blindaje de Hosts y Seguridad de Red (`settings.py`):** Removido comodín `'*'` de `ALLOWED_HOSTS` previniendo ataques de *Host Header Poisoning* y *DNS Rebinding*; añadidos hosts locales explícitos (`127.0.0.1`, `localhost`, `0.0.0.0`, `[::1]`) y resolución de IPs de red local sin excepciones silenciosas.
  2. **Configuración de Logging Empresarial (`settings.py`):** Integrado diccionario estructurado `LOGGING` con formateadores estándar y manejador de consola.
  3. **Atomicidad y Transaccionalidad CAD (`layout.py`):** Reemplazada la escritura en `salon.json` con reemplazo atómico seguro (`tempfile.NamedTemporaryFile` + `fsync` + `os.replace`), eliminando el riesgo de truncamiento a 0 bytes y corrupción por concurrencia. Operaciones `add_table` y `unify_tables` blindadas con `transaction.atomic()`.
  4. **Liberación del Event Loop en Visión (`services/vision/main.py`):** Delegación de la inferencia síncrona CPU-bound de OpenCV HOG a worker threadpool vía `await asyncio.to_thread(analyze_bytes, raw)`, manteniendo el event loop de FastAPI 100% no bloqueante.
  5. **Resiliencia y Logging en Ruteo (`services/routing/main.py`):** Incorporado `logging.getLogger('routing')` emitiendo advertencias descriptivas ante fallos de lectura de topología dinámica.
  6. **Suite de Pruebas Unitarias Normalizada (`test_routing.py` & `tests.py`):** Suite completa de Django (21/21 tests `OK`) y microservicio de ruteo (3/3 tests `OK`) aprobados al 100%.

- [x] Nuevas Mejoras Operativas y CAD (Google Docs `1uHiRLsUjMB-CbFEfsNDCjfaFEMPdzbgf`):
  1. **Salón CAD & Prevención de Colisiones (`layout.py` & `views.py`):** Detección estricta de colisiones espaciales (`_check_collision`) impidiendo solapamientos entre mesas o sobre la cocina/acceso, retornando HTTP 400 descriptivo.
  2. **Auto-Expansión Dinámica del Salón (`layout.py`):** Si una mesa se ubica en coordenadas mayores al tamaño actual, `columns` y `rows` se expanden automáticamente en `salon.json` evitando que desaparezca del SVG. Endpoint `api_update_layout_dimensions` y modal `#modal-dimensions` para calibración manual por Gerencia/Admin.
  3. **Desunificación / Separación de Mesas (`layout.py`, `views.py`, `layout.html`, `app.js`):** `unify_tables` ahora almacena `original_tables`; creada función `separate_table` y endpoint `api_separate_table`. Botón `⤢ Separar` en tarjetas de mesas combinadas que restaura con un clic las mesas originales a sus posiciones, capacidades y zonas de origen.
  4. **Reubicación Inteligente por Zona:** Función `suggest_zone_coordinates` para sugerir automáticamente el primer nodo disponible dentro de las columnas asignadas a una zona.
  5. **Ruteo Dijkstra sin Cruzar sobre Mesas (`services/routing/main.py`):** Las mesas intermedias distintas a la mesa de destino se tratan automáticamente como obstáculos físicos, obligando a los meseros a transitar exclusivamente por pasillos libres.
  6. **Matriz Estricta de Roles Operativos (`base.html`, `views.py`):**
     - *Jefe de Meseros (`capitan`):* Panel principal, Rutas, Plano y mesas, Indicadores y Perfil. Bloqueado de Saturación del salón, Visión OpenCV y cambio de roles.
     - *Gerente General (`gerente`):* Acceso total a Panel, Rutas, Saturación, Indicadores, Plano y Visión. Bloqueado estrictamente de cambiar roles de empleados en `/perfil/`.
     - *Administrador (`admin`):* Acceso integral con gestión de roles de personal.
  7. **UX Móvil y Animación Suave de Alertas SVG (`app.css`, `app.js`):**
     - Corregido el salto brusco en hover del icono de alerta SVG con `transform-box: fill-box; transform-origin: center;` y animación suave `@keyframes alertGlowPulse`.
     - Hitbox táctil invisible de 28px de radio (56px diámetro) con eventos `pointerdown`/`touchstart` para apertura instantánea del modal en móviles y tablets.
     - Viewport responsive del plano en pantallas pequeñas (`min-width: 580px; overflow-x: auto;`) manteniendo legibilidad sin compresión excesiva.
  8. **Ensamble OpenCV para Comensales Sentados (`services/vision/main.py`):**
     - Multi-modelo combinando `haarcascade_upperbody.xml` (torsos sentados) + `haarcascade_frontalface_default.xml` + `haarcascade_profileface.xml` + HOG descriptor + CLAHE para luz de salón + Non-Maximum Suppression (`cv2.dnn.NMSBoxes`).
     - Detección exitosa comprobada en fotografías reales de salón con comensales sentados a mesas.
  9. **Cloud AWS S3 & URLs Prefirmadas (`services.py`, `views.py`, `vision.html`):** Función `get_s3_presigned_url` para generar enlaces temporales seguros de 1 hora y enlace cliqueable `☁️ Ver en S3 ↗` en el historial de capturas.
  10. **Suite Completa Aprobada:** 24 de 24 pruebas unitarias Django (`OK`) y 4 de 4 pruebas de ruteo Dijkstra (`OK`), 0 errores en Pyright.

## Estado de la Entrega y Sistema Operativo
- Las 5 Fases Iniciales y las **10 Nuevas Mejoras Operativas** están **100% COMPLETADAS Y VERIFICADAS**.
- Repositorio GitHub con rama `main` operativa y sincronizada con la cuenta `Sofia12-cer`.
- Suite de pruebas: **24/24 pruebas unitarias Django (`OK`) + 4/4 pruebas de microservicio Dijkstra (`OK`)**.





- [x] Auditoría Estructural Integral y 4 Nuevas Mejoras Operativas (Google Docs `1uHiRLsUjMB-CbFEfsNDCjfaFEMPdzbgf` · 2026-10-31):
  1. **Muro Estricto de Dimensiones y Escalado Dinámico del Plano SVG:**
     - En [floor_plan.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/modules/floor_plan.js), el lienzo SVG calcula dinámicamente `viewBox`, pasillos, orígenes, sectores de Zonas A/B/C y sello `RED CAD X×Y` en función de `columns × rows`.
     - En [layout.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/layout.py), eliminada la auto-expansión silenciosa; `_check_bounds` aplica las dimensiones actuales como muro estricto rechazando con `HTTP 400` cualquier mesa fuera de `0..columns-1` o `0..rows-1`.
  2. **Reubicación Física Automática al Cambiar de Zona y Alerta de Zona Llena:**
     - En [layout.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/layout.py) (`move_table`, `suggest_zone_coordinates`, `compute_zones_for_columns`) y [cad_tables.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/modules/cad_tables.js), cambiar el sector de una mesa la traslada automáticamente en el mapa a una celda disponible de la nueva zona; si la zona no dispone de espacio libre dentro de las dimensiones actuales, muestra alerta clara (`HTTP 400` + `.cad-inline-error`).
  3. **Rutas Dijkstra Estrictamente Dentro de las Dimensiones del Salón:**
     - En [main.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/services/routing/main.py), validados `_in_bounds`, nodos neurálgicos dinámicos por zona y preservación estricta de `other_tables` como obstáculos para que ningún recorrido ni desvío salga del marco `columns × rows` ni pise mesas intermedias.
  4. **Ciclo Completo de Tareas Asignadas a Meseros y Notificación al Supervisor:**
     - En [routing.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/modules/routing.js) y [routes.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/routes.html), pulsar `Atender ➔` traza el `data-path` guardado sin duplicar registros en base de datos, e incorpora botón directo `✓ Finalizar`.
     - Al finalizar la tarea ([api_routing.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views/api_routing.py)), se retira al instante la alerta del mesero y la píldora urgente del topbar, el estado cambia de `Pendiente` a `Finalizada` en tiempo real, y se emite una notificación `AdminNotification` directa (`recipient`) al supervisor (**Capitán**, **Gerente** o **Administrador**) que asignó la ruta, habilitando la campana `🔔` también para `gerente`.
  5. **Auditoría Arquitectónica, Modularización (<350 líneas) y Reorganización de Carpetas:**
     - Desacoplado el monolito `web/core/views.py` (999 líneas) en el paquete modular `web/core/views/` (`helpers.py`, `auth_profile.py`, `pages.py`, `api_routing.py`, `api_cad_vision.py`).
     - Desacoplado el monolito `web/static/js/app.js` (1,535 líneas) en `web/static/js/modules/` (`core.js`, `floor_plan.js`, `routing.js`, `cad_tables.js`, `vision_zones.js`) + `app.js`.
     - Reorganización limpia sin borrados destructivos (`git mv`): guías movidas a `docs/guias/`, prototipo autónomo a `docs/preview/`, 24 bocetos gráficos fuera de runtime archivados en `docs/assets_archive/` (dejando solo los 5 activos de producción en `web/static/img/`), y creados `.agents/AGENTS.md` y `docs/ARQUITECTURA.md`.
  6. **Verificación Automatizada Integral:** **26/26 pruebas unitarias Django (`OK`)**, **5/5 pruebas unitarias Dijkstra (`OK`)**, `collectstatic` compilado y **0 errores en Pyright**.

- [x] Refinamiento Ejecutivo Split-Screen Glassmorphism en Login y Registro (`2026-10-31`):
  - En [login.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/login.html), [register.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/register.html), [public.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/public.html), [forms.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/forms.py) y [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css), se equilibró el contenedor `.auth-split-inner` (`1240px`/`1280px` centrado con `100dvh`), se aplicó glassmorphism real (`backdrop-filter: blur(22px) saturate(140%)`) con haz especular naranja superior, iconos SVG reactivos en inputs, atributos nativos de `autocomplete`/`spellcheck` y eliminación de enlaces duplicados de registro/acceso conservando intactos el logotipo espiral e identidad cromática azul noche + naranja.

- [x] Pulido Visual de Emblema Auth, Espacio Interno en Rutas, Modal QR Directo a `/login/` y Responsive Móvil Integral (`2026-10-31`):
  - **Logo cubriendo el aro naranja:** En [login.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/login.html), [register.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/register.html) y [app.css](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/css/app.css), se eliminó el borde circular naranja exterior y el espacio vacío, expandiendo el isotipo espiral a `72×72px` (`100%`).
  - **Espacio y selectores en `Rutas de servicio`:** Aplicado `color-scheme: dark`, selectores azul noche (`#0e1c34`), alturas simétricas (`align-items: stretch`) y centrado elástico de `.map-surface`.
  - **Modal QR limpio directo a `/login/`:** En [helpers.py](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/core/views/helpers.py) y [base.html](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/templates/base.html), retirado el bloque superior de dirección/copiar enlace y configurado `lan_url` con ruta directa `http://<IP_LAN>:8000/login/`.
  - **Responsive integral para Smartphone (`< 720px`):** Corregido topbar móvil sin desborde (`☰` blanco, botón QR compacto, avatar y campana dentro de `100vw`), backdrop en menú lateral ([core.js](file:///c:/Users/Flavio/Desktop/H4CK/Flavio/OptiFlow_Dining/web/static/js/modules/core.js)), blindaje `minmax(0, 1fr)` en `/perfil/`, filas apiladas en `/panel/` y tarjeta inmediata en Login/Registro móvil.
