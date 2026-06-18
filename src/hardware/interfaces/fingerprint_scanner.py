"""
Fingerprint scanner interface for various manufacturers
"""
import serial
import time
import struct
import logging
from typing import Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseFingerprintScanner(ABC):
    """Abstract base class for fingerprint scanners"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the scanner"""
        pass
    
    @abstractmethod
    def scan_fingerprint(self, timeout: int = 5) -> Optional[Tuple[str, float]]:
        """Scan fingerprint and return (user_id, confidence)"""
        pass
    
    @abstractmethod
    def capture_template(self) -> Optional[bytes]:
        """Capture fingerprint template for enrollment"""
        pass
    
    @abstractmethod
    def verify_fingerprint(self, template: bytes) -> Tuple[bool, float]:
        """Verify fingerprint against template"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if scanner is connected"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from scanner"""
        pass


class ZKTecoFingerprintScanner(BaseFingerprintScanner):
    """Interface for ZKTeco fingerprint scanners"""
    
    # ZKTeco command codes
    CMD_CONNECT = 0x01
    CMD_DISCONNECT = 0x02
    CMD_SCAN_FINGER = 0x03
    CMD_GET_TEMPLATE = 0x04
    CMD_VERIFY = 0x05
    CMD_ENROLL = 0x06
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get("device_id", "scanner_1")
        self.port = config.get("port", "/dev/ttyUSB0")
        self.baudrate = config.get("baudrate", 9600)
        self.timeout = config.get("timeout", 5)
        self.serial_conn = None
        self.is_initialized = False
        self.last_scan_time = None
        self.scan_count = 0
        
        logger.info(f"Initializing ZKTeco scanner {self.device_id} on {self.port}")
    
    def initialize(self) -> bool:
        """Initialize serial connection to scanner"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            
            # Send connect command
            connect_packet = self._create_packet(self.CMD_CONNECT)
            self.serial_conn.write(connect_packet)
            response = self.serial_conn.read(8)  # Response header
            
            if response and len(response) >= 8:
                self.is_initialized = True
                logger.info(f"ZKTeco scanner {self.device_id} connected successfully")
                return True
            
        except Exception as e:
            logger.error(f"Failed to initialize ZKTeco scanner: {e}")
        
        return False
    
    def scan_fingerprint(self, timeout: int = 5) -> Optional[Tuple[str, float]]:
        """Scan fingerprint and identify user"""
        if not self.is_connected():
            logger.error("Scanner not connected")
            return None
        
        try:
            # Send scan command
            scan_packet = self._create_packet(self.CMD_SCAN_FINGER)
            self.serial_conn.write(scan_packet)
            
            # Wait for fingerprint scan
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.read(32)  # Response contains user ID and score
                    
                    if len(response) >= 32:
                        # Parse response: first 4 bytes = user ID, next 4 bytes = confidence score
                        user_id_bytes = response[0:4]
                        score_bytes = response[4:8]
                        
                        user_id = struct.unpack('I', user_id_bytes)[0]
                        confidence = struct.unpack('I', score_bytes)[0] / 100.0  # Convert to percentage
                        
                        if user_id > 0:  # Valid user ID
                            self.last_scan_time = time.time()
                            self.scan_count += 1
                            
                            logger.info(f"Fingerprint scan successful: User {user_id}, Confidence: {confidence}%")
                            return (str(user_id), confidence)
                
                time.sleep(0.1)
            
            logger.debug("No fingerprint detected within timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error scanning fingerprint: {e}")
            return None
    
    def capture_template(self) -> Optional[bytes]:
        """Capture fingerprint template for enrollment"""
        if not self.is_connected():
            return None
        
        try:
            # Send template capture command
            template_packet = self._create_packet(self.CMD_GET_TEMPLATE)
            self.serial_conn.write(template_packet)
            
            # Read template data (typically 512 bytes for ZKTeco)
            response = self.serial_conn.read(520)  # 512 + 8 byte header
            
            if len(response) >= 520:
                template_data = response[8:520]  # Skip header
                return template_data
        
        except Exception as e:
            logger.error(f"Error capturing template: {e}")
        
        return None
    
    def verify_fingerprint(self, template: bytes) -> Tuple[bool, float]:
        """Verify fingerprint against stored template"""
        if not self.is_connected() or not template:
            return False, 0.0
        
        try:
            # Send verification command with template
            verify_packet = self._create_verify_packet(template)
            self.serial_conn.write(verify_packet)
            
            response = self.serial_conn.read(12)  # Response for verification
            
            if len(response) >= 12:
                result = struct.unpack('I', response[4:8])[0]
                score = struct.unpack('I', response[8:12])[0] / 100.0
                
                return (result == 1, score)
        
        except Exception as e:
            logger.error(f"Error verifying fingerprint: {e}")
        
        return False, 0.0
    
    def enroll_fingerprint(self, user_id: int) -> bool:
        """Enroll new fingerprint for user"""
        if not self.is_connected():
            return False
        
        try:
            # Start enrollment process
            enroll_packet = self._create_enroll_packet(user_id)
            self.serial_conn.write(enroll_packet)
            
            # Wait for user to place finger (3 times for enrollment)
            for i in range(3):
                logger.info(f"Enrollment step {i+1}/3: Please place finger")
                
                response = self.serial_conn.read(8, timeout=30)
                if not response:
                    logger.error("Enrollment timeout")
                    return False
            
            # Finalize enrollment
            finalize_packet = self._create_packet(0x07)  # CMD_FINALIZE_ENROLL
            self.serial_conn.write(finalize_packet)
            
            response = self.serial_conn.read(8)
            if response and len(response) >= 8:
                return response[4] == 0x01  # Success flag
        
        except Exception as e:
            logger.error(f"Error enrolling fingerprint: {e}")
        
        return False
    
    def is_connected(self) -> bool:
        """Check if scanner is connected"""
        return self.is_initialized and self.serial_conn and self.serial_conn.is_open
    
    def disconnect(self):
        """Disconnect from scanner"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                disconnect_packet = self._create_packet(self.CMD_DISCONNECT)
                self.serial_conn.write(disconnect_packet)
                time.sleep(0.1)
                self.serial_conn.close()
            
            self.is_initialized = False
            logger.info(f"Scanner {self.device_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting scanner: {e}")
    
    def _create_packet(self, command: int, data: bytes = b'') -> bytes:
        """Create ZKTeco protocol packet"""
        # Packet structure: [START(0xAA), COMMAND, LENGTH_HIGH, LENGTH_LOW, DATA..., CHECKSUM]
        length = len(data)
        packet = bytearray([0xAA, command, (length >> 8) & 0xFF, length & 0xFF])
        packet.extend(data)
        
        # Calculate checksum
        checksum = sum(packet) & 0xFF
        packet.append(checksum)
        
        return bytes(packet)
    
    def _create_verify_packet(self, template: bytes) -> bytes:
        """Create verification packet with template data"""
        return self._create_packet(self.CMD_VERIFY, template)
    
    def _create_enroll_packet(self, user_id: int) -> bytes:
        """Create enrollment packet with user ID"""
        user_id_bytes = struct.pack('I', user_id)
        return self._create_packet(self.CMD_ENROLL, user_id_bytes)


class SupremaFingerprintScanner(BaseFingerprintScanner):
    """Interface for Suprema fingerprint scanners"""
    # Implementation similar to ZKTeco but with Suprema-specific protocol
    pass


# Factory function to create appropriate scanner
def create_fingerprint_scanner(config: Dict[str, Any]) -> BaseFingerprintScanner:
    """Factory function to create appropriate scanner instance"""
    scanner_type = config.get("type", "zkteco").lower()
    
    if scanner_type == "zkteco":
        return ZKTecoFingerprintScanner(config)
    elif scanner_type == "suprema":
        return SupremaFingerprintScanner(config)
    else:
        raise ValueError(f"Unsupported scanner type: {scanner_type}")


# Alias for backward compatibility
FingerprintScanner = create_fingerprint_scanner