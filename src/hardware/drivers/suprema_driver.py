"""
Suprema Biometric Device Driver
Uses manufacturer-specific implementation from suprema folder
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# Import from manufacturer-specific implementation
try:
    from .suprema.suprema_driver import SupremaDevice as BaseSupremaDevice
    HAS_MANUFACTURER_DRIVER = True
    logger = logging.getLogger(__name__)
    logger.info("[OK] Loaded manufacturer-specific Suprema driver")
except ImportError as e:
    HAS_MANUFACTURER_DRIVER = False
    logger = logging.getLogger(__name__)
    logger.warning(f"[WARN] Manufacturer Suprema driver not found: {e}")
    logger.warning("Using generic fallback implementation")

class SupremaDevice:
    """
    Suprema Biometric Device Driver
    Wrapper that uses manufacturer-specific implementation if available.
    """
    
    def __init__(self, ip: str, port: int = 443, username: str = 'admin', 
                 password: str = 'admin', use_https: bool = True):
        """
        Initialize Suprema device.
        
        Args:
            ip: Device IP address
            port: Device port (default 443 for HTTPS)
            username: Authentication username
            password: Authentication password
            use_https: Use HTTPS (default True)
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.use_https = use_https
        self._device = None
        self._using_manufacturer = False
        self.socket = None
        self.connected = False
        
        if HAS_MANUFACTURER_DRIVER:
            try:
                # Try with full parameters (no timeout)
                self._device = BaseSupremaDevice(
                    ip=ip, 
                    port=port, 
                    username=username, 
                    password=password, 
                    use_https=use_https
                )
                self._using_manufacturer = True
                logger.info(f"Using Suprema manufacturer driver for {ip}:{port}")
            except TypeError:
                try:
                    # Try without use_https
                    self._device = BaseSupremaDevice(
                        ip=ip, 
                        port=port, 
                        username=username, 
                        password=password
                    )
                    self._using_manufacturer = True
                    logger.info(f"Using Suprema manufacturer driver (without HTTPS) for {ip}:{port}")
                except TypeError:
                    try:
                        # Try with just ip and port (no auth)
                        self._device = BaseSupremaDevice(ip, port)
                        self._using_manufacturer = True
                        logger.info(f"Using Suprema manufacturer driver (compatibility mode) for {ip}:{port}")
                    except:
                        self._device = None
                        self._using_manufacturer = False
                        self._init_generic()
                        logger.warning("Could not initialize manufacturer driver, using generic")
        else:
            self._device = None
            self._using_manufacturer = False
            self._init_generic()
            logger.info(f"Using generic Suprema driver for {ip}:{port}")
    
    def _init_generic(self):
        """Initialize generic implementation attributes."""
        import socket
        self.socket = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to Suprema device."""
        if self._using_manufacturer and self._device is not None:
            try:
                return self._device.connect()
            except:
                return False
        else:
            return self._generic_connect()
    
    def _generic_connect(self) -> bool:
        """Generic implementation of connect."""
        try:
            import socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)  # Fixed timeout
            self.socket.connect((self.ip, self.port))
            self.connected = True
            logger.info(f"Connected to Suprema device at {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of users from device."""
        if self._using_manufacturer and self._device is not None:
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
        if self._using_manufacturer and self._device is not None:
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
    
    def add_user(self, user_id: str, name: str, privilege: int = 0) -> bool:
        """Add user to device."""
        if self._using_manufacturer and self._device is not None and hasattr(self._device, 'add_user'):
            try:
                # Try with 3 parameters
                return self._device.add_user(user_id=user_id, name=name)
            except TypeError:
                try:
                    # Try with 2 parameters
                    return self._device.add_user(user_id, name)
                except TypeError:
                    try:
                        # Try with keyword arguments
                        return self._device.add_user(user_id=user_id, name=name)
                    except:
                        return False
        return False
    
    def delete_user(self, user_id: str) -> bool:
        """Delete user from device."""
        if self._using_manufacturer and self._device is not None and hasattr(self._device, 'delete_user'):
            try:
                return self._device.delete_user(user_id)
            except:
                return False
        return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get device information."""
        if self._using_manufacturer and self._device is not None:
            base_info = {}
            if hasattr(self._device, 'get_info'):
                base_info = self._device.get_info()
            elif hasattr(self._device, 'get_device_info'):
                base_info = self._device.get_device_info()
            elif hasattr(self._device, 'get_device_status'):
                base_info = self._device.get_device_status()
                
            base_info['driver_type'] = 'manufacturer'
            base_info['ip'] = self.ip
            base_info['port'] = self.port
            base_info['username'] = self.username
            base_info['use_https'] = self.use_https
            return base_info
        else:
            return {
                'ip': self.ip,
                'port': self.port,
                'connected': self.connected,
                'driver_type': 'generic',
                'username': self.username,
                'use_https': self.use_https
            }
    
    def disconnect(self):
        """Disconnect from device."""
        if self._using_manufacturer and self._device is not None:
            if hasattr(self._device, 'disconnect'):
                try:
                    self._device.disconnect()
                except:
                    pass
        elif hasattr(self, 'socket') and self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.connected = False
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        if self._using_manufacturer and self._device is not None:
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