"""Procesamiento de imágenes con OpenCV DNN para contar personas en el salón.

Detector principal: YOLOX-S de OpenCV Zoo (ONNX) ejecutado con cv2.dnn sobre la foto completa
y sobre un mosaico de recortes solapados, para no perder personas pequeñas o lejanas, de
espaldas o en ángulo. Si el modelo ONNX no está disponible se usa el ensamble anterior
(MobileNet-SSD + Haar + HOG). En ambos casos los resultados se fusionan con NMS.
"""
import asyncio
import base64
import math
import os
import threading
from typing import Any, Dict, List, Tuple

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "16000000")

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
import numpy as np

app = FastAPI(
    title='OptiFlow · Visión con OpenCV',
    version='3.0.0',
    description='Conteo de comensales y personal con OpenCV DNN (YOLOX-S de OpenCV Zoo) y mosaico de recortes.',
)

MAX_SIZE: int = 5 * 1024 * 1024  # 5 MB
MAX_PIXELS: int = 16_000_000
MAX_DIMENSION: int = 1000  # lado máximo de la imagen anotada que se devuelve
DETECT_MAX_DIMENSION: int = 1600  # lado máximo de la imagen sobre la que se detecta
DETECT_MIN_DIMENSION: int = 1280  # las fotos más pequeñas se amplían para que el mosaico vea a los lejanos

# Inicialización de modelos de detección de personas y comensales
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
PROFILE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
UPPER_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

HOG = cv2.HOGDescriptor()
HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# Inicialización de red neuronal profunda MobileNet-SSD (Caffe)
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')
PROTOTXT = os.path.join(MODELS_DIR, 'MobileNetSSD_deploy.prototxt')
CAFFEMODEL = os.path.join(MODELS_DIR, 'MobileNetSSD_deploy.caffemodel')

NET = None
if os.path.exists(PROTOTXT) and os.path.exists(CAFFEMODEL):
    try:
        NET = cv2.dnn.readNetFromCaffe(PROTOTXT, CAFFEMODEL)
    except Exception:
        NET = None

# YOLOX-S (OpenCV Zoo, Apache-2.0): entrada 640x640 RGB sin normalizar, salida (1, 8400, 85)
# con [cx, cy, w, h, objectness, 80 clases COCO]. La clase 0 es 'person'.
YOLOX_ONNX = os.path.join(MODELS_DIR, 'object_detection_yolox_2022nov.onnx')
YOLOX_INPUT = 640
YOLOX_STRIDES = (8, 16, 32)
PERSON_SCORE = 0.25
NMS_IOU = 0.55  # comensales sentados juntos se solapan mucho; un IoU bajo los fusionaría
# Niveles del mosaico (lado del recorte, solape). 640 = entrada de YOLOX, para personas lejanas;
# 1024 para personas de primer plano que quedan cortadas en los recortes pequeños. El solape debe
# superar el tamaño típico de una persona a esa escala.
TILE_LEVELS = ((640, 160), (1024, 256))
EDGE_MARGIN = 3  # px: una caja que toca un borde interior del recorte está cortada

YOLOX_NET = None
if os.path.exists(YOLOX_ONNX):
    try:
        YOLOX_NET = cv2.dnn.readNetFromONNX(YOLOX_ONNX)
    except Exception:
        YOLOX_NET = None

# cv2.dnn.Net no es seguro entre hilos y /analyze corre en un threadpool.
NET_LOCK = threading.Lock()


def _yolox_grid() -> Tuple[np.ndarray, np.ndarray]:
    """Rejilla de celdas y paso (stride) de cada una de las 8400 salidas de YOLOX."""
    grids, strides = [], []
    for stride in YOLOX_STRIDES:
        size = YOLOX_INPUT // stride
        xv, yv = np.meshgrid(np.arange(size), np.arange(size))
        grids.append(np.stack((xv, yv), axis=2).reshape(-1, 2))
        strides.append(np.full((size * size, 1), stride))
    return np.concatenate(grids).astype(np.float32), np.concatenate(strides).astype(np.float32)


YOLOX_GRID, YOLOX_GRID_STRIDES = _yolox_grid()


def _yolox_people(region: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Detecta personas en una región BGR. Devuelve cajas [x, y, w, h] en píxeles de la región y scores."""
    rh, rw = region.shape[:2]
    ratio = min(YOLOX_INPUT / rh, YOLOX_INPUT / rw)
    resized = cv2.resize(region, (int(rw * ratio), int(rh * ratio)), interpolation=cv2.INTER_LINEAR)
    # Letterbox como en la demo de OpenCV Zoo: lienzo gris (114) con la imagen arriba a la izquierda.
    canvas = np.full((YOLOX_INPUT, YOLOX_INPUT, 3), 114, dtype=np.uint8)
    canvas[:resized.shape[0], :resized.shape[1]] = resized
    blob = cv2.dnn.blobFromImage(canvas, 1.0, swapRB=True)

    with NET_LOCK:
        YOLOX_NET.setInput(blob)
        out = YOLOX_NET.forward()[0]

    person = out[:, 4] * out[:, 5]
    keep = person >= PERSON_SCORE
    if not np.any(keep):
        return np.empty((0, 4), dtype=np.float32), np.empty(0, dtype=np.float32)
    out = out[keep]
    centers = (out[:, :2] + YOLOX_GRID[keep]) * YOLOX_GRID_STRIDES[keep]
    sizes = np.exp(out[:, 2:4]) * YOLOX_GRID_STRIDES[keep]
    boxes = np.concatenate((centers - sizes / 2, sizes), axis=1) / ratio
    return boxes, person[keep]


def _tile_origins(length: int, size: int, overlap: int) -> List[int]:
    """Posiciones de inicio de los recortes a lo largo de un eje (el último pegado al borde)."""
    if length <= size:
        return [0]
    count = math.ceil((length - overlap) / (size - overlap))
    step = (length - size) / (count - 1)
    return [round(i * step) for i in range(count)]


def _detect_yolox(image: np.ndarray) -> Tuple[List[List[int]], List[float]]:
    """Foto completa + mosaico de recortes solapados a dos escalas; cajas en píxeles de `image`."""
    h, w = image.shape[:2]
    boxes, scores = _yolox_people(image)
    all_boxes, all_scores = [boxes], [scores]

    for size, overlap in TILE_LEVELS:
        if max(h, w) <= size:
            continue
        for y0 in _tile_origins(h, size, overlap):
            for x0 in _tile_origins(w, size, overlap):
                tile = image[y0:y0 + size, x0:x0 + size]
                th, tw = tile.shape[:2]
                boxes, scores = _yolox_people(tile)
                if not len(boxes):
                    continue
                x1, y1 = boxes[:, 0], boxes[:, 1]
                x2, y2 = x1 + boxes[:, 2], y1 + boxes[:, 3]
                # Una persona cortada por un borde interior del recorte aparece entera en el
                # recorte vecino (gracias al solape) o en la pasada de foto completa.
                cut = np.zeros(len(boxes), dtype=bool)
                if x0 > 0:
                    cut |= x1 <= EDGE_MARGIN
                if y0 > 0:
                    cut |= y1 <= EDGE_MARGIN
                if x0 + tw < w:
                    cut |= x2 >= tw - EDGE_MARGIN
                if y0 + th < h:
                    cut |= y2 >= th - EDGE_MARGIN
                boxes = boxes[~cut] + np.array([x0, y0, 0, 0], dtype=np.float32)
                all_boxes.append(boxes)
                all_scores.append(scores[~cut])

    boxes = np.concatenate(all_boxes)
    scores = np.concatenate(all_scores)
    return boxes.round().astype(int).tolist(), scores.astype(float).tolist()


def _detect_legacy(image: np.ndarray) -> Tuple[List[List[int]], List[float]]:
    """Ensamble anterior (MobileNet-SSD + Haar + HOG), usado solo si falta el modelo YOLOX."""
    h, w = image.shape[:2]
    candidate_boxes: List[List[int]] = []
    scores: List[float] = []

    # 1. Inferencia profunda con MobileNet-SSD (Clase 15: Person)
    if NET is not None:
        blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007843, (300, 300), 127.5)
        NET.setInput(blob)
        detections = NET.forward()
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            class_idx = int(detections[0, 0, i, 1])
            if class_idx == 15 and confidence >= 0.18:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype('int')
                bw = max(1, x2 - x1)
                bh = max(1, y2 - y1)
                candidate_boxes.append([int(x1), int(y1), int(bw), int(bh)])
                scores.append(confidence)

        # Escaneo multi-escala horizontal para comensales sentados a media/larga distancia
        for y_start, y_end in [(0, int(h * 0.65)), (int(h * 0.3), h)]:
            slice_img = image[y_start:y_end, :]
            sh, sw = slice_img.shape[:2]
            if sh > 100:
                sblob = cv2.dnn.blobFromImage(cv2.resize(slice_img, (300, 300)), 0.007843, (300, 300), 127.5)
                NET.setInput(sblob)
                s_detections = NET.forward()
                for i in range(s_detections.shape[2]):
                    confidence = float(s_detections[0, 0, i, 2])
                    class_idx = int(s_detections[0, 0, i, 1])
                    if class_idx == 15 and confidence >= 0.20:
                        box = s_detections[0, 0, i, 3:7] * np.array([sw, sh, sw, sh])
                        x1, y1, x2, y2 = box.astype('int')
                        candidate_boxes.append([int(x1), int(y1 + y_start), int(max(1, x2 - x1)), int(max(1, y2 - y1))])
                        scores.append(confidence)

    # 2. Preprocesamiento de iluminación con CLAHE para rostros y torsos sentados
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)

    # Detección de rostros frontales
    faces = FACE_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    for (x, y, bw, bh) in faces:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh * 1.5)])
        scores.append(0.75)

    # Detección de rostros de perfil
    profiles = PROFILE_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    for (x, y, bw, bh) in profiles:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh * 1.5)])
        scores.append(0.70)

    # Detección de cuerpo superior (torsos de personas sentadas)
    uppers = UPPER_CASCADE.detectMultiScale(gray_eq, scaleFactor=1.05, minNeighbors=2, minSize=(30, 30))
    for (x, y, bw, bh) in uppers:
        candidate_boxes.append([int(x), int(y), int(bw), int(bh)])
        scores.append(0.68)

    # 3. Detector HOG de personas completas (personal de pie o transitando)
    hog_boxes, weights = HOG.detectMultiScale(
        image,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.08,
        useMeanshiftGrouping=False,
    )
    for (x, y, bw, bh), weight in zip(hog_boxes, weights):
        if float(weight) >= 0.35:
            candidate_boxes.append([int(x), int(y), int(bw), int(bh)])
            scores.append(float(weight))

    return candidate_boxes, scores


def _drop_partial_duplicates(boxes: List[List[int]], scores: List[float], kept: np.ndarray) -> List[int]:
    """Quita cajas que son un trozo de otra persona ya contada (NMS no las ve: su IoU es bajo).

    Una caja casi entera (>=90 %) dentro de otra con mejor score y de anchura parecida es la
    misma persona cortada arriba o abajo. Una persona lejana detrás de otra cercana también cae
    dentro de su caja, pero es mucho más estrecha, así que se conserva.
    """
    order = sorted(kept.tolist(), key=lambda i: scores[i], reverse=True)
    result: List[int] = []
    for i in order:
        x, y, bw, bh = boxes[i]
        partial = False
        for j in result:
            X, Y, BW, BH = boxes[j]
            iw = min(x + bw, X + BW) - max(x, X)
            ih = min(y + bh, Y + BH) - max(y, Y)
            if iw > 0 and ih > 0 and iw * ih >= 0.9 * bw * bh and bw >= 0.7 * BW:
                partial = True
                break
        if not partial:
            result.append(i)
    return result


def _fit(image: np.ndarray, max_side: int, min_side: int = 0) -> np.ndarray:
    """Escala la imagen proporcionalmente para que su lado mayor quede entre `min_side` y `max_side`."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest > max_side:
        scale, interpolation = max_side / longest, cv2.INTER_AREA
    elif longest < min_side:
        scale, interpolation = min_side / longest, cv2.INTER_CUBIC
    else:
        return image
    return cv2.resize(image, (round(w * scale), round(h * scale)), interpolation=interpolation)


def analyze_bytes(raw: bytes) -> Dict[str, Any]:
    """Decodifica una imagen y cuenta las personas por zonas A/B/C.

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

    output = _fit(image, MAX_DIMENSION)
    if YOLOX_NET is not None:
        detect_image = _fit(image, DETECT_MAX_DIMENSION, DETECT_MIN_DIMENSION)
        candidate_boxes, scores = _detect_yolox(detect_image)
        score_threshold, nms_threshold = PERSON_SCORE, NMS_IOU
        method = 'OpenCV DNN · YOLOX-S (OpenCV Zoo) con mosaico de recortes + NMS'
    else:
        detect_image = output
        candidate_boxes, scores = _detect_legacy(output)
        score_threshold, nms_threshold = 0.25, 0.35
        method = 'OpenCV Ensamble DNN MobileNet-SSD + Haar + HOG + NMS'

    h, w = output.shape[:2]
    scale = w / detect_image.shape[1]
    zone_counts = {'A': 0, 'B': 0, 'C': 0}
    final_rectangles: List[Tuple[int, int, int, int, float]] = []

    # Fusión y eliminación de solapamientos con Non-Maximum Suppression (NMS)
    if candidate_boxes:
        indices = cv2.dnn.NMSBoxes(candidate_boxes, scores, score_threshold, nms_threshold)
        for idx in _drop_partial_duplicates(candidate_boxes, scores, np.array(indices).flatten()):
            x, y, bw, bh = (round(v * scale) for v in candidate_boxes[idx])
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            bw = max(1, min(bw, w - x))
            bh = max(1, min(bh, h - y))

            cx = (x + bw / 2) / max(1, w)
            zone = 'A' if cx < 1 / 3 else 'B' if cx < 2 / 3 else 'C'
            zone_counts[zone] += 1
            final_rectangles.append((x, y, bw, bh, scores[idx]))

    overlay = output.copy()
    for (x, y, bw, bh, _confidence) in final_rectangles:
        # Solo el recuadro: con decenas de personas, una etiqueta por caja tapa la foto.
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (30, 205, 255), 2)

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

    ok, encoded = cv2.imencode('.jpg', overlay, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError('No se pudo procesar y codificar la imagen anotada.')

    return {
        'people_count': len(final_rectangles),
        'zone_counts': zone_counts,
        'annotated_image': 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii'),
        'method': method,
        'disclaimer': (
            'Estimación automática: personas muy tapadas o fuera de cuadro pueden no contarse.'
        ),
    }


@app.get('/', include_in_schema=False)
def root() -> RedirectResponse:
    """Redirige automáticamente la raíz al explorador interactivo Swagger UI."""
    return RedirectResponse(url='/docs')


@app.get('/health')
def health() -> Dict[str, str]:
    """Verificación de operatividad del microservicio de visión."""
    return {
        'status': 'ok',
        'service': 'vision',
        'engine': cv2.__version__,
        'dnn_model': (
            'YOLOX-S' if YOLOX_NET is not None
            else 'MobileNet-SSD' if NET is not None
            else 'haar-hog-fallback'
        ),
    }


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
