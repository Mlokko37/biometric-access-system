"""
Access controller interface (door locks, relays, etc.)
"""

import logging
import time
from typing import Dict, Any, Tuple
from .biometric_interface import BaseBiometricDevice

logger = logging.getLogger(__name__)


class AccessController(BaseBiometricDevice):
    """Access controller for door locks and relays"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.device_id = config.get("device_id", "door_1")
        self.controller_type = config.get("type", "simulated")
        self.gpio_pin = config.get("gpio_pin", 17)
        self.active_low = config.get("active_low", True)
        self.open_duration = config.get("open_duration", 5)  # seconds
        
        self.is_initialized = False
        self.is_open = False
        self.access_count = 0
        self.last_access_time = None
        
        logger.info(f"Initializing access controller {self.device_id}")
    
    def initialize(self) -> bool:
        """Initialize access controller"""
        try:
            if self.controller_type == "gpio":
                # Initialize GPIO for Raspberry Pi
                try:
                    import RPi.GPIO as GPIO
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.gpio_pin, GPIO.OUT)
                    
                    # Set initial state (closed)
                    if self.active_low:
                        GPIO.output(self.gpio_pin, GPIO.HIGH)  # Normally high = closed
                    else:
                        GPIO.output(self.gpio_pin, GPIO.LOW)   # Normally low = closed
                    
                    self.is_initialized = True
                    logger.info(f"GPIO controller {self.device_id} initialized on pin {self.gpio_pin}")
                    
                except ImportError:
                    logger.warning("RPi.GPIO not available, running in simulated mode")
                    self.controller_type = "simulated"
                    self.is_initialized = True
            
            elif self.controller_type == "serial":
                # Initialize serial controller
                try:
                    import serial
                    port = self.config.get("port", "/dev/ttyUSB0")
                    baudrate = self.config.get("baudrate", 9600)
                    
                    self.serial_conn = serial.Serial(port, baudrate, timeout=2)
                    self.is_initialized = True
                    logger.info(f"Serial controller {self.device_id} initialized on {port}")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize serial controller: {e}")
                    return False
            
            elif self.controller_type == "network":
                # Initialize network controller
                self.is_initialized = True
                logger.info(f"Network controller {self.device_id} initialized")
            
            else:  # simulated
                self.is_initialized = True
                logger.info(f"Simulated controller {self.device_id} initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize access controller: {e}")
            return False
    
    def grant_access(self, user_id: str = None) -> bool:
        """Grant access (open door/lock)"""
        if not self.is_connected():
            logger.error("Access controller not connected")
            return False
        
        try:
            logger.info(f"Granting access via controller {self.device_id}")
            
            if self.controller_type == "gpio":
                import RPi.GPIO as GPIO
                if self.active_low:
                    GPIO.output(self.gpio_pin, GPIO.LOW)  # Active low = open
                else:
                    GPIO.output(self.gpio_pin, GPIO.HIGH)  # Active high = open
                
                self.is_open = True
                
                # Schedule door closure
                time.sleep(self.open_duration)
                self.deny_access()
            
            elif self.controller_type == "serial":
                # Send open command via serial
                open_command = b"\x01\x02\x03\x04"  # Example command
                self.serial_conn.write(open_command)
                self.is_open = True
                
                # Schedule closure
                time.sleep(self.open_duration)
                self.deny_access()
            
            elif self.controller_type == "network":
                # Send network command
                self.is_open = True
                logger.info(f"Network access granted for {self.device_id}")
            
            else:  # simulated
                self.is_open = True
                logger.info(f"Simulated access granted for {self.device_id}")
                time.sleep(self.open_duration)
                self.is_open = False
            
            # Update statistics
            self.access_count += 1
            self.last_access_time = time.time()
            
            if user_id:
                logger.info(f"Access granted to user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error granting access: {e}")
            return False
    
    def deny_access(self) -> bool:
        """Deny access (close door/lock)"""
        if not self.is_connected():
            return False
        
        try:
            if self.controller_type == "gpio":
                import RPi.GPIO as GPIO
                if self.active_low:
                    GPIO.output(self.gpio_pin, GPIO.HIGH)  # Normally high = closed
                else:
                    GPIO.output(self.gpio_pin, GPIO.LOW)   # Normally low = closed
            
            elif self.controller_type == "serial":
                # Send close command
                close_command = b"\x01\x02\x03\x05"  # Example command
                self.serial_conn.write(close_command)
            
            self.is_open = False
            logger.info(f"Access denied/closed for {self.device_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error denying access: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        status = {
            "device_id": self.device_id,
            "controller_type": self.controller_type,
            "connected": self.is_connected(),
            "is_open": self.is_open,
            "access_count": self.access_count,
            "last_access_time": self.last_access_time,
            "open_duration": self.open_duration
        }
        
        if self.controller_type == "gpio":
            status["gpio_pin"] = self.gpio_pin
            status["active_low"] = self.active_low
        
        return status
    
    def is_connected(self) -> bool:
        """Check if controller is connected"""
        return self.is_initialized
    
    def disconnect(self):
        """Disconnect controller"""
        try:
            if self.controller_type == "gpio":
                import RPi.GPIO as GPIO
                GPIO.cleanup(self.gpio_pin)
            
            elif self.controller_type == "serial" and hasattr(self, 'serial_conn'):
                self.serial_conn.close()
            
            self.is_initialized = False
            logger.info(f"Access controller {self.device_id} disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting controller: {e}")
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information"""
        return self.get_status()
    
    def test_device(self) -> Tuple[bool, str]:
        """Test access controller"""
        try:
            if not self.is_connected():
                return False, "Controller not connected"
            
            # Test opening and closing
            test_result = self.grant_access("test_user")
            
            if test_result:
                return True, "Access controller test passed"
            else:
                return False, "Failed to grant access"
            
        except Exception as e:
            return False, f"Access controller test failed: {e}"