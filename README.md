# OptiFlow Dining · Aplicación web

Proyecto académico de **Construcción de Software**, construido sobre los documentos de requerimientos, Scrum y prototipo de OptiFlow Dining. Esta entrega contiene una aplicación **Django**, dos microservicios **FastAPI**, análisis de fotografías con **OpenCV** e integración **opcional** con **Amazon S3**.

> **Importante:** es un MVP funcional/de demostración, **no** un sistema desplegado en AWS ni una solución de visión artificial validada para estimar ocupación real del restaurante.

## 1. Ejecutar en Windows

Necesitas **Python 3.11 o superior**. Al instalarlo, marca «Add python.exe to PATH».

Da doble clic a `iniciar.cmd`. La primera vez instala lo necesario y puede tardar varios minutos; después abre la aplicación en el navegador. Para detenerla, cierra las tres ventanas de los servicios. Sin claves de AWS, S3 queda desactivado y las fotos se guardan solo en tu equipo. Para abrirla desde un móvil en la misma red, escanea el QR de la aplicación y, si Windows lo pregunta, permite el acceso a Python. La ventana del lanzador muestra los usuarios de prueba `mesero_demo`, `capitan_demo` y `gerente_demo` con su contraseña, generada al azar en cada equipo; el análisis de fotos requiere `gerente_demo`.

Abre **http://localhost:8000**. Presiona **«Crear cuenta»** y regístrate. Un usuario nuevo tiene rol **Mesero / Runner**. Luego inicia sesión, entra a «Rutas de servicio», selecciona «Zona de cocina» y «Mesa 08» y calcula la ruta. Verás el mensaje de congestión; pulsa **«Recalcular ruta»** y después **«Finalizar tarea»**. El resultado queda guardado en la base de datos.

### Probar los otros perfiles

Por seguridad, el registro público solo crea usuarios **Mesero**. Para administrar los perfiles, primero crea un superusuario:

```bash
.venv\Scripts\python web\manage.py createsuperuser
```

Accede a `http://localhost:8000/admin/`, abre **Profiles**, selecciona el usuario y cambia el rol a **Capitán de meseros** o **Gerente general**. También puedes habilitar usuarios demo **solo en un entorno local** con `ENABLE_DEMO_USERS=1` y una clave `DEMO_PASSWORD` robusta en `.env` (mínimo 12 caracteres); reinicia la app. Se crearán `mesero_demo`, `capitan_demo` y `gerente_demo` con la misma contraseña configurada por ti. No habilites cuentas de demostración en producción.

## 2. Módulos disponibles

| Vista / función | Tecnología y comportamiento | Roles |
|---|---|---|
| Registro y login | Django Auth, sesiones protegidas, formularios, contraseñas hash y CSRF | Público |
| Panel principal | Estado del salón y contadores persistidos | Todos |
| M1 Plano y mesas | Editor CAD en cuadrícula (crear, mover, unificar, separar mesas y dimensiones del salón) y gestión de estados (`disponible/activa/ocupada`) | Estados: Capitán, Gerente, Admin · Edición CAD: Gerente, Admin |
| M2 Rutas | Motor Dijkstra en microservicio FastAPI: consulta, detección de nodos congestionados, desvío óptimo, asignación a meseros y cierre con notificación al supervisor | Mesero, Capitán, Gerente, Admin |
| M3 Saturación | Modificación de nivel y permanencia, alertas cuando la zona crítica supera 4 minutos | Gerente, Admin |
| M3 Indicadores | Conteos reales de rutas consultadas, recalculadas, finalizadas y zonas críticas | Capitán, Gerente, Admin |
| OpenCV | Conteo de personas (sentadas, de pie, de espaldas o en ángulo) con OpenCV DNN y el modelo YOLOX-S de OpenCV Zoo en fotografía JPEG/PNG/WebP, división en tres sectores y propagación automática de afluencia a las zonas para desvío en Dijkstra | Gerente, Admin |
| AWS S3 | Resguardo privado opcional de fotografías cuando se configura un bucket e identidad IAM | Gerente, Admin |

### Límites de esta iteración

- El **plano es esquemático** con un **editor CAD en cuadrícula** (`columns × rows`) con muros dimensionales estrictos, detección de colisiones, reubicación automática por zona y fusión/separación de mesas.
- El **ruteo** utiliza una red de pasillos adaptable (`columns × rows`), no sensores físicos ni una representación milimétrica del restaurante.
- Los indicadores reflejan **registros realmente almacenados**, no métricas inventadas. Los tiempos físicos de desplazamiento, cruces reales y alertas automáticas por sensores necesitarían fuentes de datos adicionales.
- **OpenCV DNN + YOLOX-S** (`services/vision/models/object_detection_yolox_2022nov.onnx`, OpenCV Zoo, Apache-2.0) se ejecuta con `cv2.dnn`, sin otras librerías de IA. Analiza la foto completa y un mosaico de recortes solapados para no perder personas lejanas. El conteo es una estimación: puede omitir personas muy tapadas o fuera de cuadro. No se usa reconocimiento facial. Si falta el modelo ONNX, el servicio vuelve al ensamble anterior (MobileNet-SSD + Haar + HOG). La estimación visual **actualiza automáticamente** los niveles de saturación de las zonas para que el motor Dijkstra evite pasillos congestionados.
- El diseño es responsive y sigue la identidad azul marino/naranja del prototipo suministrado.

## 3. Arquitectura de microservicios

```mermaid
flowchart LR
    U[Usuario en navegador] -->|HTTPS en producción| D[Django web + autenticación]
    D --> DB[(SQLite local / RDS PostgreSQL)]
    D -->|REST interno| R[FastAPI: motor de rutas]
    D -->|REST interno + foto| V[FastAPI: OpenCV]
    D -.->|opcional: boto3 + IAM| S3[(Amazon S3 privado)]
```

Servicios:

- **web**: Django + Django Templates + JS/CSS; REST JSON propio, validación, base de datos, autenticación, roles y AWS SDK (`8000`).
- **routing**: FastAPI independiente; `POST /route`, `GET /layout`, `GET /health` (`8001`, no expuesto públicamente).
- **vision**: FastAPI + OpenCV DNN (YOLOX-S); `POST /analyze` (foto con imagen anotada), `POST /detect` (fotograma de la cámara en vivo: solo cajas y conteo; `?mode=rapido|normal|preciso`, de más fluido a más preciso), `GET /health` (`8002`, no expuesto públicamente).
- **base de datos**: SQLite local para desarrollo. Puede migrarse a PostgreSQL mediante `DATABASE_URL` para producción.

La carpeta `config/salon.json` define las coordenadas iniciales, las mesas y nodos congestionados. **Django es la única fuente de verdad del plano**: lo edita (crear, mover, unificar o separar mesas) y lo envía en cada petición `POST /route` (campo `layout`), así el microservicio de rutas siempre calcula sobre el plano vigente aunque no comparta disco con Django.

## 4. Usar AWS en producción

Se proporciona integración de **Amazon S3**; el programa **no crea cuentas, servidores ni recursos cloud por sí solo**. Para probar en AWS:

1. Crea un bucket S3 con acceso público bloqueado (p. ej. `optiflow-evidencias-privadas`) y cifrado habilitado.
2. Crea una instancia **EC2**, instala Python y asigna un **rol IAM** a la instancia, con permiso `s3:PutObject` **limitado** a `arn:aws:s3:::TU_BUCKET/optiflow/analisis/*`.
3. Clona/copia este proyecto al servidor, genera `.env` y configura `AWS_S3_BUCKET=TU_BUCKET`, `AWS_REGION=us-east-1` (o la región elegida).
4. Configura `ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` y `DJANGO_SECRET_KEY` correctamente. Sitúa la app detrás de un proxy/ALB con **HTTPS** y activa `DJANGO_SECURE_SSL_REDIRECT=1`. No expongas los microservicios a Internet.
5. Para persistencia escalable, crea **Amazon RDS PostgreSQL** con acceso privado y define `DATABASE_URL=postgresql://usuario:contraseña@host:5432/basedatos` en tu gestor de secretos / entorno. Haz `python manage.py migrate` al cambiar la base de datos.

No coloques `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en archivos versionados. El SDK `boto3` usa automáticamente credenciales temporales del rol IAM de EC2. La foto original solo se almacena en S3 si está configurado `AWS_S3_BUCKET`; Django guarda únicamente los metadatos, y la respuesta anotada se envía al navegador. Se recomienda obtener consentimiento antes de procesar fotografías de personas y definir políticas de retención en S3.

## 5. Ejecución manual (Linux, macOS o sin el lanzador)

Con Python 3.11 o superior, desde el directorio raíz:

```bash
python web/generate_env.py
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r web/requirements.txt
python -m pip install -r services/routing/requirements.txt
python -m pip install -r services/vision/requirements.txt
```

Abre **tres terminales**, todas con el entorno virtual activado y situadas en `OptiFlow_Dining`:

```bash
# Terminal 1 (rutas)
python -m uvicorn services.routing.main:app --port 8001

# Terminal 2 (visión)
python -m uvicorn services.vision.main:app --port 8002

# Terminal 3 (web)
cd web
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

La variable `DATABASE_URL` permite PostgreSQL; de lo contrario Django crea SQLite local. Para configurar contraseñas secretas no se requiere un servicio externo.

## 6. Pruebas y validación

```bash
cd web
python manage.py test core
```

Se incluyen pruebas automáticas para registro, restricción de roles, recálculo y almacenamiento de consultas. Se pueden probar directamente las funciones de ruteo de `services/routing/test_routing.py` si tienes pytest. **Es necesario ejecutar estas pruebas completas en un entorno con Django y las dependencias instaladas**.

### Endpoints de ejemplo

```json
POST /api/rutas/
{"origin":"cocina","destination":"mesa08","task_type":"entrega","avoid_congestion":false}
```

Necesitas iniciar sesión y enviar la cookie de sesión y el token CSRF. En la interfaz web esto se gestiona automáticamente.

## 7. Estructura del proyecto

```text
OptiFlow_Dining/
  iniciar.cmd                Lanzador automático local en Windows (Django + 2 FastAPI)
  .env.example               Variables de entorno de ejemplo
  .gitignore                 Exclusión de entorno local, cachés y variables sensibles
  config/salon.json          Distribución y nodos del plano
  web/
    generate_env.py         Crea el archivo .env
    optiflow/               Configuración y settings de Django
    core/views/             Paquete modular de vistas HTML, permisos y APIs REST DRF
    core/tests/             Pruebas automatizadas por tema
    templates/              Plantillas: layouts/, auth/, pages/ y partials/
    static/
      css/
        app.css             Estilos globales y componentes principales
        operations.css      Pantallas operativas
      img/                  Activos gráficos activos de producción (logos y fondos)
      js/
        app.js              Lógica de cliente, formularios, rutas y OpenCV en Django
        modules/            Módulos JS desacoplados (core, floor_plan, routing, cad_tables, vision_zones)
  services/
    routing/                 Microservicio FastAPI de trayectorias
    vision/                  Microservicio FastAPI de análisis OpenCV
```

## 8. Relación con las entregas adjuntas

- **Requerimientos (Tarea 2):** se conservan los 3 módulos M1/M2/M3, los actores y la comunicación REST, y se implementan parcialmente las historias HU-01 a HU-05.
- **Scrum/Jira (Tarea 3):** la alerta de saturación contiene la **zona/nodo afectado y el tiempo de permanencia**, como recoge la modificación a HU-04.
- **Prototipo (Tarea 4):** se conserva la navegación *login → panel → tarea → ruta → congestión → alternativa → finalizar*, así como el código de color azul/naranja y las pantallas de saturación e indicadores.
- **Extensión solicitada en este encargo:** Django, registro de usuarios, microservicios, Amazon S3 y OpenCV.

**Aclaración:** Este paquete contiene el código fuente y la configuración de arranque. La ejecución integral y el despliegue en una cuenta AWS dependen del entorno y de las credenciales del usuario.
