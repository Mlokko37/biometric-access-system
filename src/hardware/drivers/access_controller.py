"""
Access Controller Driver
Controls door locks, relays, and Arduino-based controllers
"""

import serial
import serial.tools.list_ports
import time
import logging
import os  # Added missing import
from typing import Optional, Dict, Any, Tuple
import threading

logger = logging.getLogger(__name__)

class AccessController:
    """Driver for access control hardware (Arduino/Relay boards)."""
    
    # Command codes
    CMD_OPEN_DOOR = b'OPEN'
    CMD_CLOSE_DOOR = b'CLOSE'
    CMD_STATUS = b'STATUS'
    CMD_PING = b'PING'
    CMD_LOCK = b'LOCK'
    CMD_UNLOCK = b'UNLOCK'
    CMD_RESET = b'RESET'
    CMD_GET_TEMP = b'TEMP'
    
    # Response codes
    RESP_OK = b'OK'
    RESP_ERROR = b'ERR'
    RESP_OPEN = b'OPENED'
    RESP_CLOSED = b'CLOSED'
    RESP_LOCKED = b'LOCKED'
    RESP_UNLOCKED = b'UNLOCKED'
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 9600, timeout: int = 2):
        """
        Initialize access controller.
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB1' or 'COM4')
            baudrate: Communication speed
            timeout: Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.door_status = 'closed'
        self.lock_status = 'locked'
        self.temperature = 25.0
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
    
    def connect(self) -> bool:
        """Connect to access controller."""
        try:
            # Auto-detect port if not specified
            if not self.port:
                self.port = self._detect_port()
                if not self.port:
                    logger.error("No access controller found")
                    return False
            
            # Open serial connection
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            
            # Wait for device to initialize
            time.sleep(2)
            
            # Test connection
            if self.test_connection():
                self.connected = True
                
                # Start status monitoring
                self._start_monitoring()
                
                logger.info(f"Connected to access controller on {self.port}")
                return True
            else:
                logger.error("Connection test failed")
                if self.serial:
                    self.serial.close()
                return False
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def _detect_port(self) -> Optional[str]:
        """Auto-detect access controller port."""
        try:
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                # Arduino boards typically have these identifiers
                if 'Arduino' in port.description:
                    logger.info(f"Found Arduino on {port.device}")
                    return port.device
                
                # Check for USB serial devices
                if 'USB Serial' in port.description or 'CH340' in port.description:
                    logger.info(f"Found USB Serial device on {port.device}")
                    return port.device
            
            # If no specific match, try common Arduino ports
            common_ports = ['/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyUSB0', 'COM4', 'COM5']
            for port in common_ports:
                try:
                    if os.path.exists(port):
                        logger.info(f"Trying common port {port}")
                        return port
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Port detection error: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test communication with controller."""
        if not self.serial:
            return False
            
        try:
            # Send ping command
            self.serial.write(self.CMD_PING + b'\n')
            self.serial.flush()
            
            # Wait for response
            time.sleep(0.1)
            
            if self.serial.in_waiting:
                response = self.serial.readline().strip()
                return response == self.RESP_OK
            
            return False
            
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return False
    
    def _start_monitoring(self):
        """Start background thread for status monitoring."""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_loop(self):
        """Monitor status from controller."""
        while self._running and self.connected and self.serial:
            try:
                # Request status
                self.serial.write(self.CMD_STATUS + b'\n')
                self.serial.flush()
                
                # Read response
                if self.serial.in_waiting:
                    response = self.serial.readline().strip().decode()
                    
                    # Parse status (format: "door:closed,lock:locked,temp:25.5")
                    parts = response.split(',')
                    for part in parts:
                        if ':' in part:
                            key, value = part.split(':')
                            if key == 'door':
                                self.door_status = value
                            elif key == 'lock':
                                self.lock_status = value
                            elif key == 'temp':
                                try:
                                    self.temperature = float(value)
                                except:
                                    pass
                
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)
    
    def open_door(self, duration: int = 3) -> bool:
        """
        Open door for specified duration.
        
        Args:
            duration: Time to hold door open in seconds
            
        Returns:
            True if successful
        """
        if not self.connected or not self.serial:
            logger.error("Access controller not connected")
            return False
        
        try:
            # Send open command with duration
            cmd = f"{self.CMD_OPEN_DOOR.decode()} {duration}\n"
            self.serial.write(cmd.encode())
            self.serial.flush()
            
            # Wait for response
            time.sleep(0.5)
            
            if self.serial.in_waiting:
                response = self.serial.readline().strip()
                
                if response == self.RESP_OPEN:
                    logger.info(f"Door opened for {duration} seconds")
                    self.door_status = 'open'
                    
                    # Schedule auto-close (controller should handle this, but we'll track)
                    threading.Timer(duration, self._update_door_status).start()
                    
                    return True
                else:
                    logger.error(f"Failed to open door: {response}")
                    return False
            else:
                logger.error("No response from controller")
                return False
                
        except Exception as e:
            logger.error(f"Open door error: {e}")
            return False
    
    def _update_door_status(self):
        """Update door status after auto-close."""
        self.door_status = 'closed'
        logger.debug("Door auto-closed")
    
    def close_door(self) -> bool:
        """Force door close."""
        if not self.connected or not self.serial:
            return False
        
        try:
            self.serial.write(self.CMD_CLOSE_DOOR + b'\n')
            self.serial.flush()
            
            time.sleep(0.5)
            
            if self.serial.in_waiting:
                response = self.serial.readline().strip()
                
                if response == self.RESP_CLOSED:
                    logger.info("Door closed")
                    self.door_status = 'closed'
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Close door error: {e}")
            return False
    
    def lock_door(self) -> bool:
        """Lock the door."""
        if not self.connected or not self.serial:
            return False
        
        try:
            self.serial.write(self.CMD_LOCK + b'\n')
            self.serial.flush()
            
            time.sleep(0.5)
            
            if self.serial.in_waiting:
                response = self.serial.readline().strip()
                
                if response == self.RESP_LOCKED:
                    logger.info("Door locked")
                    self.lock_status = 'locked'
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Lock door error: {e}")
            return False
    
    def unlock_door(self) -> bool:
        """Unlock the door."""
        if not self.connected or not self.serial:
            return False
        
        try:
            self.serial.write(self.CMD_UNLOCK + b'\n')
            self.serial.flush()
            
            time.sleep(0.5)
            
            if self.serial.in_waiting:
                response = self.serial.readline().strip()
                
                if response == self.RESP_UNLOCKED:
                    logger.info("Door unlocked")
                    self.lock_status = 'unlocked'
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Unlock door error: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current controller status."""
        return {
            'connected': self.connected,
            'port': self.port,
            'door': self.door_status,
            'lock': self.lock_status,
            'temperature': self.temperature,
            'baudrate': self.baudrate
        }
    
    def grant_access(self, duration: int = 3) -> bool:
        """
        Grant access by unlocking and opening door.
        
        Args:
            duration: How long to hold door open
            
        Returns:
            True if successful
        """
        logger.info("Granting access")
        
        # Unlock first if needed
        if self.lock_status == 'locked':
            if not self.unlock_door():
                logger.error("Failed to unlock door")
                return False
        
        # Open door
        if not self.open_door(duration):
            logger.error("Failed to open door")
            return False
        
        # Log access
        logger.info(f"Access granted for {duration} seconds")
        
        return True
    
    def deny_access(self) -> bool:
        """Deny access and ensure door is locked."""
        logger.info("Denying access")
        
        # Close door if open
        if self.door_status == 'open':
            self.close_door()
        
        # Ensure door is locked
        if self.lock_status == 'unlocked':
            self.lock_door()
        
        return True
    
    def disconnect(self):
        """Disconnect from controller."""
        self._running = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
        
        self.serial = None
        self.connected = False
        logger.info("Disconnected from access controller")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()