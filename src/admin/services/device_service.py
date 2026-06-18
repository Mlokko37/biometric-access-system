import sys
import os
import logging
import socket
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

# Ensure we can import from root drivers folder
current_dir = os.path.dirname(__file__)
root_dir = os.path.join(current_dir, '..', '..')
sys.path.insert(0, root_dir)

logger = logging.getLogger(__name__)

class DeviceService:
    """Service for managing real hardware devices."""
    
    def __init__(self):
        self.devices = {}
        self.load_devices_from_db()
    
    def load_devices_from_db(self):
        """Load devices from database."""
        try:
            from src.database.connection import execute_query
            
            result = execute_query("""
                SELECT device_id, device_name, device_type, ip_address, port, 
                       username, password, location, status
                FROM devices WHERE is_active = TRUE
            """)
            
            if result:
                for row in result:
                    self.devices[row[0]] = {
                        'device_id': row[0],
                        'device_name': row[1],
                        'device_type': row[2],
                        'ip_address': row[3],
                        'port': row[4],
                        'username': row[5],
                        'password': row[6],
                        'location': row[7],
                        'status': row[8],
                        'connected': False,
                        'last_seen': None
                    }
            
            logger.info(f"Loaded {len(self.devices)} devices from database")
            
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
    
    def initialize_device(self, device_id: str) -> bool:
        """Initialize and connect to a physical device."""
        try:
            device = self.devices.get(device_id)
            if not device:
                logger.error(f"Device {device_id} not found")
                return False
            
            # Different initialization based on device type
            if device['device_type'] == 'fingerprint_scanner':
                return self._init_fingerprint_scanner(device)
            elif device['device_type'] == 'facial_camera':
                return self._init_facial_camera(device)
            elif device['device_type'] == 'access_controller':
                return self._init_access_controller(device)
            elif device['device_type'] == 'zkteco':
                return self._init_zkteco_device(device)
            else:
                # Generic TCP/IP device
                return self._init_generic_device(device)
                
        except Exception as e:
            logger.error(f"Error initializing device {device_id}: {e}")
            return False
    
    def _init_fingerprint_scanner(self, device: Dict) -> bool:
        """Initialize fingerprint scanner."""
        try:
            from src.hardware.drivers.fingerprint_scanner import FingerprintScanner
            
            scanner = FingerprintScanner(
                port=device.get('port', '/dev/ttyUSB0'),
                baudrate=57600
            )
            
            if scanner.connect():
                device['connected'] = True
                device['instance'] = scanner
                device['last_seen'] = datetime.now()
                logger.info(f"Fingerprint scanner {device['device_name']} connected")
                return True
            
        except ImportError:
            logger.warning("Fingerprint scanner driver not available")
        except Exception as e:
            logger.error(f"Fingerprint scanner init error: {e}")
        
        return False
    
    def _init_facial_camera(self, device: Dict) -> bool:
        """Initialize facial recognition camera."""
        try:
            import cv2
            
            camera = cv2.VideoCapture(int(device.get('camera_index', 0)))
            
            if camera.isOpened():
                device['connected'] = True
                device['instance'] = camera
                device['last_seen'] = datetime.now()
                logger.info(f"Facial camera {device['device_name']} connected")
                return True
            
        except ImportError:
            logger.warning("OpenCV not available")
        except Exception as e:
            logger.error(f"Facial camera init error: {e}")
        
        return False
    
    def _init_access_controller(self, device: Dict) -> bool:
        """Initialize access controller (Arduino/Relay)."""
        try:
            import serial
            
            controller = serial.Serial(
                port=device.get('port', 'COM3'),
                baudrate=9600,
                timeout=1
            )
            
            if controller.is_open:
                device['connected'] = True
                device['instance'] = controller
                device['last_seen'] = datetime.now()
                logger.info(f"Access controller {device['device_name']} connected")
                return True
            
        except ImportError:
            logger.warning("PySerial not available")
        except Exception as e:
            logger.error(f"Access controller init error: {e}")
        
        return False
    
    def _init_zkteco_device(self, device: Dict) -> bool:
        """Initialize ZKTeco biometric device."""
        try:
            # Try to import pyzk, provide fallback if not available
            try:
                from zk import ZK
                ZK_AVAILABLE = True
            except ImportError:
                ZK_AVAILABLE = False
                logger.warning("pyzk not available - ZKTeco devices will use generic connection")
            
            if ZK_AVAILABLE:
                zk = ZK(
                    device.get('ip_address'),
                    port=device.get('port', 4370),
                    timeout=30
                )
                
                conn = zk.connect()
                if conn:
                    device['connected'] = True
                    device['instance'] = conn
                    device['last_seen'] = datetime.now()
                    logger.info(f"ZKTeco device {device['device_name']} connected")
                    return True
            else:
                # Fallback: just test TCP connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((device.get('ip_address'), device.get('port', 4370)))
                sock.close()
                
                if result == 0:
                    device['connected'] = True
                    device['last_seen'] = datetime.now()
                    logger.info(f"ZKTeco device {device['device_name']} reachable (generic mode)")
                    return True
                
        except Exception as e:
            logger.error(f"ZKTeco device init error: {e}")
        
        return False
    
    def _init_generic_device(self, device: Dict) -> bool:
        """Initialize generic TCP/IP device."""
        try:
            # Try to ping the device
            response = os.system(f"ping -c 1 {device.get('ip_address')}")
            
            if response == 0:
                device['connected'] = True
                device['last_seen'] = datetime.now()
                logger.info(f"Generic device {device['device_name']} reachable")
                return True
            
        except Exception as e:
            logger.error(f"Generic device init error: {e}")
        
        return False
    
    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get real status from physical device."""
        device = self.devices.get(device_id)
        if not device:
            return {'status': 'unknown', 'error': 'Device not found'}
        
        try:
            # Check if device is still connected
            if not device.get('connected', False):
                # Try to reconnect
                self.initialize_device(device_id)
            
            # Get device-specific status
            if device['device_type'] == 'fingerprint_scanner':
                return self._get_fingerprint_scanner_status(device)
            elif device['device_type'] == 'facial_camera':
                return self._get_facial_camera_status(device)
            elif device['device_type'] == 'access_controller':
                return self._get_access_controller_status(device)
            elif device['device_type'] == 'zkteco':
                return self._get_zkteco_status(device)
            else:
                # Generic status check
                return self._get_generic_status(device)
                
        except Exception as e:
            logger.error(f"Error getting device status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _get_fingerprint_scanner_status(self, device: Dict) -> Dict:
        """Get fingerprint scanner status."""
        try:
            if device.get('connected') and device.get('instance'):
                # Check if scanner is still responsive
                scanner = device['instance']
                if hasattr(scanner, 'verifyPassword'):
                    if scanner.verifyPassword():
                        return {
                            'status': 'online',
                            'device_type': 'fingerprint_scanner',
                            'last_seen': device['last_seen'].isoformat() if device['last_seen'] else None
                        }
            
            return {'status': 'offline', 'error': 'Scanner not responding'}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _get_facial_camera_status(self, device: Dict) -> Dict:
        """Get facial camera status."""
        try:
            if device.get('connected') and device.get('instance'):
                camera = device['instance']
                ret, frame = camera.read()
                if ret:
                    return {
                        'status': 'online',
                        'device_type': 'facial_camera',
                        'last_seen': device['last_seen'].isoformat() if device['last_seen'] else None
                    }
            
            return {'status': 'offline', 'error': 'Camera not responding'}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _get_access_controller_status(self, device: Dict) -> Dict:
        """Get access controller status."""
        try:
            if device.get('connected') and device.get('instance'):
                controller = device['instance']
                if controller.is_open:
                    return {
                        'status': 'online',
                        'device_type': 'access_controller',
                        'last_seen': device['last_seen'].isoformat() if device['last_seen'] else None
                    }
            
            return {'status': 'offline', 'error': 'Controller not responding'}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _get_zkteco_status(self, device: Dict) -> Dict:
        """Get ZKTeco device status."""
        try:
            if device.get('connected') and device.get('instance'):
                conn = device['instance']
                if conn.test_connection():
                    return {
                        'status': 'online',
                        'device_type': 'zkteco',
                        'firmware': conn.get_firmware_version(),
                        'users': len(conn.get_users()),
                        'attendance_count': conn.get_attendance().count(),
                        'last_seen': device['last_seen'].isoformat() if device['last_seen'] else None
                    }
            
            return {'status': 'offline', 'error': 'Device not responding'}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _get_generic_status(self, device: Dict) -> Dict:
        """Get generic device status via HTTP API."""
        try:
            if device.get('ip_address'):
                url = f"http://{device['ip_address']}:{device.get('port', 80)}/status"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    device['last_seen'] = datetime.now()
                    return {
                        'status': 'online',
                        'device_type': device['device_type'],
                        'data': data,
                        'last_seen': device['last_seen'].isoformat()
                    }
            
            return {'status': 'offline', 'error': 'Device not reachable'}
            
        except requests.RequestException as e:
            return {'status': 'offline', 'error': str(e)}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def send_command(self, device_id: str, command: str, params: Optional[Dict] = None) -> Dict:
        """Send command to physical device."""
        device = self.devices.get(device_id)
        if not device:
            return {'success': False, 'error': 'Device not found'}
        
        try:
            if device['device_type'] == 'access_controller':
                return self._send_controller_command(device, command, params)
            elif device['device_type'] == 'zkteco':
                return self._send_zkteco_command(device, command, params)
            elif device.get('ip_address'):
                return self._send_http_command(device, command, params)
            else:
                return {'success': False, 'error': 'Device does not support commands'}
                
        except Exception as e:
            logger.error(f"Command error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_controller_command(self, device: Dict, command: str, params: Optional[Dict] = None) -> Dict:
        """Send command to access controller."""
        try:
            if not device.get('connected') or not device.get('instance'):
                return {'success': False, 'error': 'Device not connected'}
            
            controller = device['instance']
            
            if command == 'grant_access':
                controller.write(b'GRANT\n')
                return {'success': True, 'message': 'Access granted'}
            elif command == 'deny_access':
                controller.write(b'DENY\n')
                return {'success': True, 'message': 'Access denied'}
            elif command == 'get_status':
                controller.write(b'STATUS\n')
                response = controller.readline().decode().strip()
                return {'success': True, 'status': response}
            else:
                return {'success': False, 'error': f'Unknown command: {command}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _send_zkteco_command(self, device: Dict, command: str, params: Optional[Dict] = None) -> Dict:
        """Send command to ZKTeco device."""
        try:
            if not device.get('connected') or not device.get('instance'):
                return {'success': False, 'error': 'Device not connected'}
            
            conn = device['instance']
            params = params or {}  # Convert None to empty dict
            
            if command == 'get_users':
                users = conn.get_users()
                return {'success': True, 'users': [{'uid': u.uid, 'name': u.name} for u in users]}
            elif command == 'get_attendance':
                attendance = conn.get_attendance()
                return {'success': True, 'attendance': len(attendance)}
            elif command == 'set_user':
                uid = params.get('uid')
                name = params.get('name')
                privilege = params.get('privilege', 0)
                password = params.get('password', '')
                user_id = params.get('user_id', '')
                
                conn.set_user(uid, user_id, name, privilege, password)
                return {'success': True, 'message': f'User {name} added'}
            else:
                return {'success': False, 'error': f'Unknown command: {command}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _send_http_command(self, device: Dict, command: str, params: Optional[Dict] = None) -> Dict:
        """Send HTTP command to device API."""
        try:
            url = f"http://{device['ip_address']}:{device.get('port', 80)}/{command}"
            response = requests.post(url, json=params or {}, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def capture_fingerprint(self, device_id: str) -> Dict:
        """Capture fingerprint from device."""
        return self.send_command(device_id, 'capture_fingerprint')
    
    def verify_fingerprint(self, device_id: str, template: str) -> Dict:
        """Verify fingerprint against template."""
        return self.send_command(device_id, 'verify_fingerprint', {'template': template})
    
    def unlock_door(self, device_id: str, duration: int = 5) -> Dict:
        """Unlock door for specified duration."""
        return self.send_command(device_id, 'unlock_door', {'duration': duration})
    
    def sync_users_to_device(self, device_id: str) -> bool:
        """Sync users from database to device."""
        try:
            from src.database.connection import execute_query
            
            # Get all active students
            users = execute_query("""
                SELECT student_id, registration_number, first_name, last_name
                FROM students WHERE is_active = TRUE
            """)
            
            if not users:
                logger.warning("No users to sync")
                return False
            
            device = self.devices.get(device_id)
            if not device or not device.get('connected'):
                logger.error(f"Device {device_id} not connected")
                return False
            
            # Sync based on device type
            if device['device_type'] == 'zkteco':
                conn = device['instance']
                
                # Clear existing users
                existing_users = conn.get_users()
                for user in existing_users:
                    conn.delete_user(user.uid)
                
                # Add new users
                for user in users:
                    student_id, reg_no, first_name, last_name = user
                    name = f"{first_name} {last_name}"[:20]  # Truncate if needed
                    conn.set_user(
                        uid=int(student_id) if student_id.isdigit() else hash(student_id) % 10000,
                        user_id=reg_no[:8],  # First 8 chars of registration
                        name=name,
                        privilege=0,
                        password=''
                    )
                
                logger.info(f"Synced {len(users)} users to device {device_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False
    
    def get_all_devices_status(self) -> Dict[str, Any]:
        """Get status of all devices."""
        status = {
            'total': len(self.devices),
            'online': 0,
            'offline': 0,
            'devices': {}
        }
        
        for device_id, device in self.devices.items():
            device_status = self.get_device_status(device_id)
            status['devices'][device_id] = device_status
            
            if device_status.get('status') == 'online':
                status['online'] += 1
            else:
                status['offline'] += 1
        
        return status
    
    def cleanup(self):
        """Clean up device connections."""
        for device_id, device in self.devices.items():
            try:
                if device.get('connected') and device.get('instance'):
                    if device['device_type'] == 'facial_camera':
                        device['instance'].release()
                    elif device['device_type'] == 'access_controller':
                        device['instance'].close()
                    elif device['device_type'] == 'zkteco':
                        device['instance'].disconnect()
                    
                    device['connected'] = False
                    logger.info(f"Cleaned up device {device_id}")
                    
            except Exception as e:
                logger.error(f"Cleanup error for device {device_id}: {e}")

# Singleton instance
device_service = DeviceService()