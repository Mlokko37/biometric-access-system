"""
Face Recognition Service – Optional.
If face_recognition is not installed, this service will log warnings and return empty results.
"""
import logging
import numpy as np
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import face_recognition; if missing, use a dummy
try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
    logger.info("face_recognition library loaded successfully")
except ImportError:
    HAS_FACE_RECOGNITION = False
    logger.warning("face_recognition not available – face recognition features disabled")

class FaceRecognitionService:
    """Service for face encoding and recognition – gracefully handles missing library."""
    
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.known_face_data = []  # store additional info
    
    def add_face(self, student_id: str, name: str, face_encoding: List[float]) -> bool:
        """Add a face encoding to the known list."""
        if not HAS_FACE_RECOGNITION:
            logger.warning("face_recognition not installed – cannot add face")
            return False
        try:
            encoding = np.array(face_encoding)
            self.known_face_encodings.append(encoding)
            self.known_face_ids.append(student_id)
            self.known_face_names.append(name)
            self.known_face_data.append({'student_id': student_id, 'name': name})
            return True
        except Exception as e:
            logger.error(f"Error adding face: {e}")
            return False
    
    def recognize_face(self, face_image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Recognize faces in an image.
        Returns list of matches sorted by confidence.
        """
        if not HAS_FACE_RECOGNITION:
            logger.error("face_recognition not installed – cannot recognize")
            return []
        if not self.known_face_encodings:
            return []
        try:
            # Resize for speed
            small_image = face_recognition.resize_image(face_image, width=320)
            rgb_image = face_image[:, :, ::-1]  # BGR to RGB
            face_locations = face_recognition.face_locations(rgb_image)
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            results = []
            for encoding in face_encodings:
                distances = face_recognition.face_distance(self.known_face_encodings, encoding)
                best_match_index = np.argmin(distances)
                if distances[best_match_index] < 0.6:  # threshold
                    confidence = 1 - distances[best_match_index]
                    results.append({
                        'student_id': self.known_face_ids[best_match_index],
                        'name': self.known_face_names[best_match_index],
                        'confidence': float(confidence),
                        'distance': float(distances[best_match_index])
                    })
            # sort by confidence
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results
        except Exception as e:
            logger.error(f"Error during face recognition: {e}")
            return []
    
    def get_all_students(self) -> List[Dict[str, Any]]:
        """Return all known students with encodings (for sync)."""
        if not HAS_FACE_RECOGNITION:
            return []
        students = []
        for i, student_id in enumerate(self.known_face_ids):
            students.append({
                'student_id': student_id,
                'name': self.known_face_names[i],
                'encoding': self.known_face_encodings[i].tolist()
            })
        return students
    
    def clear(self):
        """Clear all known faces."""
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.known_face_data = []

# Singleton instance
_face_service = None

def get_face_recognition_service() -> FaceRecognitionService:
    global _face_service
    if _face_service is None:
        _face_service = FaceRecognitionService()
    return _face_service