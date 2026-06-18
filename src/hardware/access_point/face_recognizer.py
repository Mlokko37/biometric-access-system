"""
Face Recognizer - Handles face recognition on the access point
"""
import cv2
import face_recognition
import numpy as np
import pickle
import os
import requests
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class FaceRecognizer:
    """Face recognition for access point"""
    
    def __init__(self, confidence_threshold=0.6):
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.confidence_threshold = confidence_threshold
        self.last_recognition_time = None
        self.recognition_count = 0
    
    def load_encodings(self, encodings_data: List[Dict[str, Any]]):
        """Load face encodings from data"""
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        
        for student in encodings_data:
            if 'encoding' in student and student['encoding']:
                # Parse encoding if it's a string
                encoding = student['encoding']
                if isinstance(encoding, str):
                    import json
                    encoding = json.loads(encoding)
                
                self.known_face_encodings.append(np.array(encoding))
                self.known_face_ids.append(student['student_id'])
                self.known_face_names.append(student['name'])
        
        logger.info(f"Loaded {len(self.known_face_encodings)} face encodings")
    
    def load_encodings_from_file(self, filepath: str) -> bool:
        """Load face encodings from pickle file"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    data = pickle.load(f)
                    self.known_face_encodings = data.get('encodings', [])
                    self.known_face_ids = data.get('ids', [])
                    self.known_face_names = data.get('names', [])
                logger.info(f"Loaded {len(self.known_face_encodings)} encodings from {filepath}")
                return True
            except Exception as e:
                logger.error(f"Error loading encodings: {e}")
        return False
    
    def recognize(self, frame) -> List[Dict[str, Any]]:
        """Recognize faces in a frame"""
        results = []
        
        if not self.known_face_encodings:
            return results
        
        try:
            # Convert to RGB for face_recognition
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(rgb_frame)
            if not face_locations:
                return results
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            for encoding in face_encodings:
                # Compare with known faces
                distances = face_recognition.face_distance(self.known_face_encodings, encoding)
                
                if len(distances) > 0:
                    best_match_idx = np.argmin(distances)
                    confidence = 1 - distances[best_match_idx]
                    
                    if confidence >= self.confidence_threshold:
                        results.append({
                            'student_id': self.known_face_ids[best_match_idx],
                            'name': self.known_face_names[best_match_idx],
                            'confidence': float(confidence),
                            'distance': float(distances[best_match_idx])
                        })
            
            # Sort by confidence
            results.sort(key=lambda x: x['confidence'], reverse=True)
            self.last_recognition_time = datetime.utcnow()
            self.recognition_count += 1
            
        except Exception as e:
            logger.error(f"Error in recognition: {e}")
        
        return results
    
    def get_best_match(self, frame) -> Tuple[Optional[int], Optional[float], Optional[str]]:
        """Get the best matching face in a frame"""
        results = self.recognize(frame)
        if results:
            best = results[0]
            return (best['student_id'], best['confidence'], best['name'])
        return (None, None, None)
    
    def draw_recognition_result(self, frame, result: Dict[str, Any], box_color=(0, 255, 0)):
        """Draw recognition result on frame"""
        if result:
            text = f"{result.get('name', 'Unknown')} ({result.get('confidence', 0):.2f})"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
        return frame
    
    def get_stats(self) -> Dict[str, Any]:
        """Get recognition statistics"""
        return {
            'enrolled_faces': len(self.known_face_encodings),
            'recognition_count': self.recognition_count,
            'last_recognition': self.last_recognition_time.isoformat() if self.last_recognition_time else None,
            'confidence_threshold': self.confidence_threshold
        }