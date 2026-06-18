"""
Base biometric device interface
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any


class BaseBiometricDevice(ABC):
    """Abstract base class for all biometric devices"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the device"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is connected"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from device"""
        pass
    
    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information"""
        pass
    
    @abstractmethod
    def test_device(self) -> Tuple[bool, str]:
        """Test device functionality"""
        pass