"""
Hikvision Access Control Device Driver
Uses manufacturer-specific implementation from hikvision folder
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Import from manufacturer-specific implementation
try:
    from .hikvision.hikvision_driver import HikvisionDevice as BaseHikvisionDevice
    HAS_MANUFACTURER_DRIVER = True
    logger = logging.getLogger(__name__)
    logger.info("[OK] Loaded manufacturer-specific Hikvision driver")
except ImportError as e:
    HAS_MANUFACTURER_DRIVER = False
    logger = logging.getLogger(__name__)
    logger.warning(f"[WARN] Manufacturer Hikvision driver not found: {e}")
    logger.warning("Using generic fallback implementation")

class HikvisionDevice:
    """
    Hikvision Access Control Device Driver
    Wrapper that uses manufacturer-specific implementation if available.
    """
    
    def __init__(self, ip: str, port: int = 8000, username: str = 'admin', 
                 password: str = 'admin123', timeout: int = 30):
        """
        Initialize Hikvision device.
        
        Args:
            ip: Device IP address
            port: Device port (default 8000 for Hikvision)
            username: Authentication username
            password: Authentication password
            timeout: Connection timeout in seconds
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        
        if HAS_MANUFACTURER_DRIVER:
            # BaseHikvisionDevice expects 4 parameters: ip, port, username, password
            # Remove timeout as it's not accepted by the base driver
            self._device = BaseHikvisionDevice(ip, port, username, password)
            self._using_manufacturer = True
            logger.info(f"Using Hikvision manufacturer driver for {ip}:{port}")
        else:
            self._device = None
            self._using_manufacturer = False
            self._init_generic()
            logger.info(f"Using generic Hikvision driver for {ip}:{port}")
    
    def _init_generic(self):
        """Initialize generic implementation attributes."""
        import requests
        self.session = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Hikvision device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
            return self._device.connect()
        else:
            return self._generic_connect()
    
    def _generic_connect(self) -> bool:
        """Generic implementation of connect."""
        try:
            import requests
            from requests.auth import HTTPDigestAuth
            
            self.session = requests.Session()
            # Test connection with a simple request
            url = f"http://{self.ip}:{self.port}/ISAPI/System/status"
            response = self.session.get(url, auth=HTTPDigestAuth(self.username, self.password), timeout=self.timeout)
            
            if response.status_code == 200:
                self.connected = True
                logger.info(f"Connected to Hikvision device at {self.ip}:{self.port}")
                return True
            else:
                logger.error(f"Authentication failed for Hikvision device")
                return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of users from device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
            if hasattr(self._device, 'get_users'):
                return self._device.get_users()
            elif hasattr(self._device, 'get_all_users'):
                return self._device.get_all_users()
            else:
                return []
        else:
            return []
    
    def get_attendance(self) -> List[Dict[str, Any]]:
        """Get attendance records from device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
            if hasattr(self._device, 'get_attendance'):
                return self._device.get_attendance()
            elif hasattr(self._device, 'get_all_attendance'):
                return self._device.get_all_attendance()
            elif hasattr(self._device, 'get_events'):
                return self._device.get_events()
            else:
                return []
        else:
            return []
    
    def add_user(self, user_id: str, name: str, card_number: Optional[str] = None, 
                 pin_code: Optional[str] = None) -> bool:
        """Add user to device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None and hasattr(self._device, 'add_user'):
            # Convert None to empty string for the base driver
            card = card_number if card_number is not None else ""
            pin = pin_code if pin_code is not None else ""
            return self._device.add_user(user_id, name, card, pin)
        return False
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user from device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None and hasattr(self._device, 'delete_user'):
            return self._device.delete_user(user_id)
        return False
    
    def open_door(self, door_id: int = 1, duration: int = 3) -> bool:
        """Open door."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None and hasattr(self._device, 'open_door'):
            return self._device.open_door(door_id, duration)
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get device information."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
            base_info = {}
            if hasattr(self._device, 'get_info'):
                base_info = self._device.get_info()
            base_info['driver_type'] = 'manufacturer'
            base_info['ip'] = self.ip
            base_info['port'] = self.port
            return base_info
        else:
            return {
                'ip': self.ip,
                'port': self.port,
                'connected': self.connected,
                'driver_type': 'generic'
            }
    
    def disconnect(self):
        """Disconnect from device."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
            if hasattr(self._device, 'disconnect'):
                self._device.disconnect()
        elif hasattr(self, 'session') and self.session:
            try:
                self.session.close()
            except:
                pass
            self.connected = False
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        if HAS_MANUFACTURER_DRIVER and self._device is not None:
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