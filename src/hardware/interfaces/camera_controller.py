"""
Camera controller interface
"""

import cv2
import time
import logging
from typing import Optional, Tuple, Dict, Any
from .biometric_interface import BaseBiometricDevice

logger = logging.getLogger(__name__)


class CameraController(BaseBiometricDevice):
    """Camera controller for basic camera operations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get("device_id", "camera_1")
        self.camera_index = config.get("camera_index", 0)
        self.camera_url = config.get("camera_url")
        self.resolution = config.get("resolution", (640, 480))
        self.fps = config.get("fps", 30)
        
        self.capture = None
        self.is_initialized = False
        self.frame_count = 0
        
        logger.info(f"Initializing camera {self.device_id}")
    
    def initialize(self) -> bool:
        """Initialize camera"""
        try:
            if self.camera_url:
                self.capture = cv2.VideoCapture(self.camera_url)
            else:
                self.capture = cv2.VideoCapture(self.camera_index)
            
            if not self.capture.isOpened():
                logger.error(f"Failed to open camera {self.device_id}")
                return False
            
            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.capture.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Test camera
            ret, frame = self.capture.read()
            if not ret:
                logger.error(f"Failed to capture frame from camera {self.device_id}")
                return False
            
            self.is_initialized = True
            logger.info(f"Camera {self.device_id} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False
    
    def capture_frame(self) -> Optional[bytes]:
        """Capture a single frame"""
        if not self.is_connected():
            return None
        
        try:
            ret, frame = self.capture.read()
            if ret:
                self.frame_count += 1
                
                # Convert to JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    return buffer.tobytes()
            
            return None
            
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
    
    def capture_multiple_frames(self, count: int = 5, delay: float = 0.5) -> list:
        """Capture multiple frames"""
        frames = []
        
        for i in range(count):
            frame_data = self.capture_frame()
            if frame_data:
                frames.append(frame_data)
            
            time.sleep(delay)
        
        return frames
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Get camera information"""
        info = {
            "device_id": self.device_id,
            "connected": self.is_connected(),
            "frame_count": self.frame_count,
            "resolution": self.resolution,
            "fps": self.fps
        }
        
        if self.capture and self.is_connected():
            info.update({
                "width": self.capture.get(cv2.CAP_PROP_FRAME_WIDTH),
                "height": self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
                "actual_fps": self.capture.get(cv2.CAP_PROP_FPS)
            })
        
        return info
    
    def is_connected(self) -> bool:
        """Check if camera is connected"""
        return self.is_initialized and self.capture and self.capture.isOpened()
    
    def disconnect(self):
        """Disconnect camera"""
        try:
            if self.capture:
                self.capture.release()
            
            self.is_initialized = False
            logger.info(f"Camera {self.device_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting camera: {e}")
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information"""
        return self.get_camera_info()
    
    def test_device(self) -> Tuple[bool, str]:
        """Test camera functionality"""
        try:
            if not self.is_connected():
                return False, "Camera not connected"
            
            # Capture test frame
            frame = self.capture_frame()
            if not frame:
                return False, "Failed to capture frame"
            
            # Check frame size
            if len(frame) < 1000:  # Arbitrary minimum size
                return False, "Frame size too small"
            
            return True, "Camera test passed"
            
        except Exception as e:
            return False, f"Camera test failed: {e}"