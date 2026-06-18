"""
Hardware configuration management
"""
import os
import yaml
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HardwareConfig:
    """Hardware configuration class"""
    config_file: str = "hardware/configs/devices.yaml"
    fingerprint_scanners: List[Dict] = field(default_factory=list)
    facial_cameras: List[Dict] = field(default_factory=list)
    access_controllers: List[Dict] = field(default_factory=list)
    fingerprint_threshold: float = 75.0
    facial_threshold: float = 80.0
    
    def __post_init__(self):
        """Initialize after dataclass creation"""
        self.load_config()
    
    def load_config(self):
        """Load hardware configuration from YAML file"""
        try:
            # Create default config if not exists
            if not os.path.exists(self.config_file):
                self.create_default_config()
            
            # Load config
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Parse configuration
            if config:
                self.fingerprint_scanners = config.get('fingerprint_scanners', [])
                self.facial_cameras = config.get('facial_cameras', [])
                self.access_controllers = config.get('access_controllers', [])
                self.fingerprint_threshold = config.get('fingerprint_threshold', 75.0)
                self.facial_threshold = config.get('facial_threshold', 80.0)
            
            # Use logger instead of print
            logger.info(f"Loaded configuration from {self.config_file}")
            logger.info(f"Devices: {len(self.fingerprint_scanners)} scanners, "
                       f"{len(self.facial_cameras)} cameras, "
                       f"{len(self.access_controllers)} controllers")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Create default config on error
            self.create_default_config()
    
    def create_default_config(self):
        """Create default configuration file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            default_config = {
                'fingerprint_scanners': [
                    {
                        'device_id': 'scanner_1',
                        'model': 'zkteco_livscan',
                        'port': 'USB0',
                        'baud_rate': 115200,
                        'timeout': 5
                    }
                ],
                'facial_cameras': [
                    {
                        'device_id': 'camera_1',
                        'model': 'logitech_c920',
                        'index': 0,
                        'resolution': [1280, 720],
                        'fps': 30
                    }
                ],
                'access_controllers': [
                    {
                        'device_id': 'controller_1',
                        'model': 'relay_board',
                        'port': 'COM3',
                        'baud_rate': 9600
                    }
                ],
                'fingerprint_threshold': 75.0,
                'facial_threshold': 80.0
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            
            logger.info(f"Created default configuration at {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error creating default config: {e}")
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config = {
                'fingerprint_scanners': self.fingerprint_scanners,
                'facial_cameras': self.facial_cameras,
                'access_controllers': self.access_controllers,
                'fingerprint_threshold': self.fingerprint_threshold,
                'facial_threshold': self.facial_threshold
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            logger.info(f"Configuration saved to {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def add_device(self, device_type: str, device_config: Dict) -> bool:
        """Add a new device to configuration"""
        try:
            if device_type == 'fingerprint':
                self.fingerprint_scanners.append(device_config)
            elif device_type == 'facial':
                self.facial_cameras.append(device_config)
            elif device_type == 'controller':
                self.access_controllers.append(device_config)
            else:
                logger.error(f"Unknown device type: {device_type}")
                return False
            
            return self.save_config()
            
        except Exception as e:
            logger.error(f"Error adding device: {e}")
            return False
    
    def remove_device(self, device_type: str, device_id: str) -> bool:
        """Remove a device from configuration"""
        try:
            if device_type == 'fingerprint':
                self.fingerprint_scanners = [
                    d for d in self.fingerprint_scanners 
                    if d.get('device_id') != device_id
                ]
            elif device_type == 'facial':
                self.facial_cameras = [
                    d for d in self.facial_cameras 
                    if d.get('device_id') != device_id
                ]
            elif device_type == 'controller':
                self.access_controllers = [
                    d for d in self.access_controllers 
                    if d.get('device_id') != device_id
                ]
            else:
                logger.error(f"Unknown device type: {device_type}")
                return False
            
            return self.save_config()
            
        except Exception as e:
            logger.error(f"Error removing device: {e}")
            return False