"""
ZKTeco Biometric Device Driver
Uses manufacturer-specific implementation from zkteco folder
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Import from manufacturer-specific implementation
try:
    # Note: This imports from your existing file: src/hardware/drivers/zkteco/zkteco_driver.py
    from .zkteco.zkteco_driver import ZKTecoDevice as BaseZKTecoDevice
    HAS_MANUFACTURER_DRIVER = True
    logger = logging.getLogger(__name__)
    logger.info("[OK] Loaded manufacturer-specific ZKTeco driver")
except ImportError as e:
    HAS_MANUFACTURER_DRIVER = False
    logger = logging.getLogger(__name__)
    logger.warning(f"[WARN] Manufacturer ZKTeco driver not found: {e}")
    logger.warning("Using generic fallback implementation")

class ZKTecoDevice:
    """
    ZKTeco Biometric Device Driver
    Wrapper that uses manufacturer-specific implementation if available.
    """
    
    def __init__(self, ip: str, port: int = 4370, timeout: int = 30):
        """
        Initialize ZKTeco device.
        
        Args:
            ip: Device IP address
            port: Device port (default 4370)
            timeout: Connection timeout in seconds
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        
        if HAS_MANUFACTURER_DRIVER:
            # Use manufacturer-specific implementation from zkteco folder
            self._device = BaseZKTecoDevice(ip, port, timeout)
            self._using_manufacturer = True
            logger.info(f"Using ZKTeco manufacturer driver for {ip}:{port}")
        else:
            # Use generic implementation
            self._device = None
            self._using_manufacturer = False
            self._init_generic()
            logger.info(f"Using generic ZKTeco driver for {ip}:{port}")
    
    def _init_generic(self):
        """Initialize generic implementation attributes."""
        import socket
        self.socket = None
        self.connected = False
        self.session_id = 0
        self.reply_id = 0
        self.serial_number = ""
        self.firmware_version = ""
        self.user_count = 0
        self.attendance_count = 0
    
    def connect(self) -> bool:
        """Connect to ZKTeco device."""
        if HAS_MANUFACTURER_DRIVER:
            return self._device.connect()
        else:
            return self._generic_connect()
    
    def _generic_connect(self) -> bool:
        """Generic implementation of connect."""
        try:
            import socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            self.connected = True
            logger.info(f"Connected to ZKTeco device at {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def get_firmware(self) -> str:
        """Get device firmware version."""
        if HAS_MANUFACTURER_DRIVER:
            return self._device.get_firmware_version() if hasattr(self._device, 'get_firmware_version') else "Unknown"
        else:
            return self.firmware_version
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of users from device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'get_users'):
                return self._device.get_users()
            elif hasattr(self._device, 'get_all_users'):
                return self._device.get_all_users()
            else:
                logger.warning("Manufacturer driver doesn't have get_users method")
                return []
        else:
            logger.warning("Generic driver doesn't support get_users")
            return []
    
    def get_attendance(self) -> List[Dict[str, Any]]:
        """Get attendance records from device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'get_attendance'):
                return self._device.get_attendance()
            elif hasattr(self._device, 'get_all_attendance'):
                return self._device.get_all_attendance()
            else:
                logger.warning("Manufacturer driver doesn't have get_attendance method")
                return []
        else:
            logger.warning("Generic driver doesn't support get_attendance")
            return []
    
    def add_user(self, user_id: str, name: str, privilege: int = 0,
                 password: str = "", fingerprint: bytes = None) -> bool:
        """Add user to device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'add_user'):
                return self._device.add_user(user_id, name, privilege, password, fingerprint)
            else:
                logger.warning("Manufacturer driver doesn't have add_user method")
                return False
        else:
            logger.warning("Generic driver doesn't support add_user")
            return False
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user from device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'delete_user'):
                return self._device.delete_user(user_id)
            else:
                logger.warning("Manufacturer driver doesn't have delete_user method")
                return False
        else:
            logger.warning("Generic driver doesn't support delete_user")
            return False
    
    def delete_all_users(self) -> bool:
        """Delete all users from device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'delete_all_users'):
                return self._device.delete_all_users()
            elif hasattr(self._device, 'clear_all_users'):
                return self._device.clear_all_users()
            else:
                logger.warning("Manufacturer driver doesn't have delete_all_users method")
                return False
        else:
            logger.warning("Generic driver doesn't support delete_all_users")
            return False
    
    def verify_user(self, user_id: str, fingerprint: bytes) -> Tuple[bool, float]:
        """Verify user with fingerprint."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'verify_user'):
                return self._device.verify_user(user_id, fingerprint)
            else:
                logger.warning("Manufacturer driver doesn't have verify_user method")
                return False, 0.0
        else:
            logger.warning("Generic driver doesn't support verify_user")
            return False, 0.0
    
    def identify_user(self, fingerprint: bytes) -> Tuple[Optional[str], float]:
        """Identify user by fingerprint."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'identify_user'):
                return self._device.identify_user(fingerprint)
            else:
                logger.warning("Manufacturer driver doesn't have identify_user method")
                return None, 0.0
        else:
            logger.warning("Generic driver doesn't support identify_user")
            return None, 0.0
    
    def enable_device(self) -> bool:
        """Enable device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'enable_device'):
                return self._device.enable_device()
            else:
                return True
        else:
            return True
    
    def disable_device(self) -> bool:
        """Disable device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'disable_device'):
                return self._device.disable_device()
            else:
                return True
        else:
            return True
    
    def get_time(self) -> Optional[datetime]:
        """Get device time."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'get_time'):
                return self._device.get_time()
            else:
                return datetime.now()
        else:
            return datetime.now()
    
    def set_time(self, dt: datetime = None) -> bool:
        """Set device time."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'set_time'):
                return self._device.set_time(dt)
            else:
                return True
        else:
            return True
    
    def get_info(self) -> Dict[str, Any]:
        """Get device information."""
        if HAS_MANUFACTURER_DRIVER:
            base_info = {}
            if hasattr(self._device, 'get_info'):
                base_info = self._device.get_info()
            elif hasattr(self._device, 'get_device_info'):
                base_info = self._device.get_device_info()
            
            base_info['driver_type'] = 'manufacturer'
            base_info['ip'] = self.ip
            base_info['port'] = self.port
            return base_info
        else:
            return {
                'ip': self.ip,
                'port': self.port,
                'connected': self.connected,
                'firmware': self.firmware_version,
                'driver_type': 'generic'
            }
    
    def disconnect(self):
        """Disconnect from device."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'disconnect'):
                self._device.disconnect()
            elif hasattr(self._device, 'close'):
                self._device.close()
        elif hasattr(self, 'socket') and self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.connected = False
            logger.info("Disconnected from ZKTeco device")
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        if HAS_MANUFACTURER_DRIVER:
            if hasattr(self._device, 'is_connected'):
                return self._device.is_connected()
            elif hasattr(self._device, 'connected'):
                return self._device.connected
            else:
                return True
        else:
            return self.connected
    
    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()