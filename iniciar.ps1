# ==========================================================
# OptiFlow Dining - Lanzador de Microservicios (PowerShell)
# ==========================================================

$root = $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[ERROR] No se encontro el entorno virtual en .venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "Verifica que la carpeta .venv exista en la raiz del proyecto." -ForegroundColor Yellow
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Iniciando OptiFlow Dining (Django + Microservicios)   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Django Web (Puerto 8000)
Write-Host "[1/3] Iniciando Django Web en puerto 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$host.UI.RawUI.WindowTitle = 'OptiFlow - Django Web (:8000)'; cd '$root'; Write-Host '--- Django Web (:8000) ---' -ForegroundColor Cyan; & '$python' web/manage.py runserver 8000"

# 2. Microservicio Rutas (FastAPI en puerto 8001)
Write-Host "[2/3] Iniciando Microservicio de Rutas en puerto 8001..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$host.UI.RawUI.WindowTitle = 'OptiFlow - Rutas FastAPI (:8001)'; cd '$root'; Write-Host '--- Microservicio Rutas (:8001) ---' -ForegroundColor Cyan; & '$python' -m uvicorn services.routing.main:app --port 8001"

# 3. Microservicio Vision OpenCV (FastAPI en puerto 8002)
Write-Host "[3/3] Iniciando Microservicio de Vision OpenCV en puerto 8002..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$host.UI.RawUI.WindowTitle = 'OptiFlow - Vision OpenCV (:8002)'; cd '$root'; Write-Host '--- Microservicio Vision (:8002) ---' -ForegroundColor Cyan; & '$python' -m uvicorn services.vision.main:app --port 8002"

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  Los 3 servicios estan ejecutandose en paralelo:" -ForegroundColor Yellow
Write-Host "  - Web Django:        http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  - Panel Admin:       http://127.0.0.1:8000/admin/" -ForegroundColor White
Write-Host "  - Rutas (FastAPI):   http://127.0.0.1:8001/docs" -ForegroundColor White
Write-Host "  - Vision (OpenCV):   http://127.0.0.1:8002/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Credenciales: admin / 1234" -ForegroundColor White
Write-Host "  Para detenerlos: Cierra las 3 ventanas de terminal." -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Yellow
