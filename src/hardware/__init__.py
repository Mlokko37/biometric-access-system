"""
Hardware Module for Biometric Access System
"""

from .hardware_manager import HardwareManager, HardwareStatus
from .device_service import DeviceService
from .drivers.fingerprint_scanner import FingerprintScanner
from .drivers.facial_camera import FacialCamera
from .drivers.access_controller import AccessController
from .drivers.zkteco_driver import ZKTecoDevice

__all__ = [
    'HardwareManager',
    'HardwareStatus',
    'DeviceService',
    'FingerprintScanner',
    'FacialCamera',
    'AccessController',
    'ZKTecoDevice'
]