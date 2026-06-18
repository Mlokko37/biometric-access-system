"""
Base Device Class for all hardware devices
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class BaseDevice(ABC):
    """Abstract base class for all hardware devices."""
    
    def __init__(self, ip: str, port: int, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize base device.
        
        Args:
            ip: Device IP address
            port: Device port
            username: Authentication username (optional)
            password: Authentication password (optional)
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.connected = False
        self.device_type = "base"
        self.model = "Unknown"
        self.serial_number = ""
        self.firmware_version = ""
        
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the device."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the device."""
        pass
    
    @abstractmethod
    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of users from device."""
        pass
    
    @abstractmethod
    def send_command(self, command: str, params: Optional[Dict] = None) -> Any:
        """Send command to device."""
        pass
    
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self.connected
    
    def get_info(self) -> Dict[str, Any]:
        """Get device information."""
        return {
            'ip': self.ip,
            'port': self.port,
            'device_type': self.device_type,
            'model': self.model,
            'serial_number': self.serial_number,
            'firmware': self.firmware_version,
            'connected': self.connected
        }
    
    def __str__(self) -> str:
        return f"{self.device_type.upper()} Device at {self.ip}:{self.port}"