@echo off
chcp 65001 >nul
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

echo ==========================================================
echo    OptiFlow Dining - Lanzador de Servicios (CMD)
echo ==========================================================
echo.

rem La primera vez prepara todo: entorno virtual, dependencias y .env.
if exist ".venv\.instalado" goto env_check

set "SYS_PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "SYS_PY=py -3"
if defined SYS_PY goto create_venv
python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 set "SYS_PY=python"
if defined SYS_PY goto create_venv
echo [ERROR] Necesitas Python 3.11 o superior. Te abro la pagina de descarga.
echo Al instalar, marca la opcion "Add python.exe to PATH" y vuelve a abrir este archivo.
start "" https://www.python.org/downloads/
goto fail

:create_venv
echo Primera vez: instalando lo necesario. Puede tardar varios minutos...
if not exist ".venv\Scripts\python.exe" %SYS_PY% -m venv .venv
if errorlevel 1 goto install_error
.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r web\requirements.txt -r services\routing\requirements.txt -r services\vision\requirements.txt
if errorlevel 1 goto install_error
type nul > ".venv\.instalado"

:env_check
if exist ".env" goto port_check
.venv\Scripts\python.exe scripts\generate_env.py --demo
if errorlevel 1 goto install_error

:port_check
rem Si Docker (docker compose) ya ocupa el puerto 8000, runserver no puede arrancar y el
rem navegador abriria la version de Docker en lugar de la local.
netstat -ano | findstr /R /C:":8000 .*LISTENING" /C:":8000 .*ESCUCHANDO" >nul
if not errorlevel 1 (
    echo [AVISO] El puerto 8000 ya esta en uso, probablemente por Docker.
    echo         Si sigues, veras la version de Docker y no la de este lanzador.
    echo         Detenlo con:  docker compose down
    echo         y vuelve a ejecutar iniciar.cmd.
    goto fail
)

rem Con DJANGO_DEBUG=0, WhiteNoise sirve CSS/JS desde web\staticfiles: hay que recopilarlos
rem en cada arranque o el navegador recibe la version antigua.
echo [0/3] Actualizando archivos estaticos (CSS/JS)...
.venv\Scripts\python.exe web\manage.py collectstatic --noinput --clear -v 0
if errorlevel 1 (
    echo [ERROR] No se pudieron preparar los archivos estaticos.
    goto fail
)

echo Preparando la base de datos...
.venv\Scripts\python.exe web\manage.py migrate --noinput -v 0
if errorlevel 1 goto db_error
.venv\Scripts\python.exe web\manage.py seed_demo
if errorlevel 1 goto db_error

echo [1/3] Levantando Django Web en puerto 8000...
start "OptiFlow - Django Web (:8000)" cmd /k "title Django Web (:8000) && echo ======================================== && echo  Servicio 1: Django Web (Puerto 8000) && echo ======================================== && .venv\Scripts\python.exe web\manage.py runserver 127.0.0.1:8000"

echo [2/3] Levantando Microservicio de Rutas en puerto 8001...
start "OptiFlow - Rutas FastAPI (:8001)" cmd /k "title Rutas FastAPI (:8001) && echo ======================================== && echo  Servicio 2: Rutas FastAPI (Puerto 8001) && echo ======================================== && .venv\Scripts\python.exe -m uvicorn services.routing.main:app --port 8001"

echo [3/3] Levantando Microservicio de Vision OpenCV en puerto 8002...
start "OptiFlow - Vision OpenCV (:8002)" cmd /k "title Vision OpenCV (:8002) && echo ======================================== && echo  Servicio 3: Vision OpenCV (Puerto 8002) && echo ======================================== && .venv\Scripts\python.exe -m uvicorn services.vision.main:app --port 8002"

echo.
echo Esperando a que responda la aplicacion...
set /a tries=0
:wait_app
curl -s -o nul http://127.0.0.1:8000/
if not errorlevel 1 goto app_ready
set /a tries+=1
if %tries% geq 40 goto app_slow
timeout /t 3 /nobreak >nul
goto wait_app

:app_slow
echo [AVISO] Aun no responde. Revisa la ventana "Django Web" por si muestra un error.
goto summary

:app_ready
start "" http://127.0.0.1:8000

:summary

echo.
echo ==========================================================
echo   Los 3 servicios se estan ejecutando en ventanas independientes:
echo.
echo   - Aplicacion Web:       http://127.0.0.1:8000
echo   - Panel Admin Django:   http://127.0.0.1:8000/admin/
echo   - Microservicio Rutas:  http://127.0.0.1:8001/docs
echo   - Microservicio Vision: http://127.0.0.1:8002/docs
echo.
echo   Acceso: pulsa "Crear cuenta" para registrarte.
findstr /b /c:"ENABLE_DEMO_USERS=1" .env >nul
if errorlevel 1 goto after_demo
echo.
echo   Usuarios de prueba: mesero_demo, capitan_demo, gerente_demo
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"DEMO_PASSWORD=" .env') do echo   Contrasena: %%b
:after_demo
echo   Administrador: .venv\Scripts\python web\manage.py createsuperuser
echo.
echo   Para detener los servicios: cierra las 3 ventanas de terminal.
echo ==========================================================
echo.
pause
exit /b 0

:install_error
echo [ERROR] No se pudo completar la instalacion. Revisa tu conexion e intentalo de nuevo.
goto fail

:db_error
echo [ERROR] No se pudo preparar la base de datos.

:fail
echo.
pause
exit /b 1
