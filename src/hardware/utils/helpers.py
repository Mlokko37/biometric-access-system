"""
Helper functions for hardware management
"""

import json
import hashlib
import time
from typing import Any, Dict, Optional
from datetime import datetime


def create_device_id(device_type: str, identifier: str) -> str:
    """Create unique device ID"""
    timestamp = int(time.time())
    unique_string = f"{device_type}_{identifier}_{timestamp}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:8]


def format_timestamp(timestamp: Optional[float] = None) -> str:
    """Format timestamp to readable string"""
    if timestamp is None:
        timestamp = time.time()
    
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def save_to_json(data: Any, filepath: str) -> bool:
    """Save data to JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving to JSON: {e}")
        return False


def load_from_json(filepath: str) -> Optional[Any]:
    """Load data from JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error loading from JSON: {e}")
        return None


def validate_config(config: Dict[str, Any], required_fields: list) -> tuple:
    """Validate configuration dictionary"""
    missing_fields = []
    
    for field in required_fields:
        if field not in config:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, "Configuration valid"


def calculate_confidence(score: float, max_score: float = 100.0) -> float:
    """Calculate confidence percentage"""
    confidence = (score / max_score) * 100.0
    return max(0.0, min(confidence, 100.0))  # Clamp between 0 and 100


def generate_audit_log(action: str, user_id: str = "system", details: Dict = None) -> Dict:
    """Generate audit log entry"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "user_id": user_id,
        "details": details or {}
    }
    
    return log_entry


class Timer:
    """Simple timer context manager"""
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.end = time.time()
        self.duration = self.end - self.start
    
    def get_duration(self) -> float:
        """Get elapsed time in seconds"""
        return self.duration if hasattr(self, 'duration') else 0.0