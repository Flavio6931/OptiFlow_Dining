"""Pruebas unitarias del microservicio de visión (YOLOX con mosaico de recortes)."""
import unittest

import cv2
import numpy as np

from services.vision import main
from services.vision.main import _drop_partial_duplicates, _tile_origins, analyze_bytes, detect_bytes


def _jpeg(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    return encoded.tobytes()


class VisionServiceTests(unittest.TestCase):
    """Pruebas unitarias del microservicio de visión."""

    def test_yolox_model_is_loaded(self):
        """El modelo YOLOX del repositorio debe cargarse; si no, se usaría el detector antiguo."""
        self.assertIsNotNone(main.YOLOX_NET)
        self.assertEqual(main.health()['dnn_model'], 'YOLOX-S')

    def test_tiles_cover_axis_with_overlap(self):
        """Los recortes cubren todo el eje y vecinos se solapan al menos TILE_OVERLAP."""
        for length in (1280, 1600, 2000):
            for size, overlap in main.TILE_LEVELS:
                starts = _tile_origins(length, size, overlap)
                self.assertEqual(starts[0], 0)
                self.assertEqual(starts[-1] + size, length)
                for a, b in zip(starts, starts[1:]):
                    self.assertGreaterEqual(a + size - b, overlap)

    def test_small_axis_uses_single_tile(self):
        self.assertEqual(_tile_origins(500, 640, 160), [0])

    def test_partial_duplicate_is_dropped(self):
        """Un trozo de la misma persona (anchura parecida) dentro de su caja no cuenta dos veces."""
        boxes = [[100, 100, 80, 200], [102, 100, 76, 90]]
        self.assertEqual(_drop_partial_duplicates(boxes, [0.9, 0.6], np.array([0, 1])), [0])

    def test_narrow_person_behind_is_kept(self):
        """Una persona lejana dentro de la caja de otra cercana, pero mucho más estrecha, se conserva."""
        boxes = [[100, 100, 200, 300], [150, 110, 40, 90]]
        kept = _drop_partial_duplicates(boxes, [0.9, 0.6], np.array([0, 1]))
        self.assertEqual(sorted(kept), [0, 1])

    def test_invalid_image_raises(self):
        with self.assertRaises(ValueError):
            analyze_bytes(b'no es una imagen')

    def test_empty_scene_keeps_response_contract(self):
        """Una foto sin personas devuelve 0 y la misma estructura que espera Django."""
        result = analyze_bytes(_jpeg(np.full((900, 1600, 3), 200, dtype=np.uint8)))
        self.assertEqual(result['people_count'], 0)
        self.assertEqual(result['zone_counts'], {'A': 0, 'B': 0, 'C': 0})
        self.assertTrue(result['annotated_image'].startswith('data:image/jpeg;base64,'))
        self.assertIn('YOLOX', result['method'])
        # La imagen anotada se devuelve como máximo a MAX_DIMENSION de lado.
        import base64
        annotated = cv2.imdecode(
            np.frombuffer(base64.b64decode(result['annotated_image'].split(',', 1)[1]), np.uint8),
            cv2.IMREAD_COLOR,
        )
        self.assertEqual(max(annotated.shape[:2]), main.MAX_DIMENSION)


class LiveDetectionTests(unittest.TestCase):
    """Detección rápida de la cámara en vivo (POST /detect)."""

    def test_live_frame_returns_normalized_boxes_without_image(self):
        result = detect_bytes(_jpeg(np.full((540, 960, 3), 200, dtype=np.uint8)))
        self.assertEqual(result['people_count'], 0)
        self.assertEqual(result['boxes'], [])
        self.assertEqual(result['zone_counts'], {'A': 0, 'B': 0, 'C': 0})
        self.assertNotIn('annotated_image', result)
        self.assertIn('en vivo', result['method'])
        self.assertEqual(result['mode'], main.LIVE_DEFAULT_MODE)
        self.assertIsInstance(result['elapsed_ms'], int)

    def test_live_mode_uses_fewer_tiles(self):
        """En vivo solo hay un nivel de mosaico y no se amplía el fotograma."""
        self.assertEqual(len(main.LIVE_TILE_LEVELS), 1)
        self.assertLess(len(main.LIVE_TILE_LEVELS), len(main.TILE_LEVELS))
        self.assertLessEqual(main.LIVE_MAX_DIMENSION, main.DETECT_MAX_DIMENSION)

    def test_each_live_mode_uses_its_input_size_and_tiles(self):
        calls = []
        original = main._detect_yolox
        main._detect_yolox = lambda image, levels, input_size: calls.append((input_size, levels)) or ([], [])
        try:
            frame = _jpeg(np.zeros((540, 960, 3), dtype=np.uint8))
            for mode in ('rapido', 'normal', 'preciso'):
                self.assertEqual(detect_bytes(frame, mode)['mode'], mode)
            # Un modo desconocido no falla: usa el de por defecto
            self.assertEqual(detect_bytes(frame, 'turbo')['mode'], main.LIVE_DEFAULT_MODE)
        finally:
            main._detect_yolox = original
        self.assertEqual(calls[:3], [main.LIVE_MODES[m] for m in ('rapido', 'normal', 'preciso')])
        self.assertLess(main.LIVE_MODES['rapido'][0], main.YOLOX_INPUT)

    def test_smaller_input_size_still_decodes_boxes(self):
        """La red acepta entradas menores que 640; la rejilla debe coincidir con su salida."""
        region = np.full((416, 416, 3), 114, dtype=np.uint8)
        boxes, scores = main._yolox_people(region, 416)
        self.assertEqual(boxes.shape[1] if len(boxes) else 4, 4)
        self.assertEqual(len(main._yolox_grid(416)[0]), sum((416 // s) ** 2 for s in main.YOLOX_STRIDES))

    def test_live_boxes_are_normalized(self):
        """Las cajas que se devuelven quedan dentro de 0-1 aunque la detección se salga del borde."""
        fake = [(950.0, 530.0, 40.0, 40.0, 0.9)]
        original = main._detect_people
        main._detect_people = lambda image, **_kwargs: (fake, 'prueba en vivo')
        try:
            result = detect_bytes(_jpeg(np.zeros((540, 960, 3), dtype=np.uint8)))
        finally:
            main._detect_people = original
        x, y, w, h, score = result['boxes'][0]
        self.assertAlmostEqual(x, 950 / 960, places=3)
        self.assertAlmostEqual(y, 530 / 540, places=3)
        self.assertEqual(score, 0.9)
        self.assertEqual(result['zone_counts']['C'], 1)


if __name__ == '__main__':
    unittest.main()
