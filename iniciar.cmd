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
if not exist ".env" if exist ".env.txt" copy /y ".env.txt" ".env" >nul
if not exist ".env" if exist "env" copy /y "env" ".env" >nul
if exist ".env" goto port_check
.venv\Scripts\python.exe web\generate_env.py --demo
if errorlevel 1 goto install_error

:port_check
rem La app queda visible en la red para el acceso movil: nunca en modo desarrollo.
set "DJANGO_DEBUG=0"

rem Si otro programa ya ocupa los puertos de OptiFlow, los servicios no pueden arrancar.
for %%P in (8000 8001 8002) do (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" /C:":%%P .*ESCUCHANDO" >nul
    if not errorlevel 1 (
        echo [AVISO] El puerto %%P ya esta en uso, quiza por otra ventana de OptiFlow.
        echo         Cierrala y vuelve a ejecutar iniciar.cmd.
        goto fail
    )
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

.venv\Scripts\python.exe web\run_local.py
if errorlevel 1 goto fail
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
