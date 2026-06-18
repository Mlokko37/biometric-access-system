"""
Device Service
Manages all hardware devices including manufacturer-specific ones
"""

import logging
from typing import Dict, Any, Optional, List, Union, Type

# Generic drivers
from .drivers.fingerprint_scanner import FingerprintScanner
from .drivers.facial_camera import FacialCamera
from .drivers.access_controller import AccessController

# Manufacturer-specific drivers - define as Any to avoid type conflicts
ZKTecoDevice: Any = None
SupremaDevice: Any = None
HikvisionDevice: Any = None
MANUFACTURER_DRIVERS_AVAILABLE = False

try:
    from .drivers.zkteco.zkteco_driver import ZKTecoDevice as _ZKTecoDevice
    from .drivers.suprema.suprema_driver import SupremaDevice as _SupremaDevice
    from .drivers.hikvision.hikvision_driver import HikvisionDevice as _HikvisionDevice
    
    ZKTecoDevice = _ZKTecoDevice
    SupremaDevice = _SupremaDevice
    HikvisionDevice = _HikvisionDevice
    MANUFACTURER_DRIVERS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Manufacturer-specific drivers loaded successfully")
except ImportError as e:
    # Create placeholder classes that raise informative errors
    class ZKTecoDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("ZKTeco driver not available. Please install required dependencies.")
    
    class SupremaDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("Suprema driver not available. Please install required dependencies.")
    
    class HikvisionDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("Hikvision driver not available. Please install required dependencies.")
    
    ZKTecoDevice = ZKTecoDevicePlaceholder
    SupremaDevice = SupremaDevicePlaceholder
    HikvisionDevice = HikvisionDevicePlaceholder
    logger = logging.getLogger(__name__)
    logger.warning(f"Manufacturer-specific drivers not available: {e}")

logger = logging.getLogger(__name__)

class DeviceService:
    """Service for managing hardware devices."""
    
    def __init__(self):
        self.devices: Dict[str, Any] = {}
        self.hardware_manager = None
    
    def initialize_device(self, name: str, device_type: str, ip: Optional[str] = None, 
                         port: Optional[Union[str, int]] = None, username: str = 'admin', 
                         password: str = 'admin123') -> Optional[Any]:
        """
        Initialize a hardware device.
        
        Args:
            name: Device name
            device_type: Type of device (fingerprint, camera, access_controller, 
                        zkteco, suprema, hikvision)
            ip: IP address for network devices
            port: Port number (string for serial, int for network)
            username: Username for authentication
            password: Password for authentication
            
        Returns:
            Device instance or None
        """
        try:
            device = None
            
            # Generic devices
            if device_type == 'fingerprint':
                # Fingerprint scanner uses string port (e.g., '/dev/ttyUSB0' or 'COM3')
                if port is None:
                    port = '/dev/ttyUSB0'
                device = FingerprintScanner(port=str(port))
            
            elif device_type == 'camera':
                # Camera uses integer index
                camera_index = 0
                if port is not None:
                    try:
                        camera_index = int(port)
                    except (ValueError, TypeError):
                        camera_index = 0
                device = FacialCamera(camera_index=camera_index)
            
            elif device_type == 'access_controller':
                # Access controller uses string port
                if port is None:
                    port = '/dev/ttyUSB1'
                device = AccessController(port=str(port))
            
            # Manufacturer-specific devices
            elif device_type == 'zkteco':
                # ZKTeco uses IP and integer port
                if ip is None:
                    logger.error("IP address required for ZKTeco device")
                    return None
                # Check if driver is available
                if ZKTecoDevice is None:
                    logger.error("ZKTeco driver not available")
                    return None
                device = ZKTecoDevice(
                    ip=ip, 
                    port=int(port) if port is not None else 4370
                )
            
            elif device_type == 'suprema':
                # Suprema uses IP and integer port
                if ip is None:
                    logger.error("IP address required for Suprema device")
                    return None
                # Check if driver is available
                if SupremaDevice is None:
                    logger.error("Suprema driver not available")
                    return None
                device = SupremaDevice(
                    ip=ip, 
                    port=int(port) if port is not None else 443
                )
            
            elif device_type == 'hikvision':
                # Hikvision uses IP, integer port, username, password
                if ip is None:
                    logger.error("IP address required for Hikvision device")
                    return None
                # Check if driver is available
                if HikvisionDevice is None:
                    logger.error("Hikvision driver not available")
                    return None
                device = HikvisionDevice(
                    ip=ip, 
                    port=int(port) if port is not None else 80,
                    username=username,
                    password=password
                )
            
            else:
                logger.error(f"Unknown device type: {device_type}")
                return None
            
            # Connect to device
            if device and hasattr(device, 'connect'):
                if device.connect():
                    self.devices[name] = device
                    logger.info(f"[OK] Device '{name}' ({device_type}) initialized successfully")
                    return device
                else:
                    logger.error(f"[ERROR] Failed to connect to device '{name}'")
                    return None
            else:
                logger.error(f"Device '{name}' has no connect method")
                return None
                
        except ImportError as e:
            logger.error(f"Driver import error for {device_type}: {e}")
            return None
        except Exception as e:
            logger.error(f"Device initialization error: {e}")
            return None
    
    def get_device(self, name: str) -> Optional[Any]:
        """Get device by name."""
        return self.devices.get(name)
    
    def get_all_devices(self) -> Dict[str, Any]:
        """Get all initialized devices."""
        return self.devices
    
    def remove_device(self, name: str) -> bool:
        """Remove and disconnect device."""
        if name in self.devices:
            try:
                if hasattr(self.devices[name], 'disconnect'):
                    self.devices[name].disconnect()
                del self.devices[name]
                logger.info(f"Device '{name}' removed")
                return True
            except Exception as e:
                logger.error(f"Error removing device '{name}': {e}")
        return False
    
    def sync_users_to_device(self, device_name: str, users: List[Dict]) -> tuple:
        """
        Sync users to device.
        
        Args:
            device_name: Name of device
            users: List of user dictionaries
            
        Returns:
            Tuple of (success, message)
        """
        device = self.get_device(device_name)
        
        if not device:
            return False, f"Device '{device_name}' not found"
        
        try:
            # Try different method names for clearing users
            if hasattr(device, 'delete_all_users'):
                device.delete_all_users()
            elif hasattr(device, 'clear_all_users'):
                device.clear_all_users()
            elif hasattr(device, 'clear_users'):
                device.clear_users()
            
            # Add each user
            success_count = 0
            for user in users:
                user_id = user.get('student_id') or user.get('id') or user.get('user_id')
                if not user_id:
                    continue
                    
                name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                if not name:
                    name = f"User_{user_id}"
                
                # Try different method names for adding users
                added = False
                if hasattr(device, 'add_user'):
                    added = device.add_user(str(user_id), name)
                elif hasattr(device, 'enroll_user'):
                    added = device.enroll_user(str(user_id), name)
                elif hasattr(device, 'create_user'):
                    added = device.create_user(str(user_id), name)
                
                if added:
                    success_count += 1
            
            logger.info(f"Synced {success_count}/{len(users)} users to {device_name}")
            return True, f"Synced {success_count} users successfully"
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False, f"Sync failed: {str(e)}"
    
    def test_device(self, device_name: str) -> tuple:
        """
        Test a specific device.
        
        Args:
            device_name: Name of device to test
            
        Returns:
            Tuple of (success, message)
        """
        device = self.get_device(device_name)
        
        if not device:
            return False, f"Device '{device_name}' not found"
        
        try:
            # Test connection
            if hasattr(device, 'is_connected'):
                if not device.is_connected():
                    return False, "Device not connected"
            
            # Get device info
            info = {}
            if hasattr(device, 'get_info'):
                info = device.get_info()
            elif hasattr(device, 'get_device_info'):
                info = device.get_device_info()
            elif hasattr(device, 'get_device_status'):
                info = device.get_device_status()
            
            return True, f"Device test successful: {info}"
            
        except Exception as e:
            return False, f"Device test failed: {str(e)}"
    
    def disconnect_all(self):
        """Disconnect all devices."""
        for name, device in self.devices.items():
            try:
                if hasattr(device, 'disconnect'):
                    device.disconnect()
                logger.info(f"Disconnected device '{name}'")
            except Exception as e:
                logger.error(f"Error disconnecting device '{name}': {e}")
        
        self.devices.clear()

device_service = DeviceService()        