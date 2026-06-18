"""
Main hardware manager for biometric access control system
Manages fingerprint scanners, facial recognition cameras, and access controllers
"""
import logging
import threading
import time
import enum  # Add this import
from typing import Dict, List, Optional
from datetime import datetime

# Import hardware interfaces
from hardware.interfaces.fingerprint_scanner import FingerprintScanner
from hardware.interfaces.facial_recognition import FacialRecognition
from hardware.interfaces.camera_controller import CameraController
from hardware.interfaces.access_controller import AccessController
from hardware.utils.device_discovery import discover_devices
from hardware.utils.diagnostics import HardwareDiagnostics
from hardware.config import HardwareConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the missing HardwareStatus enum
class HardwareStatus(enum.Enum):
    """Hardware device status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    BUSY = "busy"
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"


class HardwareManager:
    """Main hardware management class"""
    
    def __init__(self, config_file: str = "hardware/configs/devices.yaml"):
        self.config = HardwareConfig(config_file)
        self.devices = {}
        self.is_running = False
        self.event_callbacks = {}
        self.threads = {}
        self.lock = threading.Lock()
        
        # Initialize hardware components
        self.fingerprint_scanners = {}
        self.facial_cameras = {}
        self.access_controllers = {}
        
        logger.info("Hardware Manager initialized")
    
    def initialize_hardware(self) -> bool:
        """Initialize all hardware devices"""
        try:
            logger.info("Starting hardware initialization...")
            
            # Discover connected devices
            discovered_devices = discover_devices()
            
            # Initialize fingerprint scanners
            for scanner_config in self.config.fingerprint_scanners:
                try:
                    scanner = FingerprintScanner(scanner_config)
                    if scanner.initialize():
                        self.fingerprint_scanners[scanner.device_id] = scanner
                        logger.info(f"Fingerprint scanner {scanner.device_id} initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize fingerprint scanner {scanner_config['device_id']}: {e}")
            
            # Initialize facial recognition cameras
            for camera_config in self.config.facial_cameras:
                try:
                    camera = FacialRecognition(camera_config)
                    if camera.initialize():
                        self.facial_cameras[camera.device_id] = camera
                        logger.info(f"Facial recognition camera {camera.device_id} initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize facial camera {camera_config['device_id']}: {e}")
            
            # Initialize access controllers (door locks, etc.)
            for controller_config in self.config.access_controllers:
                try:
                    controller = AccessController(controller_config)
                    if controller.initialize():
                        self.access_controllers[controller.device_id] = controller
                        logger.info(f"Access controller {controller.device_id} initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize access controller {controller_config['device_id']}: {e}")
            
            self.is_running = True
            logger.info(f"Hardware initialization complete. Devices: {len(self.fingerprint_scanners)} scanners, "
                       f"{len(self.facial_cameras)} cameras, {len(self.access_controllers)} controllers")
            return True
            
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            return False
    
    def start_monitoring(self):
        """Start monitoring all hardware devices"""
        if not self.is_running:
            logger.error("Hardware not initialized")
            return
        
        # Start fingerprint scanner monitoring
        for scanner_id, scanner in self.fingerprint_scanners.items():
            thread = threading.Thread(
                target=self._monitor_fingerprint_scanner,
                args=(scanner,),
                name=f"scanner-{scanner_id}"
            )
            thread.daemon = True
            thread.start()
            self.threads[f"scanner_{scanner_id}"] = thread
        
        # Start facial recognition monitoring
        for camera_id, camera in self.facial_cameras.items():
            thread = threading.Thread(
                target=self._monitor_facial_camera,
                args=(camera,),
                name=f"camera-{camera_id}"
            )
            thread.daemon = True
            thread.start()
            self.threads[f"camera_{camera_id}"] = thread
        
        logger.info("Hardware monitoring started")
    
    def _monitor_fingerprint_scanner(self, scanner):
        """Monitor fingerprint scanner for new scans"""
        while self.is_running:
            try:
                scan_result = scanner.scan_fingerprint(timeout=1)
                if scan_result:
                    user_id, confidence = scan_result
                    logger.info(f"Fingerprint scan detected: User {user_id} (confidence: {confidence})")
                    
                    # Trigger callback if registered
                    if 'fingerprint_scan' in self.event_callbacks:
                        self.event_callbacks['fingerprint_scan']({
                            'user_id': user_id,
                            'confidence': confidence,
                            'scanner_id': scanner.device_id,
                            'timestamp': datetime.now().isoformat(),
                            'type': 'fingerprint'
                        })
                    
                    # Grant access if confidence is high
                    if confidence > self.config.fingerprint_threshold:
                        self.grant_access(user_id, 'fingerprint')
            except Exception as e:
                logger.error(f"Error monitoring fingerprint scanner {scanner.device_id}: {e}")
                time.sleep(2)
    
    def _monitor_facial_camera(self, camera):
        """Monitor facial recognition camera"""
        while self.is_running:
            try:
                recognition_result = camera.recognize_face()
                if recognition_result:
                    user_id, confidence = recognition_result
                    logger.info(f"Face recognized: User {user_id} (confidence: {confidence})")
                    
                    # Trigger callback if registered
                    if 'face_recognition' in self.event_callbacks:
                        self.event_callbacks['face_recognition']({
                            'user_id': user_id,
                            'confidence': confidence,
                            'camera_id': camera.device_id,
                            'timestamp': datetime.now().isoformat(),
                            'type': 'facial'
                        })
                    
                    # Grant access if confidence is high
                    if confidence > self.config.facial_threshold:
                        self.grant_access(user_id, 'facial')
            except Exception as e:
                logger.error(f"Error monitoring facial camera {camera.device_id}: {e}")
                time.sleep(1)
    
    def grant_access(self, user_id: str, auth_type: str):
        """Grant physical access (open door, etc.)"""
        with self.lock:
            try:
                logger.info(f"Granting access to user {user_id} via {auth_type}")
                
                # Trigger all access controllers
                for controller_id, controller in self.access_controllers.items():
                    success = controller.grant_access(user_id)
                    if success:
                        logger.info(f"Access granted via controller {controller_id}")
                    else:
                        logger.warning(f"Failed to grant access via controller {controller_id}")
                
                # Trigger callback if registered
                if 'access_granted' in self.event_callbacks:
                    self.event_callbacks['access_granted']({
                        'user_id': user_id,
                        'auth_type': auth_type,
                        'timestamp': datetime.now().isoformat()
                    })
                
                return True
            except Exception as e:
                logger.error(f"Error granting access: {e}")
                return False
    
    def enroll_fingerprint(self, user_id: str, scanner_id: Optional[str] = None) -> Dict:
        """Enroll new fingerprint for a user"""
        try:
            scanner = self._get_scanner(scanner_id)
            if not scanner:
                return {"success": False, "error": "No scanner available"}
            
            logger.info(f"Starting fingerprint enrollment for user {user_id}")
            
            # Step 1: Capture fingerprint template
            template_data = scanner.capture_template()
            if not template_data:
                return {"success": False, "error": "Failed to capture fingerprint"}
            
            # Step 2: Store template in database
            # This would typically save to your database
            enrollment_data = {
                "user_id": user_id,
                "template": template_data,
                "scanner_id": scanner.device_id,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Fingerprint enrolled successfully for user {user_id}")
            return {
                "success": True,
                "message": "Fingerprint enrolled successfully",
                "data": enrollment_data
            }
            
        except Exception as e:
            logger.error(f"Fingerprint enrollment failed: {e}")
            return {"success": False, "error": str(e)}
    
    def enroll_face(self, user_id: str, camera_id: Optional[str] = None) -> Dict:
        """Enroll new face for a user"""
        try:
            camera = self._get_camera(camera_id)
            if not camera:
                return {"success": False, "error": "No camera available"}
            
            logger.info(f"Starting facial enrollment for user {user_id}")
            
            # Capture face images from multiple angles
            face_embeddings = camera.capture_face_embeddings()
            if not face_embeddings:
                return {"success": False, "error": "Failed to capture face"}
            
            # Store embeddings in database
            enrollment_data = {
                "user_id": user_id,
                "embeddings": face_embeddings,
                "camera_id": camera.device_id,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Face enrolled successfully for user {user_id}")
            return {
                "success": True,
                "message": "Face enrolled successfully",
                "data": enrollment_data
            }
            
        except Exception as e:
            logger.error(f"Facial enrollment failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_device_status(self) -> Dict:
        """Get status of all hardware devices"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "is_running": self.is_running,
            "fingerprint_scanners": {},
            "facial_cameras": {},
            "access_controllers": {},
            "overall_status": "operational"
        }
        
        # Check fingerprint scanners
        for scanner_id, scanner in self.fingerprint_scanners.items():
            status["fingerprint_scanners"][scanner_id] = {
                "connected": scanner.is_connected(),
                "last_scan": scanner.last_scan_time,
                "total_scans": scanner.scan_count,
                "status": "online" if scanner.is_connected() else "offline"
            }
        
        # Check facial cameras
        for camera_id, camera in self.facial_cameras.items():
            status["facial_cameras"][camera_id] = {
                "connected": camera.is_connected(),
                "last_recognition": camera.last_recognition_time,
                "recognitions_today": camera.recognition_count,
                "status": "online" if camera.is_connected() else "offline"
            }
        
        # Check access controllers
        for controller_id, controller in self.access_controllers.items():
            status["access_controllers"][controller_id] = {
                "connected": controller.is_connected(),
                "last_access": controller.last_access_time,
                "access_granted_today": controller.access_count,
                "status": "online" if controller.is_connected() else "offline"
            }
        
        return status
    
    def run_diagnostics(self) -> Dict:
        """Run comprehensive hardware diagnostics"""
        diagnostics = HardwareDiagnostics(self)
        return diagnostics.run_all_tests()
    
    def shutdown(self):
        """Safely shutdown all hardware"""
        self.is_running = False
        
        # Stop all threads
        for thread_name, thread in self.threads.items():
            if thread.is_alive():
                thread.join(timeout=2)
        
        # Disconnect all devices
        for scanner in self.fingerprint_scanners.values():
            scanner.disconnect()
        
        for camera in self.facial_cameras.values():
            camera.disconnect()
        
        for controller in self.access_controllers.values():
            controller.disconnect()
        
        logger.info("Hardware manager shutdown complete")
    
    def register_callback(self, event_name: str, callback_func):
        """Register callback for hardware events"""
        self.event_callbacks[event_name] = callback_func
        logger.info(f"Callback registered for event: {event_name}")
    
    def _get_scanner(self, scanner_id: Optional[str] = None):
        """Get scanner by ID or first available"""
        if scanner_id:
            return self.fingerprint_scanners.get(scanner_id)
        elif self.fingerprint_scanners:
            return next(iter(self.fingerprint_scanners.values()))
        return None
    
    def _get_camera(self, camera_id: Optional[str] = None):
        """Get camera by ID or first available"""
        if camera_id:
            return self.facial_cameras.get(camera_id)
        elif self.facial_cameras:
            return next(iter(self.facial_cameras.values()))
        return None


# Singleton instance
hardware_manager = HardwareManager()