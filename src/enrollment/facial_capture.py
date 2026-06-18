import os
import sys
import logging
import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict, Any, Union
import time
import base64
from datetime import datetime

logger = logging.getLogger(__name__)

class FacialCapture:
    """Handles real facial image capture and feature extraction."""
    
    def __init__(self, camera_index: int = 0, simulation_mode: bool = False):
        """Initialize facial capture system."""
        self.camera_index = camera_index
        self.simulation_mode = simulation_mode
        self.camera = None
        self.face_cascade = None
        self.eye_cascade = None
        self.smile_cascade = None
        
        if not simulation_mode:
            self.initialize_camera()
            self.load_face_detectors()
    
    def initialize_camera(self) -> bool:
        """Initialize webcam connection."""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            
            if not self.camera.isOpened():
                logger.error(f"Cannot open camera index {self.camera_index}")
                self.camera = None
                return False
            
            # Set camera properties for better face capture
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
            
            # Warm up camera
            for _ in range(10):
                self.camera.read()
            
            logger.info(f"Camera initialized successfully (index {self.camera_index})")
            return True
            
        except Exception as e:
            logger.error(f"Camera initialization failed: {str(e)}")
            self.camera = None
            return False
    
    def load_face_detectors(self):
        """Load face detection cascades."""
        try:
            # Load pre-trained classifiers
            cascade_path = cv2.data.haarcascades
            
            self.face_cascade = cv2.CascadeClassifier(
                cascade_path + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cascade_path + 'haarcascade_eye.xml'
            )
            self.smile_cascade = cv2.CascadeClassifier(
                cascade_path + 'haarcascade_smile.xml'
            )
            
            if self.face_cascade.empty():
                logger.error("Failed to load face cascade classifier")
                self.face_cascade = None
                return False
            
            logger.info("Face detectors loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Face detector loading failed: {str(e)}")
            self.face_cascade = None
            return False
    
    def capture_frame(self, timeout: int = 10) -> Optional[np.ndarray]:
        """Capture a single frame from camera."""
        if self.camera is None:
            logger.error("Camera not initialized")
            return None
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            ret, frame = self.camera.read()
            if ret:
                return frame
            
            time.sleep(0.1)
        
        logger.error(f"Failed to capture frame within {timeout} seconds")
        return None
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces in a frame."""
        if self.face_cascade is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100),
            maxSize=(500, 500)
        )
        
        # Convert numpy array to list of tuples
        if len(faces) > 0:
            return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        return []
    
    def detect_eyes(self, frame: np.ndarray, face_rect: Tuple[int, int, int, int]) -> List[Tuple[int, int, int, int]]:
        """Detect eyes within face region."""
        if self.eye_cascade is None:
            return []
        
        x, y, w, h = face_rect
        face_roi = frame[y:y+h, x:x+w]
        gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        eyes = self.eye_cascade.detectMultiScale(
            gray_roi,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(20, 20)
        )
        
        # Adjust coordinates to full frame
        return [(int(x+ex), int(y+ey), int(ew), int(eh)) for (ex, ey, ew, eh) in eyes]
    
    def extract_face_region(self, frame: np.ndarray, face_rect: Tuple[int, int, int, int]) -> np.ndarray:
        """Extract and preprocess face region."""
        x, y, w, h = face_rect
        
        # Add padding
        padding = int(min(w, h) * 0.2)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)
        
        face_region = frame[y1:y2, x1:x2]
        
        # Resize to standard size for face recognition
        face_region = cv2.resize(face_region, (224, 224))
        
        return face_region
    
    def calculate_face_quality(self, frame: np.ndarray, face_rect: Tuple[int, int, int, int]) -> Dict[str, float]:
        """Calculate face image quality metrics."""
        x, y, w, h = face_rect
        face_roi = frame[y:y+h, x:x+w]
        gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        metrics = {}
        
        # 1. Sharpness (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
        metrics['sharpness'] = min(100.0, laplacian_var / 10)
        
        # 2. Brightness
        brightness = np.mean(gray_roi)
        metrics['brightness'] = 100.0 - abs(brightness - 128) * 0.5
        
        # 3. Contrast
        contrast = np.std(gray_roi)
        metrics['contrast'] = min(100.0, contrast)
        
        # 4. Face size relative to frame
        frame_area = frame.shape[0] * frame.shape[1]
        face_area = w * h
        metrics['face_size'] = min(100.0, (face_area / frame_area) * 500)
        
        # 5. Eye presence
        eyes = self.detect_eyes(frame, face_rect)
        metrics['eyes_detected'] = float(len(eyes) * 50)  # 50 per eye
        
        # Combined quality score
        metrics['overall'] = (
            metrics['sharpness'] * 0.25 +
            metrics['brightness'] * 0.2 +
            metrics['contrast'] * 0.15 +
            metrics['face_size'] * 0.25 +
            min(metrics['eyes_detected'], 100.0) * 0.15
        )
        
        return metrics
    
    def capture_face(self, angle_description: str = "front", 
                    min_quality: float = 50.0) -> Optional[Dict[str, Any]]:
        """
        Capture a face image with quality validation.
        
        Args:
            angle_description: Description of face angle
            min_quality: Minimum acceptable quality score
            
        Returns:
            Dict with image data and metadata or None if failed
        """
        try:
            logger.info(f"Capturing facial image: {angle_description}")
            
            # Capture frame
            frame = self.capture_frame(timeout=15)
            if frame is None:
                logger.error("Failed to capture frame")
                return None
            
            # Detect faces
            faces = self.detect_faces(frame)
            
            if len(faces) == 0:
                logger.warning("No face detected")
                return None
            
            # Use the largest face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            face_rect = faces[0]
            
            # Calculate quality
            quality_metrics = self.calculate_face_quality(frame, face_rect)
            
            if quality_metrics['overall'] < min_quality:
                logger.warning(f"Face quality too low: {quality_metrics['overall']:.1f}")
                return None
            
            # Extract face region
            face_region = self.extract_face_region(frame, face_rect)
            
            # Encode image
            _, buffer = cv2.imencode('.jpg', face_region, [cv2.IMWRITE_JPEG_QUALITY, 95])
            image_bytes = buffer.tobytes()
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Create result
            result = {
                'image_bytes': image_bytes,
                'image_b64': image_b64,
                'face_rect': face_rect,
                'quality': float(quality_metrics['overall']),
                'quality_metrics': quality_metrics,
                'angle': angle_description,
                'timestamp': datetime.now().isoformat(),
                'width': face_region.shape[1],
                'height': face_region.shape[0]
            }
            
            logger.info(f"Face captured successfully: {angle_description} (Quality: {quality_metrics['overall']:.1f})")
            return result
            
        except Exception as e:
            logger.error(f"Facial capture error: {str(e)}", exc_info=True)
            return None
    
    def capture_multiple_angles(self, angles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Capture face from multiple angles."""
        if angles is None:
            angles = ['front', 'left', 'right', 'up', 'down', 'smile']
        
        results = []
        
        print("\nFacial Capture Guide:")
        print("-" * 40)
        print("Please position yourself for each angle")
        print("Press SPACE to capture, ESC to skip angle")
        
        for angle in angles:
            print(f"\n{angle.upper()} view:")
            print("Look straight at camera")
            
            # Show preview window
            cv2.namedWindow('Facial Capture', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Facial Capture', 640, 480)
            
            captured = False
            while not captured:
                frame = self.capture_frame(timeout=5)
                if frame is None:
                    continue
                
                # Detect faces for preview
                faces = self.detect_faces(frame)
                display = frame.copy()
                
                for (x, y, w, h) in faces:
                    cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Calculate and display quality
                    metrics = self.calculate_face_quality(frame, (x, y, w, h))
                    cv2.putText(display, f"Quality: {metrics['overall']:.1f}", 
                               (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                cv2.putText(display, f"Angle: {angle}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(display, "SPACE: Capture  ESC: Skip", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                cv2.imshow('Facial Capture', display)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 32:  # SPACE
                    result = self.capture_face(angle)
                    if result:
                        results.append(result)
                        captured = True
                        print(f"[OK] {angle} captured (Quality: {result['quality']:.1f})")
                elif key == 27:  # ESC
                    print(f"⏭️ Skipping {angle}")
                    captured = True
            
            cv2.destroyWindow('Facial Capture')
        
        return results
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information."""
        if self.camera is None:
            return {'error': 'Camera not initialized'}
        
        # Get backend name safely
        try:
            backend_name = cv2.videoio_registry.getBackendName(int(self.camera.get(cv2.CAP_PROP_BACKEND)))
        except (AttributeError, TypeError, ValueError):
            backend_name = "Unknown"
        
        info = {
            'index': self.camera_index,
            'backend': backend_name,
            'width': int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': float(self.camera.get(cv2.CAP_PROP_FPS)),
            'brightness': float(self.camera.get(cv2.CAP_PROP_BRIGHTNESS)),
            'contrast': float(self.camera.get(cv2.CAP_PROP_CONTRAST)),
            'saturation': float(self.camera.get(cv2.CAP_PROP_SATURATION)),
            'hue': float(self.camera.get(cv2.CAP_PROP_HUE)),
            'gain': float(self.camera.get(cv2.CAP_PROP_GAIN)),
            'exposure': float(self.camera.get(cv2.CAP_PROP_EXPOSURE))
        }
        
        return info
    
    def cleanup(self):
        """Clean up camera resources."""
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
        logger.info("Camera resources cleaned up")


def test_facial_capture():
    """Test function for real facial capture."""
    print("Testing Real Facial Capture Module...")
    print("=====================================")
    
    # Check if we have camera
    capture = FacialCapture(camera_index=0, simulation_mode=False)
    
    if capture.camera is None:
        print("[ERROR] Camera not available")
        return False
    
    # Get camera info
    info = capture.get_camera_info()
    print(f"\nCamera Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Test single capture
    print("\nTesting single capture...")
    input("Press Enter when ready...")
    
    result = capture.capture_face("test", min_quality=30)
    
    if result:
        print(f"[OK] Face captured successfully!")
        print(f"  Quality: {result['quality']:.1f}")
        print(f"  Image size: {result['width']}x{result['height']}")
        print(f"  Face position: {result['face_rect']}")
    else:
        print("[ERROR] Face capture failed")
    
    # Test multiple angles
    print("\nTesting multi-angle capture...")
    input("Press Enter when ready...")
    
    results = capture.capture_multiple_angles(['front', 'smile'])
    
    print(f"\nCaptured {len(results)} angles:")
    for r in results:
        print(f"  {r['angle']}: Quality {r['quality']:.1f}")
    
    capture.cleanup()
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_facial_capture()