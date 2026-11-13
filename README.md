# OptiFlow Dining

Plataforma web inteligente para la **gestión operativa de salón y rutas de servicio en restaurantes**. Combina un panel web en **Django**, cálculo de trayectorias óptimas con **Dijkstra (FastAPI)**, conteo de personas por visión artificial con **OpenCV** y respaldo opcional en **Amazon S3**.

---

## 🚀 Inicio rápido (Windows)

**Requisito:** Python **3.11 o superior** instalado con la opción *"Add python.exe to PATH"* marcada.

1. Haz doble clic en **`iniciar.cmd`**.
   > La primera vez crea el entorno virtual `.venv`, instala dependencias, prepara `.env`, aplica migraciones, compila archivos estáticos y levanta los 3 servicios automáticamente.
2. Espera unos segundos a que se abra tu navegador en **`http://127.0.0.1:8000`**.
3. **Acceso desde celular o tablet:** Conecta el móvil al mismo Wi-Fi, abre el botón de **QR** en la barra superior de la app y escanéalo *(permite el acceso a Python si Windows Firewall lo solicita)*.

> Para detener los 3 servicios a la vez, simplemente presiona `Ctrl + C` o cierra la consola de `iniciar.cmd`.

> [!NOTE]
> **¿Prefieres arrancar desde la terminal?** Con `.venv` ya creado, ejecuta todo el sistema en una sola consola con:
> ```powershell
> .\.venv\Scripts\python.exe web\run_local.py
> ```
> Más abajo tienes la guía completa en [**Comandos de ejecución**](#-comandos-de-ejecución).

---

## 👥 Roles y usuarios de prueba

Al iniciar con `ENABLE_DEMO_USERS=1` en `.env`, la consola de `iniciar.cmd` muestra automáticamente los usuarios demo y su contraseña (`DEMO_PASSWORD`):

| Usuario | Rol | Qué puede hacer |
|---|---|---|
| `mesero_demo` | **Mesero** | Ver panel, atender rutas urgentes asignadas, consultar trayectos y finalizar tareas. |
| `capitan_demo` | **Capitán** | Todo lo de Mesero + cambiar estado de mesas, asignar rutas a meseros y ver indicadores/avisos. |
| `gerente_demo` | **Gerente** | Todo lo de Capitán + editar el plano CAD (mesas/dimensiones), gestionar saturación de zonas y usar Cámara/Visión OpenCV + S3. |
| *(Superusuario)* | **Administrador** | Control total del sistema, incluida la gestión y promoción de roles del personal en `/perfil/`. |

* El registro público (`Crear cuenta`) crea cuentas con rol inicial **Mesero**.
* Para crear un administrador manualmente: `.venv\Scripts\python.exe web\manage.py createsuperuser`.

---

## 🧩 Módulos principales

| Módulo | Función |
|---|---|
| **Panel principal** | Resumen en tiempo real del salón: mesas libres/ocupadas, tráfico por zona, recorridos del día y afluencia detectada. |
| **Plano y mesas** | Mapa 2D interactivo tipo CAD (`columns × rows`) para cambiar estados (`disponible`, `activa`, `ocupada`) y crear, mover, unificar o separar mesas sin colisiones. |
| **Rutas de servicio** | Motor **Dijkstra** que calcula el camino más corto desde Cocina o Entrada hacia cualquier mesa, evitando pasillos saturados y mesas intermedias. |
| **Saturación** | Semáforo por zonas (`A` Jardín, `B` Central, `C` Terraza) según minutos de permanencia: Normal (`≤ 2 min`), Moderada (`2.1–4 min`) y Crítica (`> 4 min`). |
| **Indicadores** | Reporte claro de viajes realizados (directos vs. desvíos), entregas/retiros y tiempos por zona. |
| **Visión OpenCV** | Conteo de personas desde foto o cámara en vivo (**YOLOX-S** de OpenCV Zoo con respaldo MobileNet-SSD/Haar/HOG). Actualiza automáticamente la saturación de las zonas para que Dijkstra esquive cuellos de botella. |
| **Cloud AWS S3** | Resguardo opcional de las fotografías analizadas en un bucket S3 privado (si no hay claves AWS configuradas, opera en modo local sin bloquear la app). |

---

## 🏗️ Arquitectura

```mermaid
flowchart LR
    U[Navegador Web / Móvil] --> D[Django Web :8000]
    D --> DB[(SQLite / PostgreSQL)]
    D -->|REST| R[FastAPI Ruteo Dijkstra :8001]
    D -->|REST + Imagen| V[FastAPI Visión OpenCV :8002]
    D -.->|Opcional boto3| S3[(Amazon S3)]
```

* **`web/` (Puerto `8000`):** Interfaz, autenticación, roles, APIs REST (DRF), gestión del plano (`config/salon.json`) y conexión con AWS S3.
* **`services/routing/` (Puerto `8001`):** Microservicio FastAPI con algoritmo Dijkstra (`/route`, `/layout`, `/health`).
* **`services/vision/` (Puerto `8002`):** Microservicio FastAPI con OpenCV DNN (`/analyze`, `/detect`, `/health`).

---

## 📂 Estructura del proyecto

```text
OptiFlow_Dining/
├── iniciar.cmd                  # Arranca entorno, BD y los 3 servicios en Windows
├── .env.example                 # Plantilla de variables de entorno
├── config/
│   └── salon.json               # Dimensiones del salón, zonas, accesos y mesas
├── services/
│   ├── routing/                 # Microservicio de rutas Dijkstra + tests
│   └── vision/                  # Microservicio OpenCV + modelos + tests
└── web/
    ├── manage.py
    ├── generate_env.py          # Genera .env local con claves seguras
    ├── run_local.py             # Ejecuta y supervisa los 3 servicios en una sola consola
    ├── optiflow/                # Configuración global de Django (settings, urls)
    ├── core/                    # Modelos, layout CAD, servicios S3, views/ y tests/
    ├── templates/               # Vistas HTML (auth/, layouts/, pages/, partials/)
    └── static/                  # CSS, imágenes y módulos JS desacoplados
```

---

## 🧪 Pruebas automatizadas

Con el entorno virtual creado, ejecuta desde la raíz del proyecto:

```powershell
# 1. Suite principal de Django (61 pruebas)
.\.venv\Scripts\python.exe web\manage.py test core

# 2. Microservicio de Ruteo Dijkstra (7 pruebas)
.\.venv\Scripts\python.exe -m unittest discover -s services\routing -p "test_*.py"

# 3. Microservicio de Visión OpenCV (12 pruebas)
.\.venv\Scripts\python.exe -m unittest discover -s services\vision -p "test_*.py"
```

---

## 💻 Comandos de ejecución

> [!NOTE]
> Todos los comandos siguientes se ejecutan desde la **raíz del proyecto** (`OptiFlow_Dining/`). Si usas tu propio archivo `.env` (por ejemplo con claves AWS), cópialo en la raíz antes de iniciar.

### 1. Inicio automático en Windows (recomendado)

```cmd
.\iniciar.cmd
```

### 2. Instalación y arranque manual paso a paso (Windows PowerShell / CMD)

```powershell
# 1) Crear entorno virtual e instalar dependencias (solo la primera vez)
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r web\requirements.txt -r services\routing\requirements.txt -r services\vision\requirements.txt

# 2) Generar .env si no tienes uno propio (con usuarios demo habilitados)
.\.venv\Scripts\python.exe web\generate_env.py --demo

# 3) Compilar estáticos, aplicar migraciones y crear usuarios demo
.\.venv\Scripts\python.exe web\manage.py collectstatic --noinput
.\.venv\Scripts\python.exe web\manage.py migrate
.\.venv\Scripts\python.exe web\manage.py seed_demo

# 4) Levantar los 3 servicios en una sola consola
.\.venv\Scripts\python.exe web\run_local.py
```

* **Crear usuario administrador adicional:** `.\.venv\Scripts\python.exe web\manage.py createsuperuser`

### 3. Ejecución por separado (Linux / macOS / depuración)

Activa el entorno (`source .venv/bin/activate` en Linux/macOS o `.venv\Scripts\activate` en Windows) y abre 3 terminales en la raíz del proyecto:

```bash
# Terminal 1 - Microservicio de Ruteo Dijkstra (:8001)
python -m uvicorn services.routing.main:app --port 8001

# Terminal 2 - Microservicio de Visión OpenCV (:8002)
python -m uvicorn services.vision.main:app --port 8002

# Terminal 3 - Aplicación Web Django (:8000)
python web/manage.py collectstatic --noinput
python web/manage.py migrate
python web/manage.py seed_demo
python web/manage.py runserver 0.0.0.0:8000
```

---

<details>
<summary>☁️ <b>Configuración de Amazon S3 y PostgreSQL (Producción / Cloud)</b></summary>

* **Amazon S3:** Crea un bucket S3 privado con cifrado y define en `.env` las variables `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_BUCKET`, `AWS_REGION` (y credenciales IAM o rol de instancia EC2). Nunca subas tu archivo `.env` real a GitHub.
* **Base de datos:** Usa SQLite por defecto en local. Para migrar a PostgreSQL (p. ej. Amazon RDS), configura `DATABASE_URL=postgresql://usuario:clave@host:5432/basedatos` y ejecuta `python web/manage.py migrate`.

</details>
