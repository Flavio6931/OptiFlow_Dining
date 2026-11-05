@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    OptiFlow Dining
echo ==========================================================
echo.

where docker >nul 2>&1
if errorlevel 1 goto no_docker

docker info >nul 2>&1
if not errorlevel 1 goto docker_ready

echo [1/3] Abriendo Docker Desktop, espera un momento...
if not exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" goto no_docker
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a tries=0
:wait_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto docker_ready
set /a tries+=1
if %tries% lss 60 goto wait_docker
echo [ERROR] Docker Desktop no respondio en 5 minutos.
echo Abrelo a mano, espera a que indique que esta corriendo y vuelve a intentarlo.
goto fail

:docker_ready
echo [2/3] Preparando la aplicacion. La primera vez puede tardar varios minutos...
docker compose up --build -d
if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo iniciar. Si el puerto 8000 esta ocupado, cierra lo que lo use.
    goto fail
)

echo [3/3] Esperando a que responda la aplicacion...
set /a tries=0
:wait_app
curl -s -o nul http://localhost:8000/
if not errorlevel 1 goto app_ready
set /a tries+=1
if %tries% geq 40 (
    echo [ERROR] La aplicacion no respondio. Revisa con: docker compose logs web
    goto fail
)
timeout /t 3 /nobreak >nul
goto wait_app

:app_ready
start "" http://localhost:8000
echo.
echo Listo: OptiFlow esta en http://localhost:8000
echo Para detenerla ejecuta: docker compose down
timeout /t 8 >nul
exit /b 0

:no_docker
echo [ERROR] Falta instalar Docker Desktop. Te abro la pagina de descarga.
echo Instalalo, reinicia si te lo pide y vuelve a dar doble clic a este archivo.
start "" https://www.docker.com/products/docker-desktop/

:fail
echo.
pause
exit /b 1
