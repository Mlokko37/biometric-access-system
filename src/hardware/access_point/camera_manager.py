"""
Camera Manager - Handles camera operations for the access point
"""
import cv2
import time
import logging
import numpy as np
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

class CameraManager:
    """Manages camera operations for face recognition"""
    
    def __init__(self, device_id=0, width=640, height=480, fps=30):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.camera = None
        self.is_running = False
        self.last_frame = None
        self.frame_count = 0
    
    def start(self):
        """Start the camera"""
        try:
            self.camera = cv2.VideoCapture(self.device_id)
            if not self.camera.isOpened():
                logger.error(f"Failed to open camera {self.device_id}")
                return False
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            self.is_running = True
            logger.info(f"Camera started: {self.width}x{self.height} @ {self.fps}fps")
            return True
            
        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            return False
    
    def capture(self) -> Optional[np.ndarray]:
        """Capture a single frame from the camera"""
        if not self.is_running or self.camera is None:
            return None
        
        try:
            ret, frame = self.camera.read()
            if ret:
                self.last_frame = frame
                self.frame_count += 1
                return frame
            else:
                logger.warning("Failed to capture frame")
                return None
                
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
    
    def capture_continuous(self, callback, max_frames=None):
        """Capture frames continuously and process with callback"""
        if not self.start():
            return
        
        frame_count = 0
        try:
            while self.is_running:
                frame = self.capture()
                if frame is not None:
                    callback(frame)
                    frame_count += 1
                    
                    if max_frames and frame_count >= max_frames:
                        break
                        
        except KeyboardInterrupt:
            logger.info("Stopping continuous capture")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the camera"""
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        logger.info("Camera stopped")
    
    def capture_image(self, filename: str) -> bool:
        """Capture a single frame and save to file"""
        frame = self.capture()
        if frame is not None:
            try:
                cv2.imwrite(filename, frame)
                logger.info(f"Image saved: {filename}")
                return True
            except Exception as e:
                logger.error(f"Error saving image: {e}")
        return False
    
    def get_resolution(self) -> Tuple[int, int]:
        """Get current camera resolution"""
        if self.camera:
            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (width, height)
        return (0, 0)
    
    def display_frame(self, frame, text=None, wait_key=True):
        """Display a frame with optional text overlay"""
        if frame is None:
            return
        
        display_frame = frame.copy()
        
        if text:
            cv2.putText(display_frame, text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow('Access Point Camera', display_frame)
        
        if wait_key:
            return cv2.waitKey(1) & 0xFF
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        cv2.destroyAllWindows()

class CameraError(Exception):
    """Camera related errors"""
    pass