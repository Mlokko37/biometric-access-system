"""
Facial Recognition Camera Driver
Supports: USB Cameras, Webcams, IP Cameras
"""

import cv2
import numpy as np
import logging
import time
import os
from typing import Optional, Dict, Any, List, Tuple
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

class FacialCamera:
    """Driver for facial recognition cameras."""
    
    def __init__(self, camera_index: int = 0, ip_camera_url: Optional[str] = None):
        """
        Initialize facial camera.
        
        Args:
            camera_index: Index of USB camera (0, 1, 2, etc.)
            ip_camera_url: RTSP URL for IP camera (e.g., 'rtsp://192.168.1.100:554/stream')
        """
        self.camera_index = camera_index
        self.ip_camera_url = ip_camera_url
        self.cap = None
        self.connected = False
        self.width = 640
        self.height = 480
        self.fps = 30
        self.face_cascade = None
        self.eye_cascade = None
        self.profile_cascade = None  # Added missing attribute
        
        # Initialize face detection
        self._init_face_detection()
    
    def _init_face_detection(self):
        """Initialize OpenCV face detection cascades."""
        try:
            # Try to load Haar cascades
            cascade_path = cv2.data.haarcascades
            
            self.face_cascade = cv2.CascadeClassifier(
                os.path.join(cascade_path, 'haarcascade_frontalface_default.xml')
            )
            
            self.eye_cascade = cv2.CascadeClassifier(
                os.path.join(cascade_path, 'haarcascade_eye.xml')
            )
            
            # Also try profile cascade for side faces
            self.profile_cascade = cv2.CascadeClassifier(
                os.path.join(cascade_path, 'haarcascade_profileface.xml')
            )
            
            logger.info("Face detection cascades loaded")
            
        except Exception as e:
            logger.error(f"Failed to load face detection cascades: {e}")
    
    def initialize(self) -> bool:
        """Initialize camera connection."""
        try:
            if self.ip_camera_url:
                # Connect to IP camera
                self.cap = cv2.VideoCapture(self.ip_camera_url)
            else:
                # Connect to USB camera
                self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap or not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_index}")
                return False
            
            # Get camera properties
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            
            if self.fps <= 0:
                self.fps = 30  # Default
            
            self.connected = True
            logger.info(f"Camera initialized: {self.width}x{self.height} @ {self.fps}fps")
            
            return True
            
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get camera information."""
        return {
            'type': 'IP Camera' if self.ip_camera_url else 'USB Camera',
            'index': self.camera_index,
            'url': self.ip_camera_url,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'connected': self.connected,
            'face_detection': self.face_cascade is not None
        }
    
    def capture_frame(self, timeout: int = 5) -> Optional[np.ndarray]:
        """
        Capture a single frame from camera.
        
        Args:
            timeout: Maximum time to wait for frame in seconds
            
        Returns:
            Frame as numpy array or None
        """
        if not self.connected or not self.cap:
            logger.error("Camera not initialized")
            return None
        
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    return frame
                
                time.sleep(0.1)
            
            logger.warning("Timeout waiting for frame")
            return None
            
        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return None
    
    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces in frame.
        
        Args:
            frame: Image frame
            
        Returns:
            List of detected faces with bounding boxes
        """
        if not self.face_cascade:
            logger.warning("Face detection not available")
            return []
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            detected_faces = []
            
            for (x, y, w, h) in faces:
                face_info = {
                    'bbox': (x, y, w, h),
                    'center': (x + w//2, y + h//2),
                    'size': w * h,
                    'confidence': self._calculate_face_confidence(gray[y:y+h, x:x+w])
                }
                
                # Detect eyes within face region
                roi_gray = gray[y:y+h, x:x+w]
                if self.eye_cascade:
                    eyes = self.eye_cascade.detectMultiScale(roi_gray)
                    face_info['eyes'] = len(eyes)
                
                detected_faces.append(face_info)
            
            logger.debug(f"Detected {len(detected_faces)} faces")
            return detected_faces
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []
    
    def _calculate_face_confidence(self, face_roi: np.ndarray) -> float:
        """Calculate confidence score for detected face."""
        # Simple confidence based on image properties
        if face_roi.size == 0:
            return 0.0
        
        # Calculate sharpness using Laplacian variance
        laplacian_var = cv2.Laplacian(face_roi, cv2.CV_64F).var()
        
        # Normalize to 0-100
        sharpness_score = min(laplacian_var / 100, 1.0) * 100
        
        # Check brightness
        mean_brightness = np.mean(face_roi)
        brightness_score = 100 - abs(mean_brightness - 128) / 1.28
        
        # Combined score
        confidence = (sharpness_score * 0.6 + brightness_score * 0.4)
        
        return round(float(confidence), 2)
    
    def capture_face(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Capture a face for enrollment/verification.
        
        Args:
            timeout: Maximum time to wait for face in seconds
            
        Returns:
            Dictionary with face data or None
        """
        logger.info("Waiting for face...")
        
        start_time = time.time()
        best_face = None
        best_quality = 0.0
        
        while time.time() - start_time < timeout:
            frame = self.capture_frame(timeout=1)
            
            if frame is not None:
                faces = self.detect_faces(frame)
                
                for face in faces:
                    if face['confidence'] > best_quality:
                        best_quality = face['confidence']
                        
                        # Extract face region
                        x, y, w, h = face['bbox']
                        face_img = frame[y:y+h, x:x+w]
                        
                        best_face = {
                            'image': face_img,
                            'full_frame': frame,
                            'bbox': face['bbox'],
                            'quality': face['confidence'],
                            'timestamp': time.time()
                        }
            
            if best_quality > 80:  # Good quality face captured
                break
            
            time.sleep(0.1)
        
        if best_face:
            logger.info(f"Face captured with quality {best_quality:.1f}")
            return best_face
        else:
            logger.warning("No face detected")
            return None
    
    def generate_template(self, face_data: Dict[str, Any]) -> Optional[bytes]:
        """
        Generate biometric template from face image.
        
        Args:
            face_data: Face data from capture_face()
            
        Returns:
            Face template as bytes or None
        """
        try:
            face_img = face_data['image']
            
            # Resize to standard size
            face_img = cv2.resize(face_img, (128, 128))
            
            # Convert to grayscale
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            
            # Extract features (simplified - in production use face recognition library)
            # This is just a placeholder - use face_recognition or dlib for real implementation
            features = self._extract_simple_features(gray)
            
            # Convert features to bytes
            template = features.tobytes()
            
            return template
            
        except Exception as e:
            logger.error(f"Template generation error: {e}")
            return None
    
    def _extract_simple_features(self, face_img: np.ndarray) -> np.ndarray:
        """Extract simple features from face image (placeholder)."""
        # This is a simplified feature extraction
        # In production, use deep learning models like FaceNet, OpenFace, etc.
        
        # Resize to smaller size
        small = cv2.resize(face_img, (32, 32))
        
        # Flatten and normalize
        features = small.flatten().astype(np.float32)
        features = features / 255.0
        
        return features
    
    def verify_face(self, stored_template: bytes) -> Tuple[bool, float]:
        """
        Verify face against stored template.
        
        Args:
            stored_template: Previously stored face template
            
        Returns:
            Tuple of (success, match_score)
        """
        print("\n[CAMERA] Look at the camera for verification")
        input("Press Enter when ready...")
        
        # Capture face
        face_data = self.capture_face(timeout=30)
        
        if not face_data:
            print("[ERROR] Failed to capture face")
            return False, 0.0
        
        # Generate template from captured face
        captured_template = self.generate_template(face_data)
        
        if not captured_template:
            print("[ERROR] Failed to generate template")
            return False, 0.0
        
        # Compare templates
        match_score = self._compare_templates(stored_template, captured_template)
        
        if match_score >= 75:  # Threshold
            print(f"[OK] Face match found! Score: {match_score:.1f}%")
            return True, match_score
        else:
            print(f"[ERROR] No match. Score: {match_score:.1f}%")
            return False, match_score
    
    def _compare_templates(self, template1: bytes, template2: bytes) -> float:
        """Compare two face templates."""
        # This is a placeholder. Use proper face recognition in production
        
        if len(template1) != len(template2):
            return 0.0
        
        try:
            # Convert back to numpy arrays
            arr1 = np.frombuffer(template1, dtype=np.float32)
            arr2 = np.frombuffer(template2, dtype=np.float32)
            
            # Calculate cosine similarity
            dot_product = np.dot(arr1, arr2)
            norm1 = np.linalg.norm(arr1)
            norm2 = np.linalg.norm(arr2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            
            # Convert to percentage
            score = (similarity + 1) * 50  # Scale from -1:1 to 0:100
            
            return round(float(score), 2)
            
        except Exception as e:
            logger.error(f"Template comparison error: {e}")
            return 0.0
    
    def start_video_stream(self, window_name: str = "Camera Feed"):
        """Start live video stream window."""
        if not self.connected:
            logger.error("Camera not initialized")
            return
        
        print(f"\n📹 Starting video stream. Press 'q' to quit.")
        
        try:
            while True:
                frame = self.capture_frame(timeout=1)
                
                if frame is not None:
                    # Detect faces
                    faces = self.detect_faces(frame)
                    
                    # Draw face rectangles
                    for face in faces:
                        x, y, w, h = face['bbox']
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        
                        # Add confidence text
                        text = f"{face['confidence']:.1f}%"
                        cv2.putText(frame, text, (x, y-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Show frame
                    cv2.imshow(window_name, frame)
                
                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            cv2.destroyAllWindows()
            
        except Exception as e:
            logger.error(f"Video stream error: {e}")
    
    def disconnect(self):
        """Disconnect camera."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            self.connected = False
            logger.info("Camera disconnected")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()