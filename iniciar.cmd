@echo off
chcp 65001 >nul
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

echo ==========================================================
echo    OptiFlow Dining - Lanzador de Servicios (CMD)
echo ==========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual en .venv\Scripts\python.exe
    echo Verifica que la carpeta .venv exista en la raiz del proyecto.
    echo.
    pause
    exit /b 1
)

echo [1/3] Levantando Django Web en puerto 8000...
start "OptiFlow - Django Web (:8000)" cmd /k "title Django Web (:8000) && echo ======================================== && echo  Servicio 1: Django Web (Puerto 8000) && echo ======================================== && .venv\Scripts\python.exe web\manage.py runserver 0.0.0.0:8000"

echo [2/3] Levantando Microservicio de Rutas en puerto 8001...
start "OptiFlow - Rutas FastAPI (:8001)" cmd /k "title Rutas FastAPI (:8001) && echo ======================================== && echo  Servicio 2: Rutas FastAPI (Puerto 8001) && echo ======================================== && .venv\Scripts\python.exe -m uvicorn services.routing.main:app --port 8001"

echo [3/3] Levantando Microservicio de Vision OpenCV en puerto 8002...
start "OptiFlow - Vision OpenCV (:8002)" cmd /k "title Vision OpenCV (:8002) && echo ======================================== && echo  Servicio 3: Vision OpenCV (Puerto 8002) && echo ======================================== && .venv\Scripts\python.exe -m uvicorn services.vision.main:app --port 8002"

echo.
echo ==========================================================
echo   Los 3 servicios se estan ejecutando en ventanas independientes:
echo.
echo   - Aplicacion Web:       http://127.0.0.1:8000
echo   - Panel Admin Django:   http://127.0.0.1:8000/admin/
echo   - Microservicio Rutas:  http://127.0.0.1:8001/docs
echo   - Microservicio Vision: http://127.0.0.1:8002/docs
echo.
echo   Credenciales de Acceso:
echo   - Usuario:  admin
echo   - Password: 1234
echo.
echo   Para detener los servicios: cierra las 3 ventanas de terminal.
echo ==========================================================
echo.
pause
