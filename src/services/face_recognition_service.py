"""
Face Recognition Service - Core face recognition functionality
"""
import os
import cv2
import face_recognition
import numpy as np
import pickle
import json
import base64
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image
import io
import logging

from src.database.connection import execute_query

logger = logging.getLogger(__name__)

class FaceRecognitionService:
    """Service for face recognition operations"""
    
    def __init__(self, encodings_file=None, confidence_threshold=0.6):
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.confidence_threshold = confidence_threshold
        
        # Set default encodings file path
        if encodings_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.encodings_file = os.path.join(base_dir, 'data', 'face_encodings.pkl')
        else:
            self.encodings_file = encodings_file
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.encodings_file), exist_ok=True)
        
        # Load existing encodings
        self.load_encodings()
    
    def load_encodings(self) -> bool:
        """Load face encodings from pickle file"""
        if os.path.exists(self.encodings_file):
            try:
                with open(self.encodings_file, 'rb') as f:
                    data = pickle.load(f)
                    self.known_face_encodings = data.get('encodings', [])
                    self.known_face_ids = data.get('ids', [])
                    self.known_face_names = data.get('names', [])
                logger.info(f"Loaded {len(self.known_face_encodings)} face encodings from file")
                return True
            except Exception as e:
                logger.error(f"Error loading encodings: {e}")
                return False
        
        # Try to load from database
        try:
            self.load_encodings_from_db()
            return True
        except Exception as e:
            logger.error(f"Error loading encodings from database: {e}")
            return False
    
    def load_encodings_from_db(self):
        """Load face encodings from database"""
        try:
            # Get all face encodings from database
            results = execute_query(
                """SELECT fe.id, fe.student_id, fe.encoding, fe.is_primary, 
                          s.first_name, s.last_name 
                   FROM face_encodings fe
                   JOIN students s ON fe.student_id = s.id
                   WHERE s.is_active = TRUE"""
            )
            
            if results:
                for row in results:
                    student_id = row['student_id']
                    encoding_json = row['encoding']
                    first_name = row['first_name']
                    last_name = row['last_name']
                    
                    # Parse encoding from JSON
                    encoding = json.loads(encoding_json)
                    
                    self.known_face_encodings.append(np.array(encoding))
                    self.known_face_ids.append(student_id)
                    self.known_face_names.append(f"{first_name} {last_name}")
                
                # Save to file for faster loading next time
                self.save_encodings()
                logger.info(f"Loaded {len(self.known_face_encodings)} face encodings from database")
            else:
                logger.info("No face encodings found in database")
                
        except Exception as e:
            logger.error(f"Error loading encodings from database: {e}")
            raise
    
    def save_encodings(self) -> bool:
        """Save face encodings to pickle file"""
        try:
            data = {
                'encodings': self.known_face_encodings,
                'ids': self.known_face_ids,
                'names': self.known_face_names
            }
            with open(self.encodings_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Saved {len(self.known_face_encodings)} face encodings to file")
            return True
        except Exception as e:
            logger.error(f"Error saving encodings: {e}")
            return False
    
    def add_face_encoding(self, student_id: int, student_name: str, face_image) -> bool:
        """
        Add a new face encoding for a student
        
        Args:
            student_id: Student ID
            student_name: Student's full name
            face_image: Image containing the face (numpy array or file path)
        
        Returns:
            bool: True if successful
        """
        try:
            # Load image if path provided
            if isinstance(face_image, str):
                image = cv2.imread(face_image)
                if image is None:
                    logger.error(f"Failed to load image: {face_image}")
                    return False
            else:
                image = face_image
            
            # Convert BGR to RGB (face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                logger.error("No face detected in image")
                return False
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            if not face_encodings:
                logger.error("Failed to generate face encoding")
                return False
            
            # Add the first face encoding
            encoding = face_encodings[0]
            encoding_json = json.dumps(encoding.tolist())
            
            # Check if student already has an encoding
            existing = execute_query(
                "SELECT id FROM face_encodings WHERE student_id = %s AND is_primary = TRUE",
                (student_id,)
            )
            
            if existing:
                # Update existing encoding
                execute_query(
                    """UPDATE face_encodings 
                       SET encoding = %s, updated_at = %s 
                       WHERE student_id = %s AND is_primary = TRUE""",
                    (encoding_json, datetime.utcnow(), student_id)
                )
            else:
                # Insert new encoding
                execute_query(
                    """INSERT INTO face_encodings 
                       (student_id, encoding, is_primary, created_at, updated_at)
                       VALUES (%s, %s, TRUE, %s, %s)""",
                    (student_id, encoding_json, datetime.utcnow(), datetime.utcnow())
                )
            
            # Update in-memory cache
            if student_id in self.known_face_ids:
                idx = self.known_face_ids.index(student_id)
                self.known_face_encodings[idx] = encoding
                self.known_face_names[idx] = student_name
            else:
                self.known_face_encodings.append(encoding)
                self.known_face_ids.append(student_id)
                self.known_face_names.append(student_name)
            
            # Save to file
            self.save_encodings()
            logger.info(f"Added face encoding for student {student_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding face encoding: {e}")
            return False
    
    def remove_face_encoding(self, student_id: int) -> bool:
        """Remove a student's face encoding"""
        try:
            # Delete from database
            execute_query(
                "DELETE FROM face_encodings WHERE student_id = %s",
                (student_id,)
            )
            
            # Remove from in-memory cache
            if student_id in self.known_face_ids:
                idx = self.known_face_ids.index(student_id)
                del self.known_face_encodings[idx]
                del self.known_face_ids[idx]
                del self.known_face_names[idx]
                self.save_encodings()
                logger.info(f"Removed face encoding for student {student_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error removing face encoding: {e}")
            return False
    
    def recognize_face(self, face_image, max_results: int = 1) -> List[Dict[str, Any]]:
        """
        Recognize a face in an image
        
        Args:
            face_image: Image containing face(s)
            max_results: Maximum number of results to return
        
        Returns:
            List of dicts with student_id, name, and confidence
        """
        results = []
        
        if not self.known_face_encodings:
            return results
        
        try:
            # Load image if path provided
            if isinstance(face_image, str):
                image = cv2.imread(face_image)
                if image is None:
                    logger.error(f"Failed to load image: {face_image}")
                    return results
            else:
                image = face_image
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(rgb_image)
            if not face_locations:
                return results
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            
            for encoding in face_encodings:
                # Compare with known faces
                distances = face_recognition.face_distance(self.known_face_encodings, encoding)
                
                if len(distances) > 0:
                    # Find best match
                    best_match_idx = np.argmin(distances)
                    confidence = 1 - distances[best_match_idx]
                    
                    if confidence >= self.confidence_threshold:
                        results.append({
                            'student_id': self.known_face_ids[best_match_idx],
                            'name': self.known_face_names[best_match_idx],
                            'confidence': float(confidence),
                            'distance': float(distances[best_match_idx])
                        })
            
            # Sort by confidence and limit results
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Error recognizing face: {e}")
            return results
    
    def get_student_count(self) -> int:
        """Get number of enrolled students"""
        return len(self.known_face_ids)
    
    def get_all_students(self) -> List[Dict[str, Any]]:
        """Get all enrolled students"""
        students = []
        for i, student_id in enumerate(self.known_face_ids):
            students.append({
                'student_id': student_id,
                'name': self.known_face_names[i]
            })
        return students
    
    def encode_face_from_image(self, image_data) -> Optional[np.ndarray]:
        """
        Generate face encoding from image data
        
        Args:
            image_data: Image data (base64 string or numpy array)
        
        Returns:
            Face encoding as numpy array or None
        """
        try:
            # Handle base64 input
            if isinstance(image_data, str):
                # Decode base64
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                image = np.array(image)
                
                # Convert to RGB if needed
                if len(image.shape) == 3 and image.shape[2] == 4:
                    image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
                elif len(image.shape) == 3 and image.shape[2] == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image = image_data
            
            # Detect faces
            face_locations = face_recognition.face_locations(image)
            if not face_locations:
                return None
            
            # Get encoding
            encodings = face_recognition.face_encodings(image, face_locations)
            if not encodings:
                return None
            
            return encodings[0]
            
        except Exception as e:
            logger.error(f"Error encoding face: {e}")
            return None
    
    def detect_faces(self, image) -> List[Dict[str, Any]]:
        """
        Detect faces in an image without recognition
        
        Args:
            image: Image to detect faces in
        
        Returns:
            List of face locations with bounding boxes
        """
        try:
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return []
            
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
            
            results = []
            for (top, right, bottom, left) in face_locations:
                results.append({
                    'top': top,
                    'right': right,
                    'bottom': bottom,
                    'left': left,
                    'width': right - left,
                    'height': bottom - top
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []

# Singleton instance
_face_recognition_service = None

def get_face_recognition_service():
    """Get singleton instance of FaceRecognitionService"""
    global _face_recognition_service
    if _face_recognition_service is None:
        _face_recognition_service = FaceRecognitionService()
    return _face_recognition_service