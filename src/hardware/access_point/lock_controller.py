"""
Lock Controller - Controls the door lock via GPIO
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LockController:
    """Controls the door lock"""
    
    def __init__(self, gpio_pin=17, unlock_duration=5, active_high=True):
        self.gpio_pin = gpio_pin
        self.unlock_duration = unlock_duration
        self.active_high = active_high
        self.is_locked = True
        self.gpio_available = False
        
        # Try to import RPi.GPIO (only works on Raspberry Pi)
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self.gpio_available = True
            self._setup_gpio()
        except (ImportError, RuntimeError):
            logger.warning("RPi.GPIO not available - running in simulation mode")
            self.gpio_available = False
    
    def _setup_gpio(self):
        """Setup GPIO pins"""
        if not self.gpio_available:
            return
        
        try:
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setup(self.gpio_pin, self.GPIO.OUT)
            self._set_lock_state(True)  # Locked by default
            logger.info(f"GPIO setup complete on pin {self.gpio_pin}")
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")
            self.gpio_available = False
    
    def _set_lock_state(self, locked: bool):
        """Set the lock state (True = locked, False = unlocked)"""
        if not self.gpio_available:
            logger.info(f"SIMULATION: Lock {'locked' if locked else 'unlocked'}")
            self.is_locked = locked
            return
        
        try:
            # GPIO.HIGH = locked or unlocked depending on active_high
            if self.active_high:
                state = self.GPIO.LOW if locked else self.GPIO.HIGH
            else:
                state = self.GPIO.HIGH if locked else self.GPIO.LOW
            
            self.GPIO.output(self.gpio_pin, state)
            self.is_locked = locked
            logger.info(f"Lock {'locked' if locked else 'unlocked'}")
            
        except Exception as e:
            logger.error(f"Error setting lock state: {e}")
    
    def unlock(self, duration: Optional[int] = None):
        """Unlock the door for a duration"""
        duration = duration or self.unlock_duration
        logger.info(f"Unlocking door for {duration} seconds")
        
        self._set_lock_state(False)
        time.sleep(duration)
        self._set_lock_state(True)
        logger.info("Door locked")
        
        return True
    
    def lock(self):
        """Lock the door"""
        self._set_lock_state(True)
        return True
    
    def is_locked(self) -> bool:
        """Check if the door is locked"""
        return self.is_locked
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        if self.gpio_available:
            try:
                self._set_lock_state(True)
                self.GPIO.cleanup()
                logger.info("GPIO cleanup complete")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")

class LockControllerSimulation:
    """Simulation mode for testing without hardware"""
    
    def __init__(self, unlock_duration=5):
        self.unlock_duration = unlock_duration
        self.is_locked = True
        self.logger = logging.getLogger(__name__)
    
    def unlock(self, duration=None):
        duration = duration or self.unlock_duration
        self.logger.info(f"SIMULATION: Unlocking for {duration} seconds")
        self.is_locked = False
        time.sleep(duration)
        self.is_locked = True
        self.logger.info("SIMULATION: Door locked")
        return True
    
    def lock(self):
        self.logger.info("SIMULATION: Locking door")
        self.is_locked = True
        return True
    
    def cleanup(self):
        pass