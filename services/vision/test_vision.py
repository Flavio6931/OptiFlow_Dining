"""Pruebas unitarias del microservicio de visión (YOLOX con mosaico de recortes)."""
import unittest

import cv2
import numpy as np

from services.vision import main
from services.vision.main import _drop_partial_duplicates, _tile_origins, analyze_bytes


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


if __name__ == '__main__':
    unittest.main()
