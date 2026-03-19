import io
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_cascade = None


def _get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    if _cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(cascade_path)
    return _cascade


def detect_face_in_image_bytes(data: bytes) -> bool:
    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade = _get_cascade()
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=4,
            minSize=(30, 30),
        )
        return len(faces) > 0
    except Exception as e:
        logger.warning(f"Erro na deteccao de rosto: {e}")
        return False
