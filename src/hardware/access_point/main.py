#!/usr/bin/env python3
"""
Access Point Main Application
Runs on Raspberry Pi at the access point
"""
import os
import sys
import time
import yaml
import logging
import signal
import argparse
from datetime import datetime
import cv2
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.hardware.access_point.camera_manager import CameraManager
from src.hardware.access_point.face_recognizer import FaceRecognizer
from src.hardware.access_point.lock_controller import LockController
from src.hardware.access_point.api_client import APIClient

class AccessPoint:
    """Main access point application"""
    
    def __init__(self, config_path='config.yaml'):
        self.config = self.load_config(config_path)
        self.setup_logging()
        
        # Initialize components
        self.camera = None
        self.recognizer = FaceRecognizer(
            confidence_threshold=self.config.get('recognition', {}).get('confidence_threshold', 0.6)
        )
        self.lock = LockController(
            gpio_pin=self.config.get('lock', {}).get('gpio_pin', 17),
            unlock_duration=self.config.get('lock', {}).get('unlock_duration', 5),
            active_high=self.config.get('lock', {}).get('relay_active_high', True)
        )
        self.api = APIClient(
            server_url=self.config['server']['url'],
            api_key=self.config['server']['api_key']
        )
        
        self.is_running = True
        self.last_sync = None
        self.sync_interval = self.config.get('server', {}).get('sync_interval', 300)
        self.recognition_interval = self.config.get('recognition', {}).get('recognition_interval', 0.5)
        
        # Statistics
        self.stats = {
            'recognitions': 0,
            'access_granted': 0,
            'access_denied': 0,
            'start_time': datetime.utcnow()
        }
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("Access Point initialized")
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        default_config = {
            'access_point': {
                'id': 'AP-001',
                'name': 'Main Gate',
                'location': 'University Main Entrance'
            },
            'server': {
                'url': 'http://localhost:5000/api/access-point',
                'api_key': 'your-api-key-here',
                'sync_interval': 300
            },
            'camera': {
                'device_id': 0,
                'resolution': [640, 480],
                'fps': 30
            },
            'recognition': {
                'confidence_threshold': 0.6,
                'recognition_interval': 0.5
            },
            'lock': {
                'gpio_pin': 17,
                'unlock_duration': 5,
                'relay_active_high': True
            },
            'logging': {
                'level': 'INFO',
                'file': '/var/log/access_point.log'
            }
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                # Merge with default config
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            # Create default config file
            try:
                with open(config_path, 'w') as f:
                    yaml.dump(default_config, f, default_flow_style=False)
                print(f"Created default config file: {config_path}")
            except Exception as e:
                print(f"Error creating config file: {e}")
            return default_config
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_file = log_config.get('file')
        
        handlers = [logging.StreamHandler()]
        if log_file:
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                handlers.append(logging.FileHandler(log_file))
            except Exception as e:
                print(f"Error creating log file: {e}")
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Shutdown signal received")
        self.is_running = False
    
    def sync_encodings(self):
        """Sync face encodings from server"""
        self.logger.info("Syncing face encodings...")
        students = self.api.sync_encodings()
        if students:
            self.recognizer.load_encodings(students)
            self.last_sync = datetime.utcnow()
            self.logger.info(f"Synced {len(students)} students")
        else:
            self.logger.warning("Failed to sync encodings")
    
    def process_frame(self, frame):
        """Process a single frame for face recognition"""
        if frame is None:
            return
        
        # Check if it's time to sync
        if self.last_sync is None or \
           (datetime.utcnow() - self.last_sync).seconds > self.sync_interval:
            self.sync_encodings()
        
        # Recognize faces
        results = self.recognizer.recognize(frame)
        self.stats['recognitions'] += 1
        
        if results:
            best = results[0]
            self.logger.info(f"Recognized: {best['name']} (confidence: {best['confidence']:.2f})")
            
            if best['confidence'] >= self.recognizer.confidence_threshold:
                # Access granted - unlock door
                self.logger.info(f"Access granted for {best['name']}")
                self.lock.unlock()
                self.stats['access_granted'] += 1
                
                # Display success on frame
                cv2.putText(frame, f"ACCESS GRANTED: {best['name']}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                self.stats['access_denied'] += 1
                cv2.putText(frame, f"ACCESS DENIED (confidence: {best['confidence']:.2f})", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        else:
            # No face recognized
            cv2.putText(frame, "No face recognized", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Display frame
        cv2.imshow('Access Point', frame)
        cv2.waitKey(1)
    
    def run(self):
        """Main application loop"""
        self.logger.info("Starting Access Point...")
        
        # Initialize camera
        camera_config = self.config.get('camera', {})
        self.camera = CameraManager(
            device_id=camera_config.get('device_id', 0),
            width=camera_config.get('resolution', [640, 480])[0],
            height=camera_config.get('resolution', [640, 480])[1],
            fps=camera_config.get('fps', 30)
        )
        
        if not self.camera.start():
            self.logger.error("Failed to start camera")
            return
        
        # Initial sync
        self.sync_encodings()
        
        self.logger.info("Access Point running. Press Ctrl+C to stop.")
        
        try:
            while self.is_running:
                # Capture frame
                frame = self.camera.capture()
                if frame is not None:
                    self.process_frame(frame)
                
                # Small delay to prevent CPU overload
                time.sleep(self.recognition_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up...")
        if self.camera:
            self.camera.cleanup()
        self.lock.cleanup()
        cv2.destroyAllWindows()
        self.logger.info("Access Point stopped")
        self.print_stats()
    
    def print_stats(self):
        """Print statistics"""
        runtime = (datetime.utcnow() - self.stats['start_time']).total_seconds()
        self.logger.info("=" * 50)
        self.logger.info("Access Point Statistics")
        self.logger.info("=" * 50)
        self.logger.info(f"Runtime: {runtime:.1f} seconds")
        self.logger.info(f"Recognitions: {self.stats['recognitions']}")
        self.logger.info(f"Access Granted: {self.stats['access_granted']}")
        self.logger.info(f"Access Denied: {self.stats['access_denied']}")
        self.logger.info(f"Enrolled Faces: {len(self.recognizer.known_face_encodings)}")
        self.logger.info("=" * 50)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Access Point for Face Recognition')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--test', action='store_true', help='Run in test mode (quick recognition test)')
    args = parser.parse_args()
    
    # Create access point instance
    ap = AccessPoint(args.config)
    
    if args.test:
        # Test mode - quick test
        ap.logger.info("Running in test mode")
        camera = CameraManager()
        if camera.start():
            for i in range(10):
                frame = camera.capture()
                if frame is not None:
                    results = ap.recognizer.recognize(frame)
                    if results:
                        print(f"Found: {results[0]['name']} ({results[0]['confidence']:.2f})")
                    else:
                        print("No face recognized")
                time.sleep(0.5)
            camera.cleanup()
        else:
            ap.logger.error("Camera test failed")
    else:
        # Normal operation
        ap.run()

if __name__ == "__main__":
    main()