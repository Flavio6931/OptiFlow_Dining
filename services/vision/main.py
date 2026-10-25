"""Procesamiento de imágenes con detector HOG de OpenCV.

No presupone identificación de personas ni seguimiento biométrico. Es una estimación
experimental sobre imágenes estáticas divididas espacialmente en tres sectores.
"""
import base64
import os
from typing import Any, Dict, List, Tuple

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "16000000")

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
import numpy as np

app = FastAPI(
    title='OptiFlow · Visión con OpenCV',
    version='1.0.0',
    description='Detección aproximada de personas mediante HOG Descriptor y clasificación por zonas.',
)

MAX_SIZE: int = 5 * 1024 * 1024  # 5 MB
MAX_PIXELS: int = 16_000_000
MAX_DIMENSION: int = 900
CONFIDENCE_THRESHOLD: float = 0.35


def analyze_bytes(raw: bytes) -> Dict[str, Any]:
    """Decodifica y procesa los bytes de una imagen para detectar personas con HOG.

    Args:
        raw: Secuencia binaria de la imagen (JPEG, PNG o WebP).

    Returns:
        Diccionario con conteo de personas, distribución por zonas A/B/C e imagen anotada en base64.

    Raises:
        ValueError: Si la imagen no es válida o excede límites dimensionales.
    """
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('El archivo no contiene una imagen válida.')

    height, width = image.shape[:2]
    if height * width > MAX_PIXELS:
        raise ValueError('La imagen supera el límite de resolución permitido.')

    # Redimensionamiento proporcional para optimizar rendimiento de inferencia
    if width > MAX_DIMENSION:
        image = cv2.resize(image, (MAX_DIMENSION, round(height * MAX_DIMENSION / width)))
    if image.shape[0] > MAX_DIMENSION:
        scale = MAX_DIMENSION / image.shape[0]
        image = cv2.resize(image, (round(image.shape[1] * scale), MAX_DIMENSION))

    h, w = image.shape[:2]
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # Detecta siluetas de personas de pie; en salones y vistas aéreas puede subestimar.
    boxes, weights = hog.detectMultiScale(
        image,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.08,
        useMeanshiftGrouping=False,
    )

    zone_counts = {'A': 0, 'B': 0, 'C': 0}
    rectangles: List[Tuple[int, int, int, int, float]] = []

    for (x, y, bw, bh), weight in zip(boxes, weights):
        if float(weight) < CONFIDENCE_THRESHOLD:
            continue
        if bw < 20 or bh < 35:
            continue
        cx = (x + bw / 2) / max(1, w)
        zone = 'A' if cx < 1 / 3 else 'B' if cx < 2 / 3 else 'C'
        zone_counts[zone] += 1
        rectangles.append((int(x), int(y), int(bw), int(bh), float(weight)))

    overlay = image.copy()
    for (x, y, bw, bh, confidence) in rectangles:
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (30, 205, 255), 2)
        cv2.putText(
            overlay,
            f'Persona {confidence:.2f}',
            (x, max(17, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            2,
        )

    # Divisiones espaciales por tercios (Zona A, B y C)
    for x in (w // 3, 2 * w // 3):
        cv2.line(overlay, (x, 0), (x, h), (230, 200, 70), 1)

    for idx, label in enumerate(('A', 'B', 'C')):
        cv2.putText(
            overlay,
            f'ZONA {label}',
            (10 + idx * (w // 3), 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )

    ok, encoded = cv2.imencode('.jpg', overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
    if not ok:
        raise ValueError('No se pudo procesar y codificar la imagen anotada.')

    return {
        'people_count': len(rectangles),
        'zone_counts': zone_counts,
        'annotated_image': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii'),
        'method': 'OpenCV HOG + clasificación espacial en tercios',
        'disclaimer': (
            'Estimación experimental: requiere vista lateral, calibración y validación; '
            'no representa conteo exacto ni monitoreo en tiempo real.'
        ),
    }


@app.get('/health')
def health() -> Dict[str, str]:
    """Verificación de operatividad del microservicio de visión."""
    return {'status': 'ok', 'service': 'vision', 'engine': cv2.__version__}


@app.post('/analyze')
async def analyze(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Recibe un archivo fotográfico y retorna el conteo de personas y distribución zonal."""
    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(
            status_code=400,
            detail='Formato no permitido: usa JPG, PNG o WebP.',
        )

    raw = await file.read(MAX_SIZE + 1)
    if len(raw) > MAX_SIZE:
        raise HTTPException(status_code=413, detail='La imagen supera 5 MB.')

    try:
        return analyze_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
