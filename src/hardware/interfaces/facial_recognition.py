"""
Facial recognition interface using OpenCV and deep learning
"""
import cv2
import numpy as np
import time
import logging
from typing import Optional, Tuple, List, Dict, Any
import pickle
import face_recognition
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class FacialRecognition:
    """Facial recognition system using webcam or IP camera"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get("device_id", "camera_1")
        self.camera_index = config.get("camera_index", 0)
        self.camera_url = config.get("camera_url")  # For IP cameras
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self.face_detection_model = config.get("face_detection_model", "hog")  # "hog" or "cnn"
        self.face_encoding_model = config.get("face_encoding_model", "large")
        
        self.capture = None
        self.is_initialized = False
        self.known_faces = {}
        self.known_encodings = []
        self.known_ids = []
        self.last_recognition_time = None
        self.recognition_count = 0
        self.lock = threading.Lock()
        
        logger.info(f"Initializing facial recognition camera {self.device_id}")
    
    def initialize(self) -> bool:
        """Initialize camera for facial recognition"""
        try:
            if self.camera_url:
                # IP camera
                self.capture = cv2.VideoCapture(self.camera_url)
            else:
                # USB/webcam
                self.capture = cv2.VideoCapture(self.camera_index)
            
            if not self.capture.isOpened():
                logger.error(f"Failed to open camera {self.device_id}")
                return False
            
            # Test camera by capturing one frame
            ret, frame = self.capture.read()
            if not ret:
                logger.error(f"Failed to capture frame from camera {self.device_id}")
                return False
            
            # Load known faces from database or file
            self._load_known_faces()
            
            self.is_initialized = True
            logger.info(f"Facial recognition camera {self.device_id} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize facial recognition: {e}")
            return False
    
    def recognize_face(self, timeout: int = 5) -> Optional[Tuple[str, float]]:
        """Recognize face from camera feed"""
        if not self.is_connected():
            logger.error("Camera not connected")
            return None
        
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                ret, frame = self.capture.read()
                if not ret:
                    logger.warning(f"Failed to capture frame from camera {self.device_id}")
                    continue
                
                # Resize frame for faster processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                
                # Convert BGR (OpenCV) to RGB (face_recognition)
                rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Find faces in the frame
                face_locations = face_recognition.face_locations(
                    rgb_frame, 
                    model=self.face_detection_model
                )
                
                if face_locations:
                    # Get face encodings
                    face_encodings = face_recognition.face_encodings(
                        rgb_frame, 
                        face_locations, 
                        model=self.face_encoding_model
                    )
                    
                    for face_encoding in face_encodings:
                        # Compare with known faces
                        matches = face_recognition.compare_faces(
                            self.known_encodings, 
                            face_encoding
                        )
                        
                        face_distances = face_recognition.face_distance(
                            self.known_encodings, 
                            face_encoding
                        )
                        
                        # Find the best match
                        best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else -1
                        
                        if best_match_index >= 0 and matches[best_match_index]:
                            confidence = 1 - face_distances[best_match_index]
                            
                            if confidence >= self.confidence_threshold:
                                user_id = self.known_ids[best_match_index]
                                
                                with self.lock:
                                    self.last_recognition_time = time.time()
                                    self.recognition_count += 1
                                
                                logger.info(f"Face recognized: User {user_id}, Confidence: {confidence:.2f}")
                                return (user_id, float(confidence))
                        
                        logger.debug(f"No match found or confidence too low")
                
                # Small delay to prevent CPU overload
                time.sleep(0.1)
            
            return None
            
        except Exception as e:
            logger.error(f"Error in face recognition: {e}")
            return None
    
    def capture_face_embeddings(self, num_samples: int = 5) -> Optional[List[np.ndarray]]:
        """Capture multiple face samples for enrollment"""
        if not self.is_connected():
            return None
        
        try:
            embeddings = []
            samples_captured = 0
            
            logger.info(f"Starting face capture for enrollment. Please look at the camera.")
            
            while samples_captured < num_samples:
                ret, frame = self.capture.read()
                if not ret:
                    continue
                
                # Resize for processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Detect face
                face_locations = face_recognition.face_locations(rgb_frame, model=self.face_detection_model)
                
                if len(face_locations) == 1:  # Exactly one face
                    face_encoding = face_recognition.face_encodings(
                        rgb_frame, 
                        face_locations, 
                        model=self.face_encoding_model
                    )[0]
                    
                    embeddings.append(face_encoding)
                    samples_captured += 1
                    
                    # Visual feedback
                    cv2.putText(frame, f"Sample {samples_captured}/{num_samples}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow("Enrollment", frame)
                    cv2.waitKey(500)  # Brief pause between samples
                
                elif len(face_locations) > 1:
                    logger.warning("Multiple faces detected. Please ensure only one person is in frame.")
                else:
                    logger.warning("No face detected. Please look at the camera.")
                
                time.sleep(0.5)
            
            cv2.destroyAllWindows()
            logger.info(f"Captured {len(embeddings)} face samples")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error capturing face embeddings: {e}")
            cv2.destroyAllWindows()
            return None
    
    def add_known_face(self, user_id: str, embeddings: List[np.ndarray]) -> bool:
        """Add new face to known faces database"""
        try:
            with self.lock:
                for embedding in embeddings:
                    self.known_encodings.append(embedding)
                    self.known_ids.append(user_id)
                
                self.known_faces[user_id] = embeddings
                
                # Save to file
                self._save_known_faces()
                
            logger.info(f"Added face for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding known face: {e}")
            return False
    
    def remove_known_face(self, user_id: str) -> bool:
        """Remove face from known faces"""
        try:
            with self.lock:
                if user_id in self.known_faces:
                    # Find and remove all entries for this user
                    indices = [i for i, uid in enumerate(self.known_ids) if uid == user_id]
                    
                    for index in sorted(indices, reverse=True):
                        del self.known_encodings[index]
                        del self.known_ids[index]
                    
                    del self.known_faces[user_id]
                    
                    # Save to file
                    self._save_known_faces()
                    
                    logger.info(f"Removed face for user {user_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing known face: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self.is_initialized and self.capture and self.capture.isOpened()
    
    def disconnect(self):
        """Disconnect camera"""
        try:
            if self.capture:
                self.capture.release()
            
            cv2.destroyAllWindows()
            self.is_initialized = False
            logger.info(f"Camera {self.device_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting camera: {e}")
    
    def _load_known_faces(self):
        """Load known faces from file"""
        try:
            with open(f"hardware/data/faces_{self.device_id}.pkl", "rb") as f:
                data = pickle.load(f)
                self.known_faces = data.get("known_faces", {})
                self.known_encodings = data.get("encodings", [])
                self.known_ids = data.get("ids", [])
            
            logger.info(f"Loaded {len(self.known_faces)} known faces")
            
        except FileNotFoundError:
            logger.info("No known faces file found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading known faces: {e}")
    
    def _save_known_faces(self):
        """Save known faces to file"""
        try:
            data = {
                "known_faces": self.known_faces,
                "encodings": self.known_encodings,
                "ids": self.known_ids,
                "updated": datetime.now().isoformat()
            }
            
            with open(f"hardware/data/faces_{self.device_id}.pkl", "wb") as f:
                pickle.dump(data, f)
            
            logger.debug(f"Saved {len(self.known_faces)} known faces to file")
            
        except Exception as e:
            logger.error(f"Error saving known faces: {e}")
    
    def get_frame(self):
        """Get current frame from camera (for display purposes)"""
        if not self.is_connected():
            return None
        
        try:
            ret, frame = self.capture.read()
            if ret:
                return frame
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
        
        return None