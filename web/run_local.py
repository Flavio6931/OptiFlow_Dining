"""Supervisor local de consola unica para los 3 servicios de OptiFlow Dining."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import webbrowser

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / '.venv' / 'logs'
ENV_PATH = ROOT_DIR / '.env'

JOB_OBJECT_EXTENDED_LIMIT_INFO_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]


class _JobObjectBasicLimitInfo(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]


class _JobObjectExtendedLimitInfo(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', _JobObjectBasicLimitInfo),
        ('IoInfo', _IoCounters),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]


class _WinJobGroup:
    """Agrupa los subprocesos en un Job Object de Windows para cerrarlos al salir."""

    def __init__(self) -> None:
        self._kernel32 = None
        self._handle = None
        if sys.platform != 'win32':
            return
        try:
            k32 = ctypes.WinDLL('kernel32', use_last_error=True)
            k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            k32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.LPVOID,
                wintypes.DWORD,
            ]
            k32.SetInformationJobObject.restype = wintypes.BOOL
            k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            k32.AssignProcessToJobObject.restype = wintypes.BOOL
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            k32.CloseHandle.restype = wintypes.BOOL

            handle = k32.CreateJobObjectW(None, None)
            if not handle:
                return
            info = _JobObjectExtendedLimitInfo()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            ok = k32.SetInformationJobObject(
                handle,
                JOB_OBJECT_EXTENDED_LIMIT_INFO_CLASS,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not ok:
                k32.CloseHandle(handle)
                return
            self._kernel32 = k32
            self._handle = handle
        except OSError:
            self._handle = None

    def attach(self, proc: subprocess.Popen[str]) -> None:
        """Asocia un proceso hijo activo al Job Object si esta disponible."""
        if not self._handle or not self._kernel32:
            return
        proc_handle = getattr(proc, '_handle', None)
        if proc_handle:
            self._kernel32.AssignProcessToJobObject(self._handle, int(proc_handle))

    def close(self) -> None:
        """Cierra el Job Object liberando los recursos del sistema."""
        if self._handle and self._kernel32:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def read_demo_config(env_path: Path) -> tuple[bool, str]:
    """Lee unicamente la bandera y contrasena de usuarios demo desde .env."""
    if not env_path.is_file():
        return False, ''
    demo_enabled = False
    demo_password = ''
    for raw_line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        clean_val = value.strip().strip('"').strip("'")
        if key == 'ENABLE_DEMO_USERS':
            demo_enabled = clean_val == '1'
        elif key == 'DEMO_PASSWORD':
            demo_password = clean_val
    return demo_enabled, demo_password


def is_url_ready(url: str) -> bool:
    """Comprueba si un servicio local responde HTTP por debajo de estado 500."""
    try:
        with urllib.request.urlopen(url, timeout=1.0) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, OSError):
        return False


def print_log_tail(log_path: Path, lines: int = 20) -> None:
    """Imprime las ultimas lineas de registro de un servicio fallido."""
    if not log_path.is_file():
        return
    content = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    for entry in content[-lines:]:
        print(f'    {entry}')


def stop_services(processes: list[tuple[str, subprocess.Popen[str], Path, object]]) -> None:
    """Termina de forma ordenada los subprocesos y cierra sus archivos de log."""
    for _, proc, _, _ in processes:
        if proc.poll() is None:
            proc.terminate()
    for _, proc, _, _ in processes:
        if proc.poll() is None:
            try:
                proc.wait(timeout=4.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
    for _, _, _, log_handle in processes:
        try:
            log_handle.close()
        except OSError:
            pass


def install_console_stop_handler(stop_event: threading.Event):
    """Captura eventos de cierre de consola en Windows para apagar sin huerfanos."""
    if sys.platform != 'win32':
        return None
    handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

    def _on_ctrl(ctrl_type: int) -> bool:
        if ctrl_type in (0, 1, 2, 5, 6):
            stop_event.set()
            return True
        return False

    callback = handler_type(_on_ctrl)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(callback, True)
    return callback


def print_summary(env_path: Path) -> None:
    """Muestra URLs activas, acceso movil y credenciales demo en la consola."""
    demo_enabled, demo_password = read_demo_config(env_path)
    print()
    print('==========================================================')
    print('  Los 3 servicios se estan ejecutando en esta consola:')
    print()
    print('  - Aplicacion Web:       http://127.0.0.1:8000')
    print('  - Panel Admin Django:   http://127.0.0.1:8000/admin/')
    print('  - Microservicio Rutas:  http://127.0.0.1:8001/docs')
    print('  - Microservicio Vision: http://127.0.0.1:8002/docs')
    print('  - Registros locales:    .venv\\logs\\')
    print()
    print('  Movil: usa la misma red y escanea el QR de la app. Si Windows pregunta, permite el acceso a Python.')
    print('  Acceso: pulsa "Crear cuenta" para registrarte.')
    if demo_enabled:
        print()
        print('  Usuarios de prueba: mesero_demo, capitan_demo, gerente_demo')
        if demo_password:
            print(f'  Contrasena: {demo_password}')
    print('  Administrador: .venv\\Scripts\\python web\\manage.py createsuperuser')
    print()
    print('  Para detener los 3 servicios: presiona Ctrl+C o cierra esta ventana.')
    print('==========================================================')
    print()


def main(argv: list[str] | None = None) -> int:
    """Inicia y supervisa Django, Rutas y Vision dentro de una sola consola."""
    parser = argparse.ArgumentParser(description='Ejecuta OptiFlow Dining en una sola consola.')
    parser.add_argument('--no-browser', action='store_true', help='No abrir el navegador automaticamente.')
    args = parser.parse_args(argv)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env.setdefault('DJANGO_DEBUG', '0')
    child_env['PYTHONUNBUFFERED'] = '1'

    specs = [
        (
            'Microservicio Rutas (:8001)',
            'http://127.0.0.1:8001/docs',
            LOGS_DIR / 'routing.log',
            [sys.executable, '-m', 'uvicorn', 'services.routing.main:app', '--port', '8001'],
        ),
        (
            'Microservicio Vision (:8002)',
            'http://127.0.0.1:8002/docs',
            LOGS_DIR / 'vision.log',
            [sys.executable, '-m', 'uvicorn', 'services.vision.main:app', '--port', '8002'],
        ),
        (
            'Django Web (:8000)',
            'http://127.0.0.1:8000/',
            LOGS_DIR / 'web.log',
            [sys.executable, str(ROOT_DIR / 'web' / 'manage.py'), 'runserver', '0.0.0.0:8000', '--noreload'],
        ),
    ]

    stop_event = threading.Event()
    _ctrl_ref = install_console_stop_handler(stop_event)
    job_group = _WinJobGroup()
    processes: list[tuple[str, subprocess.Popen[str], Path, object]] = []

    try:
        for idx, (label, _, log_path, cmd) in enumerate(specs, start=1):
            print(f'[{idx}/3] Levantando {label}...')
            log_handle = log_path.open('w', encoding='utf-8', errors='replace', buffering=1)
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=child_env,
                text=True,
            )
            job_group.attach(proc)
            processes.append((label, proc, log_path, log_handle))

        print('\nEsperando a que respondan los servicios...')
        urls = [item[1] for item in specs]
        ready = [False, False, False]
        for _ in range(150):
            if stop_event.is_set():
                return 0
            for label, proc, log_path, _ in processes:
                rc = proc.poll()
                if rc is not None:
                    print(f'\n[ERROR] {label} se detuvo al iniciar (codigo {rc}). Ultimas lineas del registro:')
                    print_log_tail(log_path)
                    return 1
            for i, url in enumerate(urls):
                if not ready[i] and is_url_ready(url):
                    ready[i] = True
            if all(ready):
                break
            stop_event.wait(0.4)

        if ready[2]:
            if not args.no_browser:
                webbrowser.open('http://127.0.0.1:8000')
        else:
            print('\n[AVISO] Django aun tarda en responder. Revisa .venv\\logs\\web.log si continua sin abrir.')

        print_summary(ENV_PATH)

        while not stop_event.is_set():
            stop_event.wait(0.5)
            for label, proc, log_path, _ in processes:
                rc = proc.poll()
                if rc is not None:
                    print(f'\n[ERROR] {label} se detuvo inesperadamente (codigo {rc}). Ultimas lineas:')
                    print_log_tail(log_path)
                    return 1
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        print('\nDeteniendo los 3 servicios de OptiFlow Dining...')
        stop_services(processes)
        job_group.close()
        print('Servicios detenidos correctamente.')


if __name__ == '__main__':
    raise SystemExit(main())
