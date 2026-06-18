"""
Hardware interfaces package
"""

from .biometric_interface import BaseBiometricDevice
from .fingerprint_scanner import FingerprintScanner
from .facial_recognition import FacialRecognition
from .camera_controller import CameraController
from .access_controller import AccessController

__all__ = [
    'BaseBiometricDevice',
    'FingerprintScanner',
    'FacialRecognition',
    'CameraController',
    'AccessController'
]