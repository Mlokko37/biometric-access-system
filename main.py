#!/usr/bin/env python3
"""
Biometric Student Access Control System
Kibabii University - Group Three
Main Entry Point with Real Hardware Support
"""

import os
import sys
import io
import logging
import time
import argparse
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# Fix for Windows console encoding - MUST BE FIRST
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
log_dir = 'data/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f'system_{datetime.now().strftime("%Y%m%d")}.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ============================================
# REAL HARDWARE SUPPORT
# ============================================
REAL_HARDWARE_AVAILABLE = False
real_hardware_devices = {}

try:
    # Try to import real hardware drivers
    from src.hardware.drivers.fingerprint_scanner import FingerprintScanner
    from src.hardware.drivers.facial_camera import FacialCamera
    from src.hardware.drivers.access_controller import AccessController
    from src.hardware.drivers.zkteco.zkteco_driver import ZKTecoDevice
    from src.hardware.drivers.hikvision.hikvision_driver import HikvisionDevice
    from src.hardware.drivers.suprema.suprema_driver import SupremaDevice
    from src.hardware.device_service import DeviceService
    from src.hardware.hardware_manager import HardwareManager
    
    REAL_HARDWARE_AVAILABLE = True
    logger.info("[OK] Real hardware drivers loaded successfully")
except ImportError as e:
    logger.warning(f"Real hardware drivers not available: {e}")
    logger.warning("Running in simulation mode")

# ============================================
# ENVIRONMENT SETUP
# ============================================
def load_environment():
    """Load environment variables from .env file."""
    try:
        from dotenv import load_dotenv
        env_file = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"[OK] Environment loaded from {env_file}")
        else:
            logger.warning("[WARN] .env file not found, using system environment")
            create_default_env()
    except ImportError:
        logger.warning("[WARN] python-dotenv not installed, using system environment")

def create_default_env():
    """Create default .env file if it doesn't exist."""
    env_template = """# Database Configuration
DB_NAME=biometric_access_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Application Configuration
APP_SECRET_KEY=your-secret-key-change-this
APP_DEBUG=True
APP_ENV=development

# Hardware Configuration - Linux/Mac
FINGERPRINT_PORT=/dev/ttyUSB0
FINGERPRINT_BAUDRATE=57600
CAMERA_INDEX=0
ARDUINO_PORT=/dev/ttyUSB1
ARDUINO_BAUDRATE=9600

# ZKTeco Configuration
ZKTECO_IP=192.168.1.201
ZKTECO_PORT=4370
ZKTECO_USERNAME=admin
ZKTECO_PASSWORD=12345

# Hikvision Configuration
HIKVISION_IP=192.168.1.100
HIKVISION_PORT=80
HIKVISION_USERNAME=admin
HIKVISION_PASSWORD=admin123

# Suprema Configuration
SUPREMA_IP=192.168.1.200
SUPREMA_PORT=443
SUPREMA_USERNAME=admin
SUPREMA_PASSWORD=admin
SUPREMA_USE_HTTPS=true

# Template Storage
TEMPLATE_STORAGE_PATH=./data/templates
FINGERPRINT_TEMPLATE_PATH=./data/templates/fingerprint
FACIAL_TEMPLATE_PATH=./data/templates/facial
"""
    try:
        with open('.env', 'w') as f:
            f.write(env_template)
        logger.info("[OK] Created default .env file. Please update with your configuration.")
        print("\n[MENU] Created default .env file. Please update it with your configuration.")
        print("   Run: python main.py hardware detect  to auto-detect hardware ports")
    except Exception as e:
        logger.error(f"[ERROR] Failed to create .env file: {e}")

# ============================================
# HARDWARE INITIALIZATION
# ============================================
def initialize_hardware() -> Dict[str, Any]:
    """Initialize all connected hardware devices."""
    global real_hardware_devices
    
    if not REAL_HARDWARE_AVAILABLE:
        logger.warning("Real hardware drivers not available - using simulation")
        return {}
    
    logger.info("=" * 60)
    logger.info("INITIALIZING REAL HARDWARE")
    logger.info("=" * 60)
    
    devices = {}
    
    # 1. Initialize Fingerprint Scanner
    print("\n[INFO] Initializing Fingerprint Scanner...")
    fp_port = os.getenv('FINGERPRINT_PORT', '/dev/ttyUSB0')
    fp_baud = int(os.getenv('FINGERPRINT_BAUDRATE', 57600))
    
    try:
        fp_scanner = FingerprintScanner(port=fp_port, baudrate=fp_baud)
        if fp_scanner.connect():
            fp_info = fp_scanner.get_info()
            devices['fingerprint'] = fp_scanner
            logger.info(f"[OK] Fingerprint scanner connected on {fp_port}")
            logger.info(f"   Model: {fp_info.get('model', 'Unknown')}")
            logger.info(f"   Capacity: {fp_info.get('capacity', 0)}")
            logger.info(f"   Templates: {fp_scanner.get_template_count()}")
        else:
            logger.error(f"[ERROR] Failed to connect to fingerprint scanner on {fp_port}")
    except Exception as e:
        logger.error(f"[ERROR] Fingerprint scanner error: {e}")
    
    # 2. Initialize Camera
    print("\n[CAMERA] Initializing Facial Recognition Camera...")
    camera_index = int(os.getenv('CAMERA_INDEX', 0))
    
    try:
        camera = FacialCamera(camera_index=camera_index)
        if camera.initialize():
            camera_info = camera.get_info()
            devices['camera'] = camera
            logger.info(f"[OK] Camera initialized")
            logger.info(f"   Resolution: {camera_info.get('width', 0)}x{camera_info.get('height', 0)}")
            
            # Test capture
            test_frame = camera.capture_frame()
            if test_frame is not None:
                logger.info("   [OK] Test capture successful")
    except Exception as e:
        logger.error(f"[ERROR] Camera initialization error: {e}")
    
    # 3. Initialize Access Controller (Arduino/Relay)
    print("\n[LOCK] Initializing Access Controller...")
    arduino_port = os.getenv('ARDUINO_PORT', '/dev/ttyUSB1')
    arduino_baud = int(os.getenv('ARDUINO_BAUDRATE', 9600))
    
    try:
        access_ctrl = AccessController(port=arduino_port, baudrate=arduino_baud)
        if access_ctrl.connect():
            devices['access_controller'] = access_ctrl
            logger.info(f"[OK] Access controller connected on {arduino_port}")
            
            # Test connection
            if access_ctrl.test():
                logger.info("   [OK] Communication test successful")
    except Exception as e:
        logger.error(f"[ERROR] Access controller error: {e}")
    
    # 4. Initialize ZKTeco Device
    print("\n[DEVICE] Initializing ZKTeco Device...")
    zk_ip = os.getenv('ZKTECO_IP', '192.168.1.201')
    zk_port = int(os.getenv('ZKTECO_PORT', 4370))
    zk_user = os.getenv('ZKTECO_USERNAME', 'admin')
    zk_pass = os.getenv('ZKTECO_PASSWORD', '12345')
    
    try:
        # ZKTecoDevice initialization (some models need username/password, some don't)
        try:
            zk_device = ZKTecoDevice(ip=zk_ip, port=zk_port, username=zk_user, password=zk_pass)
        except TypeError:
            # If username/password not accepted, try without
            zk_device = ZKTecoDevice(ip=zk_ip, port=zk_port)
        
        if zk_device.connect():
            devices['zkteco'] = zk_device
            logger.info(f"[OK] ZKTeco device connected at {zk_ip}:{zk_port}")
            
            # Get device info
            try:
                status = zk_device.get_device_status()
                logger.info(f"   Model: {status.get('model', 'Unknown')}")
                logger.info(f"   Firmware: {status.get('firmware', 'Unknown')}")
                logger.info(f"   Users: {status.get('user_count', 0)}")
            except:
                logger.info("   Device info retrieved")
        else:
            logger.error(f"[ERROR] Failed to connect to ZKTeco device at {zk_ip}:{zk_port}")
    except Exception as e:
        logger.error(f"[ERROR] ZKTeco device error: {e}")
    
    # 5. Initialize Hikvision Device
    print("\n[CAMERA] Initializing Hikvision Device...")
    hik_ip = os.getenv('HIKVISION_IP', '192.168.1.100')
    hik_port = int(os.getenv('HIKVISION_PORT', 80))
    hik_user = os.getenv('HIKVISION_USERNAME', 'admin')
    hik_pass = os.getenv('HIKVISION_PASSWORD', 'admin123')
    
    try:
        hik_device = HikvisionDevice(ip=hik_ip, port=hik_port, username=hik_user, password=hik_pass)
        
        if hik_device.connect():
            devices['hikvision'] = hik_device
            logger.info(f"[OK] Hikvision device connected at {hik_ip}:{hik_port}")
            logger.info(f"   Model: {hik_device.model}")
            logger.info(f"   Firmware: {hik_device.firmware_version}")
            logger.info(f"   Doors: {hik_device.door_count}")
        else:
            logger.error(f"[ERROR] Failed to connect to Hikvision device at {hik_ip}:{hik_port}")
    except Exception as e:
        logger.error(f"[ERROR] Hikvision device error: {e}")
    
    # 6. Initialize Suprema Device
    print("\n[SECURE] Initializing Suprema Device...")
    sup_ip = os.getenv('SUPREMA_IP', '192.168.1.200')
    sup_port = int(os.getenv('SUPREMA_PORT', 443))
    sup_user = os.getenv('SUPREMA_USERNAME', 'admin')
    sup_pass = os.getenv('SUPREMA_PASSWORD', 'admin')
    sup_https = os.getenv('SUPREMA_USE_HTTPS', 'true').lower() == 'true'
    
    try:
        suprema_device = SupremaDevice(
            ip=sup_ip, 
            port=sup_port, 
            username=sup_user, 
            password=sup_pass, 
            use_https=sup_https
        )
        
        if suprema_device.connect():
            devices['suprema'] = suprema_device
            logger.info(f"[OK] Suprema device connected at {sup_ip}:{sup_port}")
            
            # Get device info
            try:
                status = suprema_device.get_device_status()
                logger.info(f"   Model: {status.get('model', 'Unknown')}")
                logger.info(f"   Firmware: {status.get('firmware', 'Unknown')}")
                logger.info(f"   Users: {status.get('user_count', 0)}")
            except:
                logger.info("   Device info retrieved")
        else:
            logger.error(f"[ERROR] Failed to connect to Suprema device at {sup_ip}:{sup_port}")
    except Exception as e:
        logger.error(f"[ERROR] Suprema device error: {e}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("HARDWARE INITIALIZATION SUMMARY:")
    logger.info(f"  Fingerprint Scanner: {'[OK]' if 'fingerprint' in devices else '[ERROR]'}")
    logger.info(f"  Facial Camera: {'[OK]' if 'camera' in devices else '[ERROR]'}")
    logger.info(f"  Access Controller: {'[OK]' if 'access_controller' in devices else '[ERROR]'}")
    logger.info(f"  ZKTeco Device: {'[OK]' if 'zkteco' in devices else '[ERROR]'}")
    logger.info(f"  Hikvision Device: {'[OK]' if 'hikvision' in devices else '[ERROR]'}")
    logger.info(f"  Suprema Device: {'[OK]' if 'suprema' in devices else '[ERROR]'}")
    logger.info("=" * 60)
    
    real_hardware_devices = devices
    return devices

def detect_hardware_ports():
    """Auto-detect connected hardware devices and ports."""
    print("\n[INFO] Auto-detecting hardware...")
    print("-" * 40)
    
    # Detect serial ports
    detected = {
        'fingerprint': [],
        'arduino': [],
        'cameras': []
    }
    
    try:
        import serial.tools.list_ports
        
        # List all serial ports
        ports = list(serial.tools.list_ports.comports())
        
        print(f"\n📡 Found {len(ports)} serial ports:")
        for port in ports:
            print(f"  {port.device}: {port.description}")
            
            # Try to identify device type
            desc_lower = port.description.lower()
            if 'usb serial' in desc_lower or 'ftdi' in desc_lower or 'ch340' in desc_lower:
                if 'fingerprint' in desc_lower:
                    detected['fingerprint'].append(port.device)
                else:
                    detected['arduino'].append(port.device)
            elif 'arduino' in desc_lower:
                detected['arduino'].append(port.device)
    
    except ImportError:
        print("[WARN] pyserial not installed. Install with: pip install pyserial")
    except Exception as e:
        print(f"[WARN] Error detecting serial ports: {e}")
    
    # Detect cameras
    try:
        import cv2
        print("\n[CAMERA] Detecting cameras:")
        camera_found = False
        for i in range(5):  # Check first 5 indexes
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    detected['cameras'].append(i)
                    print(f"  Camera {i}: Available")
                    camera_found = True
                cap.release()
        if not camera_found:
            print("  No cameras detected")
    except ImportError:
        print("[WARN] OpenCV not installed. Install with: pip install opencv-python")
    except Exception as e:
        print(f"[WARN] Error detecting cameras: {e}")
    
    # Detect network devices (ping test)
    print("\n🌐 Testing network devices...")
    
    # Test ZKTeco
    zk_ip = os.getenv('ZKTECO_IP', '192.168.1.201')
    response = os.system(f"ping -c 1 -W 1 {zk_ip} > /dev/null 2>&1")
    if response == 0:
        print(f"  [OK] ZKTeco device at {zk_ip} is reachable")
    else:
        print(f"  [ERROR] ZKTeco device at {zk_ip} is not reachable")
    
    # Test Hikvision
    hik_ip = os.getenv('HIKVISION_IP', '192.168.1.100')
    response = os.system(f"ping -c 1 -W 1 {hik_ip} > /dev/null 2>&1")
    if response == 0:
        print(f"  [OK] Hikvision device at {hik_ip} is reachable")
    else:
        print(f"  [ERROR] Hikvision device at {hik_ip} is not reachable")
    
    # Test Suprema
    sup_ip = os.getenv('SUPREMA_IP', '192.168.1.200')
    response = os.system(f"ping -c 1 -W 1 {sup_ip} > /dev/null 2>&1")
    if response == 0:
        print(f"  [OK] Suprema device at {sup_ip} is reachable")
    else:
        print(f"  [ERROR] Suprema device at {sup_ip} is not reachable")
    
    # Generate .env configuration
    if detected['fingerprint'] or detected['arduino'] or detected['cameras']:
        print("\n[OK] Detected hardware. Update your .env file with:")
        
        if detected['fingerprint']:
            print(f"FINGERPRINT_PORT={detected['fingerprint'][0]}")
        
        if detected['arduino']:
            print(f"ARDUINO_PORT={detected['arduino'][0]}")
        
        if detected['cameras']:
            print(f"CAMERA_INDEX={detected['cameras'][0]}")
    
    return detected

# ============================================
# HARDWARE COMMANDS
# ============================================
def hardware_command(args):
    """Handle hardware-related commands."""
    if args.hardware_cmd == 'detect':
        detect_hardware_ports()
    
    elif args.hardware_cmd == 'init':
        initialize_hardware()
    
    elif args.hardware_cmd == 'status':
        show_hardware_status()
    
    elif args.hardware_cmd == 'test':
        test_hardware_component(args.component)
    
    elif args.hardware_cmd == 'list':
        list_available_hardware()

def show_hardware_status():
    """Show status of all hardware devices."""
    print("\n[CHART] Hardware Status:")
    print("-" * 40)
    
    if real_hardware_devices:
        for name, device in real_hardware_devices.items():
            try:
                if hasattr(device, 'is_connected'):
                    connected = device.is_connected()
                elif hasattr(device, 'connected'):
                    connected = device.connected
                else:
                    connected = False
                
                status = "[OK] Connected" if connected else "[ERROR] Disconnected"
                
                # Get additional info
                info = ""
                if hasattr(device, 'model') and device.model:
                    info += f" - {device.model}"
                if hasattr(device, 'serial_number') and device.serial_number:
                    info += f" (SN: {device.serial_number[:8]}...)"
                
                print(f"  {name}: {status}{info}")
            except Exception as e:
                print(f"  {name}: [WARN] Error checking status ({str(e)[:50]})")
    else:
        print("  No hardware initialized. Run: python main.py hardware init")

def test_hardware_component(component: str):
    """Test a specific hardware component."""
    if not component:
        print("[ERROR] Please specify a component to test")
        print("   Available: fingerprint, camera, access_controller, zkteco, hikvision, suprema")
        return
    
    # Initialize hardware if needed
    if not real_hardware_devices and REAL_HARDWARE_AVAILABLE:
        print("Initializing hardware...")
        initialize_hardware()
    
    if component not in real_hardware_devices:
        print(f"[ERROR] Component '{component}' not initialized")
        print(f"   Available: {', '.join(real_hardware_devices.keys()) if real_hardware_devices else 'none'}")
        return
    
    device = real_hardware_devices[component]
    
    print(f"\n[MODE] Testing {component}...")
    print("-" * 40)
    
    if component == 'fingerprint':
        print("\n📱 Fingerprint Scanner Test")
        print("Place finger on scanner when prompted")
        
        for i in range(3):
            input(f"\nPress Enter to scan finger #{i+1}...")
            try:
                result = device.capture_fingerprint()
                if result:
                    print(f"[OK] Fingerprint #{i+1} captured successfully!")
                    print(f"   Quality: {result.get('quality', 'N/A')}/100")
                    print(f"   Template size: {len(result.get('template', b''))} bytes")
                else:
                    print(f"[ERROR] Failed to capture fingerprint #{i+1}")
            except Exception as e:
                print(f"[ERROR] Error: {e}")
    
    elif component == 'camera':
        print("\n[CAMERA] Camera Test")
        
        try:
            # Test capture
            print("Capturing image...")
            frame = device.capture_frame()
            if frame is not None:
                print("[OK] Image captured successfully!")
                print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
                
                # Test face detection if available
                if hasattr(device, 'detect_faces'):
                    faces = device.detect_faces(frame)
                    print(f"   Faces detected: {len(faces)}")
                
                # Save test image
                try:
                    import cv2
                    test_file = f"data/captures/camera_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    os.makedirs('data/captures', exist_ok=True)
                    cv2.imwrite(test_file, frame)
                    print(f"   Test image saved: {test_file}")
                except:
                    print("   Could not save test image")
            else:
                print("[ERROR] Failed to capture image")
        except Exception as e:
            print(f"[ERROR] Error: {e}")
    
    elif component == 'access_controller':
        print("\n[LOCK] Access Controller Test")
        
        try:
            # Test relay
            print("Testing door relay (3 seconds)...")
            if device.open_door(3):
                print("[OK] Door opened successfully")
                time.sleep(3)
                print("   Door closed")
            else:
                print("[ERROR] Failed to open door")
            
            # Test status if available
            if hasattr(device, 'get_status'):
                status = device.get_status()
                print(f"   Controller status: {status}")
        except Exception as e:
            print(f"[ERROR] Error: {e}")
    
    elif component == 'zkteco':
        print("\n[DEVICE] ZKTeco Device Test")
        
        try:
            # Get device info
            if hasattr(device, 'get_device_status'):
                status = device.get_device_status()
                print(f"Model: {status.get('model', 'Unknown')}")
                print(f"Serial: {status.get('serial', 'Unknown')}")
                print(f"Firmware: {status.get('firmware', 'Unknown')}")
                print(f"Users: {status.get('user_count', 0)}")
                print(f"Fingerprints: {status.get('fingerprint_count', 0)}")
                print(f"Logs: {status.get('log_count', 0)}")
            else:
                print(f"Model: {getattr(device, 'model', 'Unknown')}")
                print(f"Serial: {getattr(device, 'serial_number', 'Unknown')}")
            
            # Test getting users
            print("\nFetching users...")
            users = device.get_users()
            print(f"[OK] Retrieved {len(users)} users")
            
            if users:
                print("\nSample users:")
                for user in users[:3]:
                    name = user.get('name', user.get('Name', 'Unknown'))
                    uid = user.get('user_id', user.get('UID', 'N/A'))
                    print(f"  - {name} (ID: {uid})")
            
            # Test door if available
            if hasattr(device, 'open_door'):
                print("\nTesting door open...")
                if device.open_door():
                    print("[OK] Door opened successfully")
                else:
                    print("[ERROR] Failed to open door")
        except Exception as e:
            print(f"[ERROR] Error: {e}")
    
    elif component == 'hikvision':
        print("\n[CAMERA] Hikvision Device Test")
        
        try:
            # Get device info
            print(f"Model: {getattr(device, 'model', 'Unknown')}")
            print(f"Serial: {getattr(device, 'serial_number', 'Unknown')}")
            print(f"Firmware: {getattr(device, 'firmware_version', 'Unknown')}")
            print(f"Doors: {getattr(device, 'door_count', 0)}")
            print(f"Cards: {getattr(device, 'card_count', 0)}")
            
            # Test getting users
            print("\nFetching users...")
            users = device.get_users()
            print(f"[OK] Retrieved {len(users)} users")
            
            if users:
                print("\nSample users:")
                for user in users[:3]:
                    name = user.get('name', 'Unknown')
                    card = user.get('card_id', 'N/A')
                    print(f"  - {name} (Card: {card})")
            
            # Test door
            if hasattr(device, 'open_door'):
                print("\nTesting door open...")
                if device.open_door(door_id=1):
                    print("[OK] Door opened successfully")
                else:
                    print("[ERROR] Failed to open door")
            
            # Test events
            if hasattr(device, 'get_events'):
                print("\nFetching recent events...")
                events = device.get_events(
                    start_time=datetime.now() - timedelta(hours=24),
                    end_time=datetime.now()
                )
                print(f"[OK] Retrieved {len(events)} events in last 24 hours")
        except Exception as e:
            print(f"[ERROR] Error: {e}")
    
    elif component == 'suprema':
        print("\n[SECURE] Suprema Device Test")
        
        try:
            # Get device info
            if hasattr(device, 'get_device_status'):
                status = device.get_device_status()
                print(f"Model: {status.get('model', 'Unknown')}")
                print(f"Serial: {status.get('serial', 'Unknown')}")
                print(f"Firmware: {status.get('firmware', 'Unknown')}")
                print(f"Doors: {status.get('door_count', 0)}")
                print(f"Users: {status.get('user_count', 0)}")
            else:
                print(f"Model: {getattr(device, 'model', 'Unknown')}")
                print(f"Serial: {getattr(device, 'serial_number', 'Unknown')}")
            
            # Test getting users
            print("\nFetching users...")
            users = device.get_users(limit=10)
            print(f"[OK] Retrieved {len(users)} users")
            
            if users:
                print("\nSample users:")
                for user in users[:3]:
                    name = user.get('name', 'Unknown')
                    uid = user.get('user_id', 'N/A')
                    print(f"  - {name} (ID: {uid})")
            
            # Test door
            if hasattr(device, 'open_door'):
                print("\nTesting door open...")
                if device.open_door(door_id=1):
                    print("[OK] Door opened successfully")
                else:
                    print("[ERROR] Failed to open door")
            
            # Test events
            if hasattr(device, 'get_events'):
                print("\nFetching recent events...")
                events = device.get_events(
                    start_time=datetime.now() - timedelta(hours=24),
                    end_time=datetime.now(),
                    limit=10
                )
                print(f"[OK] Retrieved {len(events)} events")
        except Exception as e:
            print(f"[ERROR] Error: {e}")

def list_available_hardware():
    """List all available hardware drivers."""
    print("\n📋 Available Hardware Drivers:")
    print("-" * 40)
    
    hardware_list = [
        ("Fingerprint Scanner", "R307/R503/ZFM60", "/dev/ttyUSB0 or COM3", "fingerprint"),
        ("Facial Camera", "USB Camera/Webcam", "Camera index 0", "camera"),
        ("Access Controller", "Arduino/Relay", "/dev/ttyUSB1 or COM4", "access_controller"),
        ("ZKTeco Device", "IN01/IN02/K40/F18", "192.168.1.201:4370", "zkteco"),
        ("Hikvision Device", "DS-K Series", "192.168.1.100:80", "hikvision"),
        ("Suprema Device", "BioEntry/FaceStation", "192.168.1.200:443", "suprema")
    ]
    
    for name, model, default, component in hardware_list:
        print(f"\n📱 {name}")
        print(f"   Models: {model}")
        print(f"   Default: {default}")
        print(f"   Test: python main.py hardware test --component {component}")

# ============================================
# MAIN APPLICATION
# ============================================
def main():
    """Main application entry point."""
    # Load environment variables
    load_environment()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Biometric Student Access Control System')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Hardware commands
    hardware_parser = subparsers.add_parser('hardware', help='Hardware management')
    hardware_parser.add_argument('hardware_cmd', choices=['detect', 'init', 'status', 'test', 'list'])
    hardware_parser.add_argument('--component', help='Component to test')
    
    # Enrollment command
    enroll_parser = subparsers.add_parser('enroll', help='Enroll a new student')
    enroll_parser.add_argument('--student-id', help='Student ID')
    enroll_parser.add_argument('--method', choices=['fingerprint', 'facial', 'both'], default='both')
    
    # Verification command
    verify_parser = subparsers.add_parser('verify', help='Verify access')
    verify_parser.add_argument('--method', choices=['fingerprint', 'facial', 'any'], default='any')
    
    # Admin command
    subparsers.add_parser('admin', help='Start admin web interface')
    
    # Database commands
    db_parser = subparsers.add_parser('db', help='Database management')
    db_parser.add_argument('db_cmd', choices=['init', 'backup', 'status', 'test'])
    
    # Test command
    subparsers.add_parser('test', help='Run system tests')
    
    # Initialize command
    subparsers.add_parser('init', help='Initialize system')
    
    args = parser.parse_args()
    
    # Initialize system directories
    initialize_directories()
    
    # Handle commands
    if args.command == 'hardware':
        hardware_command(args)
    
    elif args.command == 'enroll':
        start_enrollment(args)
    
    elif args.command == 'verify':
        start_verification(args)
    
    elif args.command == 'admin':
        start_admin_panel()
    
    elif args.command == 'db':
        handle_database_command(args)
    
    elif args.command == 'test':
        run_tests()
    
    elif args.command == 'init':
        initialize_system()
    
    else:
        # No command specified, start interactive mode
        start_interactive_mode()

def initialize_directories():
    """Create necessary directories."""
    dirs = [
        'data/templates',
        'data/templates/fingerprint',
        'data/templates/facial',
        'data/logs',
        'data/backups',
        'data/captures',
        'data/exports'
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

def start_enrollment(args):
    """Start student enrollment process."""
    print("\n[MENU] Student Enrollment")
    print("=" * 40)
    
    # Initialize hardware if needed
    if not real_hardware_devices and REAL_HARDWARE_AVAILABLE:
        print("Initializing hardware...")
        initialize_hardware()
    
    try:
        # Import here to avoid circular imports
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        
        # SIMPLE FIX: The EnrollmentManager only takes simulation_mode parameter
        # Set simulation_mode to False since we're using real hardware
        from src.enrollment.enroll_student import EnrollmentManager
        
        # Create manager with simulation_mode=False for real hardware
        manager = EnrollmentManager(simulation_mode=False)
        
        # The manager will internally use the hardware devices
        # We don't need to pass the hardware_devices dictionary
        
        if args.student_id:
            # Direct enrollment with provided ID
            if hasattr(manager, 'enroll_student'):
                manager.enroll_student(args.student_id, args.method)
            else:
                print("[ERROR] Enrollment method not available")
        else:
            # Interactive enrollment
            if hasattr(manager, 'interactive_enrollment'):
                manager.interactive_enrollment()
            else:
                print("[ERROR] Interactive enrollment not available")
            
    except ImportError as e:
        logger.error(f"Enrollment module error: {e}")
        print("[ERROR] Enrollment module not available")
        print("   Make sure the enrollment module is properly installed")
    except Exception as e:
        logger.error(f"Enrollment error: {e}")
        print(f"[ERROR] Enrollment failed: {e}")

def start_verification(args):
    """Start access verification process."""
    print("\n[SECURE] Access Verification")
    print("=" * 40)
    
    # Initialize hardware if needed
    if not real_hardware_devices and REAL_HARDWARE_AVAILABLE:
        print("Initializing hardware...")
        initialize_hardware()
    
    try:
        # Import here to avoid circular imports
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        
        # SIMPLE FIX: The VerificationManager only takes simulation_mode parameter
        # Set simulation_mode to False since we're using real hardware
        from src.verification.verify_access import VerificationManager
        
        # Create manager with simulation_mode=False for real hardware
        manager = VerificationManager(simulation_mode=False)
        
        # The manager will internally use the hardware devices
        # We don't need to pass the hardware_devices dictionary
        
        if args.method == 'fingerprint' and 'fingerprint' in real_hardware_devices:
            if hasattr(manager, 'verify_fingerprint'):
                manager.verify_fingerprint()
            else:
                print("[ERROR] Fingerprint verification not available")
        elif args.method == 'facial' and 'camera' in real_hardware_devices:
            if hasattr(manager, 'verify_facial'):
                manager.verify_facial()
            else:
                print("[ERROR] Facial verification not available")
        else:
            # Try any available method
            if hasattr(manager, 'verify_any'):
                manager.verify_any()
            else:
                print("[ERROR] Verification method not available")
            
    except ImportError as e:
        logger.error(f"Verification module error: {e}")
        print("[ERROR] Verification module not available")
        print("   Make sure the verification module is properly installed")
    except Exception as e:
        logger.error(f"Verification error: {e}")
        print(f"[ERROR] Verification failed: {e}")

def start_admin_panel():
    """Start the admin web interface."""
    print("\n🌐 Starting Admin Panel")
    print("=" * 40)
    print("Access at: http://localhost:5000")
    print("Default login: admin / Admin@123")
    
    try:
        # Import here to avoid circular imports
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        from src.admin.app import app
        app.run(host='0.0.0.0', port=5000, debug=os.getenv('APP_DEBUG', 'False').lower() == 'true')
    except ImportError as e:
        logger.error(f"Admin panel error: {e}")
        print("[ERROR] Admin panel not available")
        print("   Install Flask: pip install flask flask-login flask-wtf")
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        print(f"[ERROR] Failed to start admin panel: {e}")

def handle_database_command(args):
    """Handle database commands."""
    if args.db_cmd == 'init':
        initialize_database()
    elif args.db_cmd == 'backup':
        backup_database()
    elif args.db_cmd == 'status':
        database_status()
    elif args.db_cmd == 'test':
        test_database()

def initialize_database():
    """Initialize database with tables."""
    print("\n📦 Initializing Database")
    print("=" * 40)
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        from src.database.connection import DatabaseConnection, execute_query
        
        db = DatabaseConnection()
        if not db.connect():
            print("[ERROR] Cannot connect to database")
            print("   Please check your database configuration in .env file")
            return
        
        # Create tables
        print("Creating tables...")
        
        # Students table
        execute_query("""
            CREATE TABLE IF NOT EXISTS students (
                student_id VARCHAR(50) PRIMARY KEY,
                registration_number VARCHAR(50) UNIQUE NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                phone VARCHAR(20),
                course VARCHAR(100),
                year_of_study INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        print("[OK] Students table created")
        
        # Biometric templates table
        execute_query("""
            CREATE TABLE IF NOT EXISTS biometric_templates (
                template_id SERIAL PRIMARY KEY,
                student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
                template_type VARCHAR(20) CHECK (template_type IN ('fingerprint', 'facial')),
                template_data BYTEA NOT NULL,
                template_hash VARCHAR(64) NOT NULL,
                quality_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, template_type)
            )
        """)
        print("[OK] Biometric templates table created")
        
        # Access logs table
        execute_query("""
            CREATE TABLE IF NOT EXISTS access_logs (
                log_id SERIAL PRIMARY KEY,
                student_id VARCHAR(50) REFERENCES students(student_id),
                access_point VARCHAR(50),
                verification_method VARCHAR(20),
                verification_result VARCHAR(20),
                match_score FLOAT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("[OK] Access logs table created")
        
        # Administrators table
        execute_query("""
            CREATE TABLE IF NOT EXISTS administrators (
                admin_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                role VARCHAR(20) DEFAULT 'operator',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        print("[OK] Administrators table created")
        
        # Devices table
        execute_query("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id VARCHAR(100) PRIMARY KEY,
                device_name VARCHAR(100) NOT NULL,
                device_type VARCHAR(50) NOT NULL,
                ip_address VARCHAR(45),
                port INTEGER,
                username VARCHAR(50),
                password VARCHAR(255),
                location VARCHAR(100),
                status VARCHAR(20) DEFAULT 'offline',
                last_seen TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        print("[OK] Devices table created")
        
        print("\n[OK] Database initialization complete!")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        print(f"\n[ERROR] Database initialization failed: {e}")

def database_status():
    """Show database status."""
    print("\n[CHART] Database Status")
    print("=" * 40)
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        from src.database.connection import execute_query
        
        # Check connection
        result = execute_query("SELECT 1")
        if result:
            print("[OK] Database connection: OK")
        else:
            print("[ERROR] Database connection: Failed")
            return
        
        # Get table counts
        tables = [
            ('students', 'Students'),
            ('biometric_templates', 'Templates'),
            ('access_logs', 'Access Logs'),
            ('administrators', 'Admins'),
            ('devices', 'Devices')
        ]
        
        for table, display in tables:
            result = execute_query(f"SELECT COUNT(*) FROM {table}")
            count = result[0][0] if result and result[0] else 0
            print(f"  {display}: {count}")
        
        # Get database size (PostgreSQL specific)
        try:
            size_result = execute_query("SELECT pg_database_size(current_database())")
            if size_result and size_result[0]:
                size_mb = size_result[0][0] / (1024 * 1024)
                print(f"\n📁 Database size: {size_mb:.2f} MB")
        except:
            pass
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

def test_database():
    """Test database connection."""
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
        from src.database.connection import test_connection
        
        if test_connection():
            print("[OK] Database connection successful")
        else:
            print("[ERROR] Database connection failed")
    except ImportError:
        print("[ERROR] Database module not available")
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")

def backup_database():
    """Backup database."""
    print("\n💾 Database Backup")
    print("=" * 40)
    
    backup_dir = 'data/backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
    
    try:
        db_name = os.getenv('DB_NAME', 'biometric_access_db')
        db_user = os.getenv('DB_USER', 'postgres')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_password = os.getenv('DB_PASSWORD', '')
        
        # Check if pg_dump is available
        import subprocess
        result = subprocess.run(['pg_dump', '--version'], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Creating backup: {backup_file}")
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '-U', db_user,
                '-h', db_host,
                '-p', db_port,
                '-F', 'c',  # Custom format
                '-f', backup_file,
                db_name
            ]
            
            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                file_size = os.path.getsize(backup_file) / (1024 * 1024)
                print(f"[OK] Backup created: {backup_file}")
                print(f"   Size: {file_size:.2f} MB")
            else:
                print(f"[ERROR] Backup failed: {result.stderr}")
        else:
            print("[WARN] pg_dump not available - creating simulated backup")
            # Create a simulated backup file
            with open(backup_file, 'w') as f:
                f.write(f"-- Simulated backup for {db_name}\n")
                f.write(f"-- Generated at {timestamp}\n")
            print(f"[OK] Simulation backup created: {backup_file}")
            
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")

def run_tests():
    """Run system tests."""
    print("\n🧪 Running System Tests")
    print("=" * 40)
    
    try:
        import pytest
        result = pytest.main(['tests/', '-v', '--tb=short'])
        
        if result == 0:
            print("\n[OK] All tests passed!")
        else:
            print("\n[ERROR] Some tests failed")
            
    except ImportError:
        print("[ERROR] pytest not installed. Run: pip install pytest")
    except Exception as e:
        print(f"[ERROR] Tests failed: {e}")

def initialize_system():
    """Initialize the entire system."""
    print("\n🚀 Initializing System")
    print("=" * 40)
    
    # Create directories
    initialize_directories()
    print("[OK] Directories created")
    
    # Initialize database
    initialize_database()
    
    # Create default .env if needed
    if not os.path.exists('.env'):
        create_default_env()
    
    # Detect hardware
    if REAL_HARDWARE_AVAILABLE:
        print("\n[INFO] Detecting hardware...")
        detect_hardware_ports()
        
        # Initialize hardware
        initialize_hardware()
    
    print("\n[OK] System initialization complete!")

def start_interactive_mode():
    """Start interactive console mode."""
    print("\n" + "="*60)
    print("BIOMETRIC STUDENT ACCESS CONTROL SYSTEM")
    print("Kibabii University - Group Three")
    print("="*60)
    
    if REAL_HARDWARE_AVAILABLE:
        print("\n[MODE] Hardware Mode: REAL DEVICES")
        if real_hardware_devices:
            print(f"   Active Devices: {', '.join(real_hardware_devices.keys())}")
    else:
        print("\n[SCREEN]  Hardware Mode: SIMULATION")
    
    while True:
        print("\nMain Menu:")
        print("1. Student Enrollment")
        print("2. Access Verification")
        print("3. Admin Dashboard")
        print("4. Hardware Management")
        print("5. Database Management")
        print("6. System Information")
        print("7. Exit")
        
        choice = input("\nSelect option (1-7): ").strip()
        
        if choice == '1':
            start_enrollment(argparse.Namespace(student_id=None, method='both'))
        elif choice == '2':
            start_verification(argparse.Namespace(method='any'))
        elif choice == '3':
            start_admin_panel()
        elif choice == '4':
            hardware_menu()
        elif choice == '5':
            database_menu()
        elif choice == '6':
            system_info()
        elif choice == '7':
            print("\n👋 Goodbye!")
            break
        else:
            print("[ERROR] Invalid option")

def hardware_menu():
    """Hardware management menu."""
    while True:
        print("\n[MODE] Hardware Management:")
        print("1. Initialize Hardware")
        print("2. Show Hardware Status")
        print("3. Test Hardware")
        print("4. Detect Hardware Ports")
        print("5. List Available Hardware")
        print("6. Return to Main Menu")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            initialize_hardware()
        elif choice == '2':
            show_hardware_status()
        elif choice == '3':
            print("\nAvailable components:")
            if real_hardware_devices:
                for comp in real_hardware_devices.keys():
                    print(f"  - {comp}")
            else:
                print("  fingerprint, camera, access_controller, zkteco, hikvision, suprema")
            
            test_component = input("\nEnter component to test: ").strip()
            test_hardware_component(test_component)
        elif choice == '4':
            detect_hardware_ports()
        elif choice == '5':
            list_available_hardware()
        elif choice == '6':
            break
        else:
            print("[ERROR] Invalid option")

def database_menu():
    """Database management menu."""
    while True:
        print("\n[CHART] Database Management:")
        print("1. Initialize Database")
        print("2. Show Database Status")
        print("3. Backup Database")
        print("4. Test Connection")
        print("5. Return to Main Menu")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '1':
            initialize_database()
        elif choice == '2':
            database_status()
        elif choice == '3':
            backup_database()
        elif choice == '4':
            test_database()
        elif choice == '5':
            break
        else:
            print("[ERROR] Invalid option")

def system_info():
    """Display system information."""
    print("\nℹ️  System Information")
    print("=" * 40)
    
    print(f"Python Version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Current Directory: {os.getcwd()}")
    
    print("\n📁 Directories:")
    for dir_path in ['data/templates', 'data/logs', 'data/backups', 'data/captures']:
        exists = os.path.exists(dir_path)
        status = "[OK]" if exists else "[ERROR]"
        print(f"  {status} {dir_path}")
    
    print("\n[MODE] Hardware Status:")
    if REAL_HARDWARE_AVAILABLE:
        print(f"  Hardware Drivers: [OK] Loaded")
        print(f"  Active Devices: {len(real_hardware_devices)}")
        for device_name, device in real_hardware_devices.items():
            try:
                if hasattr(device, 'connected') and device.connected:
                    status = "[OK] Connected"
                elif hasattr(device, 'is_connected') and device.is_connected():
                    status = "[OK] Connected"
                else:
                    status = "[ERROR] Disconnected"
                print(f"    - {device_name}: {status}")
            except:
                print(f"    - {device_name}: [WARN] Unknown")
    else:
        print("  Hardware Drivers: [ERROR] Not Available")
    
    print("\n📦 Database:")
    test_database()
    
    print("\n[GEAR] Environment:")
    print(f"  APP_ENV: {os.getenv('APP_ENV', 'development')}")
    print(f"  APP_DEBUG: {os.getenv('APP_DEBUG', 'False')}")
    print(f"  DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
    print(f"  DB_NAME: {os.getenv('DB_NAME', 'biometric_access_db')}")
    
    # Show hardware config
    print("\n🔌 Hardware Configuration:")
    print(f"  Fingerprint Port: {os.getenv('FINGERPRINT_PORT', '/dev/ttyUSB0')}")
    print(f"  Camera Index: {os.getenv('CAMERA_INDEX', '0')}")
    print(f"  Arduino Port: {os.getenv('ARDUINO_PORT', '/dev/ttyUSB1')}")
    print(f"  ZKTeco IP: {os.getenv('ZKTECO_IP', '192.168.1.201')}:{os.getenv('ZKTECO_PORT', '4370')}")
    print(f"  Hikvision IP: {os.getenv('HIKVISION_IP', '192.168.1.100')}:{os.getenv('HIKVISION_PORT', '80')}")
    print(f"  Suprema IP: {os.getenv('SUPREMA_IP', '192.168.1.200')}:{os.getenv('SUPREMA_PORT', '443')}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 System shutdown requested")
        logger.info("System shutdown by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n[ERROR] Unexpected error: {e}")
    finally:
        # Cleanup hardware connections
        if real_hardware_devices:
            print("\nCleaning up hardware connections...")
            for name, device in real_hardware_devices.items():
                try:
                    if hasattr(device, 'disconnect'):
                        device.disconnect()
                        print(f"  [OK] {name} disconnected")
                    elif hasattr(device, 'close'):
                        device.close()
                        print(f"  [OK] {name} closed")
                except Exception as e:
                    print(f"  [ERROR] Error disconnecting {name}: {e}")
        print("\nSystem shutdown complete")