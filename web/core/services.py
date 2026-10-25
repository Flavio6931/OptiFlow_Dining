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


def optional_upload_s3(raw: bytes, name: str, mime: str) -> str:
    """Sube opcionalmente una imagen procesada a un bucket de Amazon S3.

    Args:
        raw: Contenido binario del archivo.
        name: Nombre original de la imagen.
        mime: Tipo MIME del archivo.

    Returns:
        Ruta o key generada en S3, o cadena vacía si S3 no está configurado.
    """
    if not settings.AWS_S3_BUCKET:
        return ''

    import boto3

    suffix = Path(name).suffix.lower()
    if suffix not in ('.jpg', '.jpeg', '.png', '.webp'):
        suffix = '.jpg'

    key = f'optiflow/analisis/{uuid4().hex}{suffix}'
    s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
    s3_client.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=raw,
        ContentType=mime,
        ServerSideEncryption='AES256',
    )
    return key
