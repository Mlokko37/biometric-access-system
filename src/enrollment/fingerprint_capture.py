import os
import sys
import logging
import time
import serial
import struct
from typing import Optional, Dict, Any, List, Tuple
import hashlib
from datetime import datetime

# Add missing imports
import numpy as np

logger = logging.getLogger(__name__)

class FingerprintCapture:
    """Handles fingerprint capture from R307/R503/ZFM60 sensors."""
    
    # Command codes for fingerprint sensor
    CMD_GET_IMAGE = 0x01
    CMD_IMAGE_2_TZ = 0x02
    CMD_SEARCH = 0x04
    CMD_REGMODEL = 0x05
    CMD_STORE = 0x06
    CMD_LOAD = 0x07
    CMD_UPLOAD = 0x08
    CMD_DOWNLOAD = 0x09
    CMD_UPLOAD_IMAGE = 0x0A
    CMD_DOWNLOAD_IMAGE = 0x0B
    CMD_DELETE = 0x0C
    CMD_EMPTY = 0x0D
    CMD_SET_SYSPARAM = 0x0E
    CMD_GET_SYSPARAM = 0x0F
    CMD_SET_PASSWORD = 0x12
    CMD_VERIFY_PASSWORD = 0x13
    CMD_GET_RANDOM_CODE = 0x14
    CMD_SET_ADDRESS = 0x15
    CMD_READ_INFO = 0x16
    CMD_SLEEP = 0x17
    CMD_GET_ENROLL_COUNT = 0x20
    CMD_CHECK_ENROLLED = 0x21
    CMD_ENROLL_START = 0x22
    CMD_ENROLL_1 = 0x23
    CMD_ENROLL_2 = 0x24
    CMD_ENROLL_3 = 0x25
    
    # Confirmation codes
    CONF_SUCCESS = 0x00
    CONF_FAIL = 0x01
    CONF_FULL = 0x04
    CONF_NO_USER = 0x05
    CONF_USER_OCCUPIED = 0x06
    CONF_USER_EXISTS = 0x07
    CONF_ALREADY_EXISTS = 0x08
    CONF_BAD_QUALITY = 0x09
    CONF_MERGE_FAIL = 0x0A
    CONF_FINGER_NOT_PRESSED = 0x0D
    CONF_FINGER_NOT_REMOVED = 0x0E
    CONF_COMM_ERR = 0x0F
    CONF_TIMEOUT = 0x10
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 57600, 
                 address: int = 0xFFFFFFFF, password: int = 0x00000000,
                 simulation_mode: bool = False):
        """Initialize fingerprint sensor."""
        self.port = port or os.getenv('FINGERPRINT_PORT', '/dev/ttyUSB0')
        self.baudrate = baudrate
        self.address = address
        self.password = password
        self.simulation_mode = simulation_mode
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        
        if not simulation_mode:
            self.connect()
    
    def connect(self) -> bool:
        """Connect to fingerprint sensor."""
        try:
            # Check if port is provided
            if not self.port:
                logger.error("No serial port specified")
                return False
            
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2
            )
            
            # Verify password
            if self.verify_password():
                self.connected = True
                logger.info(f"Fingerprint sensor connected on {self.port}")
                
                # Get sensor info
                info = self.get_sensor_info()
                logger.info(f"Sensor info: {info}")
                return True
            else:
                logger.error("Password verification failed")
                if self.serial:
                    self.serial.close()
                    self.serial = None
                return False
                
        except serial.SerialException as e:
            logger.error(f"Serial connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to fingerprint sensor: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from sensor."""
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
        self.connected = False
        logger.info("Fingerprint sensor disconnected")
    
    def send_command(self, cmd: int, data: bytes = b'') -> Tuple[int, bytes]:
        """Send command to sensor and receive response."""
        if self.simulation_mode:
            return self.CONF_SUCCESS, b'\x00' * 64
        
        # Check if serial is connected
        if not self.serial:
            logger.error("Sensor not connected")
            return self.CONF_COMM_ERR, b''
        
        try:
            # Build packet
            packet = struct.pack('>H', self.address >> 16)  # High address
            packet += struct.pack('>H', self.address & 0xFFFF)  # Low address
            packet += bytes([0x01])  # Packet type (command)
            packet += struct.pack('>H', len(data) + 2)  # Length (data + checksum)
            packet += bytes([cmd])  # Command
            packet += data  # Data
            
            # Calculate checksum
            checksum = sum(packet[6:]) & 0xFFFF
            packet += struct.pack('>H', checksum)
            
            # Send packet
            self.serial.write(packet)
            self.serial.flush()
            
            # Read response
            response = self.serial.read(12)  # Header
            if len(response) < 12:
                return (self.CONF_TIMEOUT, b'')
            
            # Parse response
            _, _, _, _, length = struct.unpack('>HHHBB', response[:9])
            data_len = length - 2  # Exclude checksum
            
            # Read data
            data = self.serial.read(data_len + 2)  # +2 for checksum
            if len(data) < data_len + 2:
                return (self.CONF_COMM_ERR, b'')
            
            conf_code = data[0]
            response_data = data[1:data_len]
            
            return (conf_code, response_data)
            
        except Exception as e:
            logger.error(f"Command send error: {e}")
            return (self.CONF_COMM_ERR, b'')
    
    def verify_password(self) -> bool:
        """Verify sensor password."""
        if self.simulation_mode:
            return True
        
        data = struct.pack('>I', self.password)
        conf, _ = self.send_command(self.CMD_VERIFY_PASSWORD, data)
        return conf == self.CONF_SUCCESS
    
    def get_sensor_info(self) -> Dict[str, Any]:
        """Get sensor information."""
        if self.simulation_mode:
            return {
                'module_type': 1,
                'module_bps': self.baudrate,
                'module_serial': 'SIM123456',
                'hardware_version': '1.0',
                'software_version': '1.0',
                'sensor_width': 256,
                'sensor_height': 288,
                'template_size': 512,
                'database_size': 1000,
                'simulated': True
            }
        
        conf, data = self.send_command(self.CMD_READ_INFO)
        
        if conf != self.CONF_SUCCESS or len(data) < 20:
            return {'error': 'Failed to read sensor info'}
        
        # Parse info
        info = {
            'module_type': data[0],
            'module_bps': data[1],
            'module_serial': data[2:6].hex() if len(data) > 5 else '',
            'hardware_version': f"{data[6]}.{data[7]}" if len(data) > 7 else '0.0',
            'software_version': f"{data[8]}.{data[9]}" if len(data) > 9 else '0.0',
            'sensor_width': data[12] * 256 + data[13] if len(data) > 13 else 0,
            'sensor_height': data[14] * 256 + data[15] if len(data) > 15 else 0,
            'template_size': data[16] * 256 + data[17] if len(data) > 17 else 0,
            'database_size': data[18] * 256 + data[19] if len(data) > 19 else 0
        }
        
        return info
    
    def get_image(self) -> bool:
        """Get image from sensor."""
        if self.simulation_mode:
            return True
        
        conf, _ = self.send_command(self.CMD_GET_IMAGE)
        return conf == self.CONF_SUCCESS
    
    def image_to_template(self, buffer_id: int = 1) -> bool:
        """Convert image to template in character buffer."""
        if self.simulation_mode:
            return True
        
        conf, _ = self.send_command(self.CMD_IMAGE_2_TZ, bytes([buffer_id]))
        return conf == self.CONF_SUCCESS
    
    def create_template(self) -> bool:
        """Create template from two character buffers."""
        if self.simulation_mode:
            return True
        
        conf, _ = self.send_command(self.CMD_REGMODEL)
        return conf == self.CONF_SUCCESS
    
    def upload_template(self, buffer_id: int = 2) -> Optional[bytes]:
        """Upload template from sensor."""
        if self.simulation_mode:
            import random
            return bytes([random.randint(0, 255) for _ in range(512)])
        
        conf, data = self.send_command(self.CMD_UPLOAD, bytes([buffer_id]))
        
        if conf == self.CONF_SUCCESS:
            return data
        return None
    
    def download_template(self, template: bytes, buffer_id: int = 2) -> bool:
        """Download template to sensor."""
        if self.simulation_mode:
            return True
        
        conf, _ = self.send_command(self.CMD_DOWNLOAD, bytes([buffer_id]) + template)
        return conf == self.CONF_SUCCESS
    
    def store_template(self, buffer_id: int, page_id: int) -> bool:
        """Store template in flash memory."""
        if self.simulation_mode:
            return True
        
        data = struct.pack('>HH', buffer_id, page_id)
        conf, _ = self.send_command(self.CMD_STORE, data)
        return conf == self.CONF_SUCCESS
    
    def load_template(self, page_id: int, buffer_id: int) -> bool:
        """Load template from flash memory."""
        if self.simulation_mode:
            return True
        
        data = struct.pack('>HH', page_id, buffer_id)
        conf, _ = self.send_command(self.CMD_LOAD, data)
        return conf == self.CONF_SUCCESS
    
    def search_template(self, buffer_id: int = 1) -> Tuple[bool, int, int]:
        """Search for template in database."""
        if self.simulation_mode:
            import random
            return random.random() > 0.3, random.randint(1, 100), random.randint(50, 100)
        
        data = struct.pack('>HH', buffer_id, 0)  # Start from page 0
        conf, response = self.send_command(self.CMD_SEARCH, data)
        
        if conf == self.CONF_SUCCESS and len(response) >= 4:
            page_id = struct.unpack('>H', response[:2])[0]
            score = struct.unpack('>H', response[2:4])[0]
            return True, page_id, score
        
        return False, 0, 0
    
    def delete_template(self, page_id: int, count: int = 1) -> bool:
        """Delete template from database."""
        if self.simulation_mode:
            return True
        
        data = struct.pack('>HH', page_id, count)
        conf, _ = self.send_command(self.CMD_DELETE, data)
        return conf == self.CONF_SUCCESS
    
    def empty_database(self) -> bool:
        """Delete all templates from database."""
        if self.simulation_mode:
            return True
        
        conf, _ = self.send_command(self.CMD_EMPTY)
        return conf == self.CONF_SUCCESS
    
    def get_template_count(self) -> int:
        """Get number of templates in database."""
        if self.simulation_mode:
            return 0
        
        conf, data = self.send_command(self.CMD_GET_ENROLL_COUNT)
        if conf == self.CONF_SUCCESS and len(data) >= 2:
            return struct.unpack('>H', data[:2])[0]
        return 0
    
    def check_enrolled(self, page_id: int) -> bool:
        """Check if template exists at page ID."""
        if self.simulation_mode:
            return False
        
        data = struct.pack('>H', page_id)
        conf, _ = self.send_command(self.CMD_CHECK_ENROLLED, data)
        return conf == self.CONF_SUCCESS
    
    def capture_fingerprint(self, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Capture fingerprint and return template.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Dict with template and metadata or None if failed
        """
        if self.simulation_mode:
            return self._simulate_capture()
        
        if not self.connected:
            logger.error("Sensor not connected")
            return None
        
        try:
            logger.info("Waiting for finger...")
            
            # Wait for finger
            start_time = time.time()
            finger_detected = False
            
            while time.time() - start_time < timeout:
                if self.get_image():
                    finger_detected = True
                    break
                time.sleep(0.1)
            
            if not finger_detected:
                logger.warning("Timeout waiting for finger")
                return None
            
            # Convert image to template
            if not self.image_to_template(1):
                logger.error("Failed to convert image to template")
                return None
            
            # Upload template
            template = self.upload_template(1)
            if not template:
                logger.error("Failed to upload template")
                return None
            
            # Calculate quality (simplified - real quality from sensor)
            quality = self._estimate_quality(template)
            
            # Get template hash
            template_hash = hashlib.sha256(template).hexdigest()
            
            result = {
                'template': template,
                'template_hash': template_hash,
                'quality': float(quality),  # Ensure float return type
                'timestamp': datetime.now().isoformat(),
                'template_size': len(template)
            }
            
            logger.info(f"Fingerprint captured successfully (Quality: {quality:.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"Fingerprint capture error: {e}")
            return None
    
    def enroll_fingerprint(self, enroll_id: Optional[int] = None, 
                          num_samples: int = 3) -> Optional[Dict[str, Any]]:
        """
        Enroll fingerprint with multiple samples.
        
        Args:
            enroll_id: ID to store template (None for temporary)
            num_samples: Number of samples to capture
            
        Returns:
            Dict with enrollment data or None if failed
        """
        if self.simulation_mode:
            return self._simulate_enroll(enroll_id)
        
        if not self.connected:
            logger.error("Sensor not connected")
            return None
        
        try:
            samples = []
            templates = []
            
            print(f"\nFingerprint Enrollment ({num_samples} samples required)")
            print("-" * 40)
            
            for i in range(num_samples):
                print(f"\nSample {i+1}/{num_samples}")
                print("Place finger on sensor...")
                
                # Capture sample
                result = self.capture_fingerprint()
                if not result:
                    print("[ERROR] Capture failed. Please try again.")
                    i -= 1  # Retry
                    continue
                
                samples.append(result)
                templates.append(result['template'])
                
                print(f"[OK] Sample captured (Quality: {result['quality']:.1f}%)")
                
                if i < num_samples - 1:
                    print("Remove finger")
                    time.sleep(1)
            
            # Create combined template if multiple samples
            if num_samples > 1:
                # Download first template to buffer 1
                self.download_template(templates[0], 1)
                
                # Download second template to buffer 2
                self.download_template(templates[1], 2)
                
                # Create merged template
                if not self.create_template():
                    logger.error("Failed to create merged template")
                    return None
                
                # Upload merged template
                final_template = self.upload_template(2)
                if not final_template:
                    logger.error("Failed to upload merged template")
                    return None
            else:
                final_template = templates[0]
            
            # Store in database if enroll_id provided
            if enroll_id is not None:
                if self.store_template(2, enroll_id):
                    logger.info(f"Template stored at ID {enroll_id}")
                else:
                    logger.warning("Failed to store template")
            
            # Calculate average quality
            avg_quality = sum(s['quality'] for s in samples) / len(samples)
            
            result = {
                'template': final_template,
                'template_hash': hashlib.sha256(final_template).hexdigest(),
                'enroll_id': enroll_id,
                'quality': float(avg_quality),  # Ensure float return type
                'samples': samples,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"\n[OK] Enrollment successful!")
            print(f"  Average quality: {avg_quality:.1f}%")
            if enroll_id:
                print(f"  Stored at ID: {enroll_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Fingerprint enrollment error: {e}")
            return None
    
    def verify_fingerprint(self, stored_template: bytes) -> Tuple[bool, float]:
        """
        Verify fingerprint against stored template.
        
        Args:
            stored_template: Previously stored template
            
        Returns:
            Tuple[bool, float]: (match, score)
        """
        if self.simulation_mode:
            return self._simulate_verify(stored_template)
        
        try:
            # Capture live fingerprint
            live = self.capture_fingerprint()
            if not live:
                return False, 0.0
            
            # Download live to buffer 1
            if not self.download_template(live['template'], 1):
                return False, 0.0
            
            # Download stored to buffer 2
            if not self.download_template(stored_template, 2):
                return False, 0.0
            
            # Search for match
            found, page_id, score = self.search_template(1)
            
            if found:
                logger.info(f"Fingerprint verified (Score: {score})")
                return True, float(score)  # Ensure float return type
            
            return False, 0.0
            
        except Exception as e:
            logger.error(f"Fingerprint verification error: {e}")
            return False, 0.0
    
    def _estimate_quality(self, template: bytes) -> float:
        """Estimate fingerprint quality based on template characteristics."""
        if len(template) < 100:
            return 0.0
        
        # Convert to numpy for analysis
        data = np.frombuffer(template, dtype=np.uint8)
        
        # Calculate various quality metrics
        variance = float(np.var(data))
        entropy = float(self._calculate_entropy(data))
        
        # Combined quality score
        quality = min(100.0, variance / 50.0 + entropy * 10.0)
        
        return quality
    
    def _calculate_entropy(self, data: np.ndarray) -> float:
        """Calculate entropy of data."""
        _, counts = np.unique(data, return_counts=True)
        probabilities = counts / len(data)
        entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
        return float(entropy / 8.0)  # Normalize to 0-1
    
    def _simulate_capture(self) -> Dict[str, Any]:
        """Simulate fingerprint capture."""
        import random
        
        time.sleep(0.5)
        
        # Generate simulated template
        template = bytes([random.randint(0, 255) for _ in range(512)])
        quality = float(random.randint(70, 95))  # Ensure float
        
        return {
            'template': template,
            'template_hash': hashlib.sha256(template).hexdigest(),
            'quality': quality,
            'timestamp': datetime.now().isoformat(),
            'template_size': len(template),
            'simulated': True
        }
    
    def _simulate_enroll(self, enroll_id: Optional[int] = None) -> Dict[str, Any]:
        """Simulate fingerprint enrollment."""
        import random
        
        samples = []
        for i in range(3):
            samples.append(self._simulate_capture())
        
        final_template = samples[0]['template']
        avg_quality = sum(s['quality'] for s in samples) / len(samples)
        
        return {
            'template': final_template,
            'template_hash': hashlib.sha256(final_template).hexdigest(),
            'enroll_id': enroll_id,
            'quality': float(avg_quality),  # Ensure float
            'samples': samples,
            'timestamp': datetime.now().isoformat(),
            'simulated': True
        }
    
    def _simulate_verify(self, stored_template: bytes) -> Tuple[bool, float]:
        """Simulate fingerprint verification."""
        import random
        return random.random() > 0.2, float(random.randint(60, 100))
    
    def cleanup(self):
        """Clean up sensor resources."""
        self.disconnect()


def test_fingerprint_capture():
    """Test function for real fingerprint capture."""
    print("Testing Real Fingerprint Capture Module...")
    print("===========================================")
    
    # Try to connect to sensor
    capture = FingerprintCapture(simulation_mode=False)
    
    if not capture.connected:
        print("[ERROR] Sensor not available")
        print("   Using simulation mode for testing")
        capture = FingerprintCapture(simulation_mode=True)
    
    # Get sensor info
    if capture.connected:
        info = capture.get_sensor_info()
        print(f"\nSensor Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        count = capture.get_template_count()
        print(f"\nTemplates in database: {count}")
    
    # Test single capture
    print("\nTesting single capture...")
    input("Press Enter when ready (place finger on sensor)...")
    
    result = capture.capture_fingerprint()
    
    if result:
        print(f"[OK] Fingerprint captured!")
        print(f"  Quality: {result['quality']:.1f}%")
        print(f"  Template size: {result['template_size']} bytes")
        print(f"  Hash: {result['template_hash'][:16]}...")
    else:
        print("[ERROR] Fingerprint capture failed")
    
    # Test enrollment
    print("\nTesting enrollment...")
    input("Press Enter when ready...")
    
    enroll_result = capture.enroll_fingerprint(num_samples=3)
    
    if enroll_result:
        print(f"[OK] Enrollment successful!")
        print(f"  Average quality: {enroll_result['quality']:.1f}%")
        print(f"  Samples: {len(enroll_result['samples'])}")
    else:
        print("[ERROR] Enrollment failed")
    
    capture.cleanup()
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_fingerprint_capture()