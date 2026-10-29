"""Procesamiento de imágenes con detector OpenCV multi-modelo adaptado a comensales.

Combina clasificadores en cascada Haar (cuerpo superior, rostros frontales y perfil)
con HOG descriptor, CLAHE para iluminación de salón y supresión de no máximos (NMS).
"""
import asyncio
import base64
import os
from typing import Any, Dict, List, Tuple

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "16000000")

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
import numpy as np

app = FastAPI(
    title='OptiFlow · Visión con OpenCV',
    version='2.0.0',
    description='Detección de comensales sentados y personal mediante ensamble Haar + HOG y NMS.',
)

MAX_SIZE: int = 5 * 1024 * 1024  # 5 MB
MAX_PIXELS: int = 16_000_000
MAX_DIMENSION: int = 900
CONFIDENCE_THRESHOLD: float = 0.35

# Inicialización de modelos de detección de personas y comensales
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
PROFILE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
UPPER_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

HOG = cv2.HOGDescriptor()
HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def analyze_bytes(raw: bytes) -> Dict[str, Any]:
    """Decodifica y procesa los bytes de una imagen con el ensamble multi-modelo adaptado a restaurante.

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

    # Preprocesamiento de iluminación con ecualización de histograma adaptativa (CLAHE)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)

    candidate_boxes: List[List[int]] = []
    scores: List[float] = []

    # 1. Detección de rostros frontales (comensales sentados mirando a cámara)
    faces = FACE_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=4, minSize=(25, 25))
    for (x, y, bw, bh) in faces:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh * 1.4)])
        scores.append(0.85)

    # 2. Detección de rostros de perfil (comensales sentados de lado)
    profiles = PROFILE_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=4, minSize=(25, 25))
    for (x, y, bw, bh) in profiles:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh * 1.4)])
        scores.append(0.80)

    # 3. Detección de cuerpo superior (torsos de personas sentadas en mesas)
    uppers = UPPER_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40))
    for (x, y, bw, bh) in uppers:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh)])
        scores.append(0.82)

    # 4. Detector HOG de personas completas (personal de pie o transitando)
    hog_boxes, weights = HOG.detectMultiScale(
        image,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.08,
        useMeanshiftGrouping=False,
    )
    for (x, y, bw, bh), weight in zip(hog_boxes, weights):
        if float(weight) >= CONFIDENCE_THRESHOLD:
            candidate_boxes.append([int(x), int(y), int(bw), int(bh)])
            scores.append(float(weight))

    zone_counts = {'A': 0, 'B': 0, 'C': 0}
    final_rectangles: List[Tuple[int, int, int, int, float]] = []

    # Fusión y eliminación de solapamientos con Non-Maximum Suppression (NMS)
    if candidate_boxes:
        indices = cv2.dnn.NMSBoxes(candidate_boxes, scores, score_threshold=0.35, nms_threshold=0.35)
        # NMSBoxes puede devolver un array plano o una lista de tuplas según versión de OpenCV
        if len(indices) > 0:
            for idx in np.array(indices).flatten():
                box = candidate_boxes[idx]
                score = scores[idx]
                x, y, bw, bh = box[0], box[1], box[2], box[3]
                # Asegurar límites dentro de la imagen
                x = max(0, min(x, w - 1))
                y = max(0, min(y, h - 1))
                bw = min(bw, w - x)
                bh = min(bh, h - y)

                cx = (x + bw / 2) / max(1, w)
                zone = 'A' if cx < 1 / 3 else 'B' if cx < 2 / 3 else 'C'
                zone_counts[zone] += 1
                final_rectangles.append((x, y, bw, bh, score))

    overlay = image.copy()
    for (x, y, bw, bh, confidence) in final_rectangles:
        # Recuadro esmeralda/naranja de detección
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (30, 205, 255), 2)
        cv2.putText(
            overlay,
            f'Comensal {confidence:.2f}',
            (x, max(17, y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
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

    ok, encoded = cv2.imencode('.jpg', overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        raise ValueError('No se pudo procesar y codificar la imagen anotada.')

    return {
        'people_count': len(final_rectangles),
        'zone_counts': zone_counts,
        'annotated_image': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii'),
        'method': 'OpenCV Ensamble (Upperbody + Rostros + HOG + CLAHE + NMS)',
        'disclaimer': (
            'Estimación optimizada para comensales en mesas y personal en pasillos.'
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
        # Ejecución en threadpool AnyIO para no bloquear el event loop asíncrono (ECC)
        return await asyncio.to_thread(analyze_bytes, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
