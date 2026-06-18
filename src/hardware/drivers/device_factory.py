from .hikvision import HikvisionDevice
from .suprema import SupremaDevice
from .zkteco import ZKTecoDevice

class DeviceFactory:
    @staticmethod
    def create_device(device_type, **kwargs):
        devices = {
            'hikvision': HikvisionDevice,
            'suprema': SupremaDevice,
            'zkteco': ZKTecoDevice
        }
        
        if device_type not in devices:
            raise ValueError(f"Unsupported device type: {device_type}")
        
        return devices[device_type](**kwargs)