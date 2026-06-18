# admin/services/__init__.py
from .device_service import DeviceService

# Create a shared singleton instance
shared_device_service = DeviceService()