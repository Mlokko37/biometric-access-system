import os
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class AccessController:
    """Controls physical access devices."""
    
    def __init__(self, simulation_mode: bool = True):
        """Initialize access controller."""
        self.simulation_mode = simulation_mode
        self.arduino_connected = False
        self.serial_conn = None
        
        if not simulation_mode:
            self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize hardware connections."""
        try:
            # Try to import Arduino/pyserial
            import serial
            
            # Get port from environment or use default
            port = os.getenv('ARDUINO_PORT', 'COM3')  # COM3 for Windows, /dev/ttyUSB0 for Linux
            
            # Initialize serial connection
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=1
            )
            
            time.sleep(2)  # Wait for Arduino to initialize
            self.arduino_connected = True
            logger.info(f"Arduino connected on {port}")
            
        except ImportError:
            logger.warning("pyserial not installed, using simulation mode")
            self.simulation_mode = True
        except Exception as e:
            logger.warning(f"Arduino connection failed: {str(e)}, using simulation mode")
            self.simulation_mode = True
    
    def grant_access(self, duration: int = 3):
        """
        Grant access by activating lock.
        
        Args:
            duration: How long to keep access granted (seconds)
        """
        try:
            logger.info(f"Granting access for {duration} seconds")
            
            if self.simulation_mode or not self.arduino_connected:
                # Simulation mode
                print(f"🎫 ACCESS GRANTED (Simulation - lock would open for {duration}s)")
                print("    [GREEN LED ON] [BUZZER: BEEP] [LOCK: OPEN]")
            else:
                # Real hardware control
                self.serial_conn.write(b'GRANT\n')
                response = self.serial_conn.readline().decode().strip()
                logger.info(f"Arduino response: {response}")
                
                # Keep access granted for specified duration
                time.sleep(duration)
                
                # Close the lock
                self.serial_conn.write(b'DENY\n')
            
            # Log the access event
            self._log_access_event('granted', duration)
            
        except Exception as e:
            logger.error(f"Error granting access: {str(e)}")
    
    def deny_access(self, reason: str = "Authentication failed"):
        """
        Deny access.
        
        Args:
            reason: Reason for denial
        """
        try:
            logger.warning(f"Denying access: {reason}")
            
            if self.simulation_mode or not self.arduino_connected:
                # Simulation mode
                print(f"[ERROR] ACCESS DENIED: {reason}")
                print("    [RED LED ON] [BUZZER: ERROR BEEP] [LOCK: CLOSED]")
            else:
                # Real hardware control
                self.serial_conn.write(b'DENY\n')
                response = self.serial_conn.readline().decode().strip()
                logger.info(f"Arduino response: {response}")
            
            # Log the access event
            self._log_access_event('denied', 0, reason)
            
        except Exception as e:
            logger.error(f"Error denying access: {str(e)}")
    
    def indicate_waiting(self):
        """Indicate system is waiting for input."""
        if self.simulation_mode:
            print("[WAIT] Waiting for biometric input...")
            print("    [YELLOW LED BLINKING]")
    
    def indicate_processing(self):
        """Indicate system is processing."""
        if self.simulation_mode:
            print("[INFO] Processing biometric data...")
            print("    [BLUE LED ON]")
    
    def _log_access_event(self, result: str, duration: int, reason: str = ""):
        """Log access event to file."""
        try:
            log_dir = 'data/logs'
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, 'access_events.log')
            
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"{timestamp} | {result.upper()} | Duration: {duration}s | Reason: {reason}\n"
            
            with open(log_file, 'a') as f:
                f.write(log_entry)
            
            logger.debug(f"Access event logged: {log_entry.strip()}")
            
        except Exception as e:
            logger.error(f"Failed to log access event: {str(e)}")
    
    def cleanup(self):
        """Clean up hardware connections."""
        if not self.simulation_mode and self.arduino_connected:
            try:
                self.serial_conn.close()
                logger.info("Arduino connection closed")
            except Exception as e:
                logger.error(f"Error closing Arduino connection: {str(e)}")

class MockAccessController:
    """Mock access controller for testing without hardware."""
    
    def grant_access(self, duration: int = 3):
        """Mock grant access."""
        print(f"🎫 [MOCK] ACCESS GRANTED for {duration} seconds")
        print("    [Simulating: Green LED, Buzzer beep, Lock open]")
        time.sleep(1)  # Simulate processing
    
    def deny_access(self, reason: str = "Authentication failed"):
        """Mock deny access."""
        print(f"[ERROR] [MOCK] ACCESS DENIED: {reason}")
        print("    [Simulating: Red LED, Error beep, Lock closed]")
    
    def indicate_waiting(self):
        """Mock waiting indication."""
        print("[WAIT] [MOCK] Waiting for biometric input...")
    
    def indicate_processing(self):
        """Mock processing indication."""
        print("[INFO] [MOCK] Processing biometric data...")
    
    def cleanup(self):
        """Mock cleanup."""
        pass

def test_access_controller():
    """Test the access controller."""
    print("Testing Access Controller...")
    
    # Test with simulation mode
    print("\n1. Simulation Mode:")
    controller = AccessController(simulation_mode=True)
    controller.indicate_waiting()
    controller.indicate_processing()
    controller.grant_access(duration=2)
    controller.deny_access(reason="Test denial")
    controller.cleanup()
    
    # Test mock controller
    print("\n2. Mock Controller:")
    mock = MockAccessController()
    mock.grant_access()
    mock.deny_access("Mock test")
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_access_controller()