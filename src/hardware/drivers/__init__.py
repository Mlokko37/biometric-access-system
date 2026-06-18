"""
Hardware Drivers Package
Exports all hardware drivers for easy import
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Generic drivers
from .fingerprint_scanner import FingerprintScanner
from .facial_camera import FacialCamera
from .access_controller import AccessController

# Manufacturer-specific drivers - initialize as Any to avoid type conflicts
ZKTecoDevice: Any = None
SupremaDevice: Any = None
HikvisionDevice: Any = None

# Try to import manufacturer-specific drivers
try:
    from .zkteco.zkteco_driver import ZKTecoDevice as _ZKTecoDevice
    ZKTecoDevice = _ZKTecoDevice
    logger.debug("ZKTeco driver loaded successfully")
except ImportError as e:
    logger.debug(f"ZKTeco driver not available: {e}")
    # Create placeholder
    class ZKTecoDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("ZKTeco driver not available. Please install required dependencies.")
    ZKTecoDevice = ZKTecoDevicePlaceholder

try:
    from .suprema.suprema_driver import SupremaDevice as _SupremaDevice
    SupremaDevice = _SupremaDevice
    logger.debug("Suprema driver loaded successfully")
except ImportError as e:
    logger.debug(f"Suprema driver not available: {e}")
    # Create placeholder
    class SupremaDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("Suprema driver not available. Please install required dependencies.")
    SupremaDevice = SupremaDevicePlaceholder

try:
    from .hikvision.hikvision_driver import HikvisionDevice as _HikvisionDevice
    HikvisionDevice = _HikvisionDevice
    logger.debug("Hikvision driver loaded successfully")
except ImportError as e:
    logger.debug(f"Hikvision driver not available: {e}")
    # Create placeholder
    class HikvisionDevicePlaceholder:
        def __init__(self, *args, **kwargs):
            raise ImportError("Hikvision driver not available. Please install required dependencies.")
    HikvisionDevice = HikvisionDevicePlaceholder

# Export all drivers
__all__ = [
    'FingerprintScanner',
    'FacialCamera',
    'AccessController',
    'ZKTecoDevice',
    'SupremaDevice',
    'HikvisionDevice'
]