"""Servicios de comunicación e integración con microservicios externos y AWS S3."""
import logging
from pathlib import Path
import sys
from typing import Any, Dict, Tuple
from uuid import uuid4

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ServiceUnavailable(Exception):
    """Excepción lanzada cuando un microservicio auxiliar no responde."""
    pass


def calculate_route(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Consulta el microservicio de ruteo o ejecuta fallback local.

    Args:
        payload: Diccionario con origen, destino, tipo de tarea y parámetros de congestión.

    Returns:
        Tupla (código_http, datos_respuesta).
    """
    # El microservicio no comparte disco con Django: enviarle siempre el plano vigente
    # para que vea mesas creadas, movidas o unificadas.
    if 'layout' not in payload:
        from .layout import get_layout
        payload = {**payload, 'layout': get_layout()}
    try:
        url = f"{settings.ROUTING_SERVICE_URL}/route"
        response = requests.post(url, json=payload, timeout=5)
        data = response.json()
        if response.status_code in (400, 404):
            return response.status_code, data
        response.raise_for_status()
        return 200, data
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Fallo al contactar el microservicio de ruteo HTTP (%s). Intentando fallback local.",
            exc,
        )
        # Fallback local automático para desarrollo sin Docker
        try:
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from services.routing.main import route as local_route, RouteRequest
            from fastapi import HTTPException

            try:
                res = local_route(RouteRequest(**payload))
                return 200, res
            except HTTPException as http_exc:
                return http_exc.status_code, {'detail': http_exc.detail}
        except (ImportError, ModuleNotFoundError, AttributeError) as local_err:
            logger.debug("Fallback local de ruteo no disponible: %s", local_err)
        except Exception as unexpected_err:
            logger.error(
                "Error inesperado en fallback local de ruteo: %s",
                unexpected_err,
                exc_info=True,
            )

        raise ServiceUnavailable(
            'El microservicio de rutas no está disponible. Verifica Docker Compose.'
        ) from exc


def analyze_image(name: str, raw: bytes, mime: str) -> Tuple[int, Dict[str, Any]]:
    """Envía una imagen al microservicio OpenCV o ejecuta fallback local.

    Args:
        name: Nombre del archivo de imagen.
        raw: Bytes binarios de la imagen.
        mime: Tipo MIME de la imagen.

    Returns:
        Tupla (código_http, datos_respuesta).
    """
    try:
        url = f"{settings.VISION_SERVICE_URL}/analyze"
        response = requests.post(
            url,
            files={'file': (name, raw, mime)},
            timeout=30,
        )
        data = response.json()
        if response.status_code in (400, 413, 422):
            return response.status_code, data
        response.raise_for_status()
        return 200, data
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Fallo al contactar el microservicio de visión HTTP (%s). Intentando fallback local.",
            exc,
        )
        # Fallback local automático para desarrollo sin Docker
        try:
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from services.vision.main import analyze_bytes

            try:
                res = analyze_bytes(raw)
                return 200, res
            except ValueError as ve:
                return 400, {'detail': str(ve)}
        except (ImportError, ModuleNotFoundError, AttributeError) as local_err:
            logger.debug("Fallback local de visión no disponible: %s", local_err)
        except Exception as unexpected_err:
            logger.error(
                "Error inesperado en fallback local de visión: %s",
                unexpected_err,
                exc_info=True,
            )

        raise ServiceUnavailable('El microservicio OpenCV no está disponible.') from exc


def detect_live_frame(raw: bytes, mime: str, mode: str = 'rapido') -> Tuple[int, Dict[str, Any]]:
    """Envía un fotograma de la cámara en vivo al microservicio OpenCV (POST /detect).

    A diferencia de analyze_image, no hay imagen anotada ni se guarda nada: solo cajas y conteo.
    `mode`: 'rapido', 'normal' o 'preciso' (de más fluido a más preciso).

    Returns:
        Tupla (código_http, datos_respuesta).
    """
    try:
        response = requests.post(
            f"{settings.VISION_SERVICE_URL}/detect",
            params={'mode': mode},
            files={'file': ('frame.jpg', raw, mime)},
            timeout=10,
        )
        data = response.json()
        if response.status_code in (400, 413, 422):
            return response.status_code, data
        response.raise_for_status()
        return 200, data
    except (requests.RequestException, ValueError) as exc:
        # Fallback local automático para desarrollo sin Docker
        try:
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from services.vision.main import detect_bytes

            try:
                return 200, detect_bytes(raw, mode)
            except ValueError as ve:
                return 400, {'detail': str(ve)}
        except (ImportError, ModuleNotFoundError, AttributeError) as local_err:
            logger.debug("Fallback local de visión en vivo no disponible: %s", local_err)

        raise ServiceUnavailable('El microservicio OpenCV no está disponible.') from exc


def _get_s3_client(config=None):
    """Construye el cliente de Amazon S3 con credenciales de entorno si están presentes."""
    import boto3
    kwargs = {'region_name': getattr(settings, 'AWS_REGION', 'us-east-1')}
    if config is not None:
        kwargs['config'] = config
    access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', '')
    secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '')
    session_token = getattr(settings, 'AWS_SESSION_TOKEN', '')
    if access_key and secret_key:
        kwargs['aws_access_key_id'] = access_key
        kwargs['aws_secret_access_key'] = secret_key
        if session_token:
            kwargs['aws_session_token'] = session_token
    return boto3.client('s3', **kwargs)


LOCAL_KEY_PREFIX = 'local:'


def _bucket_name() -> str:
    """Bucket S3 configurado explícitamente en el entorno ('' si no hay ninguno)."""
    return getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or getattr(settings, 'AWS_S3_BUCKET', '')


def _aws_error_reason(exc: Exception) -> str:
    """Resume un error de boto3 sin exponer detalles innecesarios (p. ej. AccessDenied, NoCredentialsError)."""
    response = getattr(exc, 'response', None)
    if isinstance(response, dict):
        code = response.get('Error', {}).get('Code')
        if code:
            return code
    return type(exc).__name__


S3_STATUS_CACHE_KEY = 'optiflow:s3_status'
S3_STATUS_TTL = 300  # segundos
S3_HEALTHCHECK_KEY = 'optiflow/analisis/.healthcheck'

# Estado → (icono, texto) que se muestra en la página de visión.
S3_STATE_LABELS = {
    'connected': ('🟢', 'Conectado'),
    'disabled': ('⚪', 'No configurado'),
    'no_credentials': ('🔴', 'Sin credenciales AWS'),
    'denied': ('🔴', 'Sin permiso para escribir en el bucket'),
    'not_found': ('🔴', 'El bucket no existe'),
    'error': ('🟠', 'No se pudo contactar con AWS'),
}


def _s3_state_from_error(exc: Exception) -> str:
    """Clasifica un error de boto3 en uno de los estados de S3_STATE_LABELS."""
    from botocore.exceptions import NoCredentialsError, PartialCredentialsError

    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return 'no_credentials'
    code = _aws_error_reason(exc)
    if code in ('AccessDenied', 'InvalidAccessKeyId', 'SignatureDoesNotMatch', 'ExpiredToken', '403'):
        return 'denied'
    if code in ('NoSuchBucket', '404'):
        return 'not_found'
    return 'error'


def _s3_status(state: str, bucket: str, reason: str = '') -> Dict[str, str]:
    icon, label = S3_STATE_LABELS[state]
    return {
        'state': state,
        'icon': icon,
        'label': label,
        'bucket': bucket,
        'region': getattr(settings, 'AWS_REGION', '') or '',
        'reason': reason,
    }


def _remember_s3_status(status: Dict[str, str]) -> Dict[str, str]:
    from django.core.cache import cache

    cache.set(S3_STATUS_CACHE_KEY, status, S3_STATUS_TTL)
    return status


def s3_connection_status(refresh: bool = False) -> Dict[str, str]:
    """Comprueba de verdad si la app puede guardar fotos en S3 (no basta con tener un bucket).

    Escribe un objeto vacío en S3_HEALTHCHECK_KEY, dentro del mismo prefijo que las fotos, porque
    la política IAM recomendada solo concede s3:PutObject (head_bucket daría 403 aunque las
    subidas funcionen). El resultado se guarda en caché S3_STATUS_TTL segundos.
    """
    from django.core.cache import cache

    bucket = _bucket_name()
    if not bucket:
        return _s3_status('disabled', '')
    if not refresh:
        cached = cache.get(S3_STATUS_CACHE_KEY)
        if cached and cached.get('bucket') == bucket:
            return cached

    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    config = Config(connect_timeout=3, read_timeout=3, retries={'max_attempts': 1})
    try:
        _get_s3_client(config).put_object(
            Bucket=bucket,
            Key=S3_HEALTHCHECK_KEY,
            Body=b'',
            ServerSideEncryption='AES256',
        )
        status = _s3_status('connected', bucket)
    except (BotoCoreError, ClientError) as exc:
        logger.warning('Comprobación de AWS S3 fallida (s3://%s): %s', bucket, exc)
        status = _s3_status(_s3_state_from_error(exc), bucket, _aws_error_reason(exc))
    return _remember_s3_status(status)


def optional_upload_s3(raw: bytes, name: str, mime: str) -> Dict[str, str]:
    """Sube la imagen a Amazon S3 si hay un bucket configurado; si no, o si falla, la guarda en local.

    Las credenciales se resuelven con la cadena estándar de boto3: variables de entorno,
    ~/.aws/credentials o el rol IAM de la instancia EC2.

    Returns:
        Diccionario con:
            storage: 's3' (subida real), 'local' (solo en este servidor) o 'none' (no se guardó).
            key: clave S3, 'local:<ruta>' para copias locales, o '' si no se guardó.
            bucket: bucket configurado ('' si no hay).
            error: motivo del fallo de S3 ('' si no se intentó o funcionó).
    """
    from botocore.exceptions import BotoCoreError, ClientError

    suffix = Path(name).suffix.lower()
    if suffix not in ('.jpg', '.jpeg', '.png', '.webp'):
        suffix = '.jpg'

    key = f'optiflow/analisis/{uuid4().hex}{suffix}'
    bucket = _bucket_name()
    error = ''

    if bucket:
        try:
            _get_s3_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=raw,
                ContentType=mime,
                ServerSideEncryption='AES256',
            )
            logger.info('Evidencia subida a AWS S3: s3://%s/%s', bucket, key)
            _remember_s3_status(_s3_status('connected', bucket))
            return {'storage': 's3', 'key': key, 'bucket': bucket, 'error': ''}
        except (BotoCoreError, ClientError) as aws_err:
            error = _aws_error_reason(aws_err)
            logger.warning('Fallo al subir a AWS S3 (s3://%s/%s): %s', bucket, key, aws_err)
            _remember_s3_status(_s3_status(_s3_state_from_error(aws_err), bucket, error))

    try:
        local_file = settings.MEDIA_ROOT / 'cloud_s3' / key
        local_file.parent.mkdir(parents=True, exist_ok=True)
        local_file.write_bytes(raw)
        logger.info('Evidencia guardada solo en local: %s', local_file)
        return {'storage': 'local', 'key': LOCAL_KEY_PREFIX + key, 'bucket': bucket, 'error': error}
    except OSError as local_err:
        logger.error('No se pudo guardar la evidencia en local: %s', local_err)
        return {'storage': 'none', 'key': '', 'bucket': bucket, 'error': error or type(local_err).__name__}


def get_s3_presigned_url(key: str, expiration: int = 3600) -> str:
    """Genera una URL temporal para ver una evidencia.

    Para objetos en S3 devuelve una URL prefirmada; para copias locales ('local:...') la ruta
    bajo MEDIA_URL (solo servida por Django con DEBUG=1). Devuelve '' si no es posible.
    """
    if not key:
        return ''
    if key.startswith(LOCAL_KEY_PREFIX):
        return f"{settings.MEDIA_URL}cloud_s3/{key[len(LOCAL_KEY_PREFIX):]}"

    bucket = _bucket_name()
    if not bucket:
        return ''

    from botocore.exceptions import BotoCoreError, ClientError
    try:
        return _get_s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.warning('Fallo al generar URL prefirmada en AWS S3 para key %s: %s', key, exc)
        return ''
