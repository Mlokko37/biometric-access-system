# src/hardware/utils/device_discovery.py
"""
Hardware device discovery utilities
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def discover_all_devices() -> Dict[str, Any]:
    """Discover all hardware devices"""
    devices = {
        'serial': discover_serial_devices(),
        'cameras': discover_cameras(),
        'usb': discover_usb_devices()
    }
    
    return devices


# Alias for backward compatibility
discover_devices = discover_all_devices


def discover_serial_devices() -> List[Dict[str, Any]]:
    """Discover all connected serial devices"""
    devices = []
    
    try:
        import serial.tools.list_ports
        
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            device_info = {
                'device': port.device,
                'description': port.description,
                'manufacturer': port.manufacturer,
                'hwid': port.hwid,
                'vid': port.vid if port.vid else None,
                'pid': port.pid if port.pid else None,
                'serial_number': port.serial_number
            }
            devices.append(device_info)
            
            logger.info(f"Found serial device: {port.device} - {port.description}")
    
    except ImportError:
        logger.warning("PySerial not installed, cannot discover serial devices")
    except Exception as e:
        logger.error(f"Error discovering serial devices: {e}")
    
    return devices


def discover_cameras() -> List[Dict[str, Any]]:
    """Discover all connected cameras"""
    cameras = []
    
    try:
        import cv2
        
        # Test first 10 camera indices
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # CAP_DSHOW for Windows
            if cap.isOpened():
                # Try to get some camera properties
                width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                
                camera_info = {
                    'index': i,
                    'width': width,
                    'height': height,
                    'description': f'Camera {i}'
                }
                cameras.append(camera_info)
                
                logger.info(f"Found camera at index {i}: {width}x{height}")
                
                cap.release()
    
    except ImportError:
        logger.warning("OpenCV not installed, cannot discover cameras")
    except Exception as e:
        logger.error(f"Error discovering cameras: {e}")
    
    return cameras


def discover_usb_devices() -> List[Dict[str, Any]]:
    """Discover USB devices (platform-specific)"""
    devices = []
    
    try:
        import platform
        system = platform.system()
        
        if system == "Windows":
            # Use Windows Registry to get USB devices
            try:
                import winreg
                
                # Access USB registry key
                key_path = r"SYSTEM\CurrentControlSet\Enum\USB"
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            
                            try:
                                device_desc = winreg.QueryValueEx(subkey, "DeviceDesc")[0]
                                # Extract just the description part
                                if ";" in str(device_desc):
                                    device_desc = str(device_desc).split(";")[-1]
                            except:
                                device_desc = subkey_name
                            
                            devices.append({
                                'device_id': subkey_name,
                                'description': device_desc
                            })
                            
                            i += 1
                            winreg.CloseKey(subkey)
                            
                        except WindowsError:
                            break
                    
                    winreg.CloseKey(key)
                    
                except Exception as e:
                    logger.debug(f"Could not access USB registry: {e}")
                
            except ImportError:
                logger.debug("winreg not available")
        
        elif system == "Linux":
            # Use lsusb command
            try:
                import subprocess
                result = subprocess.run(['lsusb'], capture_output=True, text=True)
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 6:
                                device_info = {
                                    'bus': parts[1],
                                    'device': parts[3].rstrip(':'),
                                    'vendor_id': parts[5].split(':')[0],
                                    'product_id': parts[5].split(':')[1],
                                    'description': ' '.join(parts[6:])
                                }
                                devices.append(device_info)
            except Exception as e:
                logger.debug(f"Could not run lsusb: {e}")
    
    except Exception as e:
        logger.error(f"Error discovering USB devices: {e}")
    
    return devices


def find_biometric_devices() -> Dict[str, Any]:
    """Specifically look for biometric devices"""
    biometric_devices = {
        'fingerprint_scanners': [],
        'cameras': []
    }
    
    # Check serial devices for known biometric scanners
    serial_devices = discover_serial_devices()
    
    # Known vendor IDs for fingerprint scanners
    fingerprint_vendors = {
        '0403': 'Future Technology Devices International (FTDI)',  # Common for USB-serial converters
        '10C4': 'Silicon Labs',  # Another common USB-serial
        '1A86': 'QinHeng Electronics',  # CH340 chips
    }
    
    for device in serial_devices:
        if device.get('vid'):
            vid_hex = f"{device['vid']:04x}".upper()
            if vid_hex in fingerprint_vendors:
                device['likely_scanner'] = True
                device['vendor_name'] = fingerprint_vendors[vid_hex]
                biometric_devices['fingerprint_scanners'].append(device)
    
    # Check cameras suitable for facial recognition
    cameras = discover_cameras()
    for camera in cameras:
        # Check if camera has reasonable resolution for facial recognition
        if camera['width'] >= 640 and camera['height'] >= 480:
            camera['suitable_for_facial'] = True
            biometric_devices['cameras'].append(camera)
    
    return biometric_devices


# Test function
if __name__ == "__main__":
    print("Discovering hardware devices...")
    devices = discover_all_devices()
    
    print(f"\nFound {len(devices['serial'])} serial devices:")
    for device in devices['serial']:
        print(f"  {device['device']}: {device['description']}")
    
    print(f"\nFound {len(devices['cameras'])} cameras:")
    for camera in devices['cameras']:
        print(f"  Camera {camera['index']}: {camera['width']}x{camera['height']}")
    
    print(f"\nFound {len(devices['usb'])} USB devices:")
    for usb in devices['usb']:
        print(f"  {usb.get('description', 'Unknown')}")