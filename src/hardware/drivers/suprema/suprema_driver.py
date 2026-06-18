"""
Real Suprema Access Control Device Driver
Uses Suprema BioStar API
"""

import requests
import json
import base64
import time
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from ..base_device import BaseDevice

import logging
logger = logging.getLogger(__name__)

class SupremaDevice(BaseDevice):
    """
    Real Suprema Access Control Device Driver
    Supports:
    - Suprema BioStar 2 devices
    - Suprema Access Control Panels
    - Suprema Biometric Devices
    - Models: BioEntry, FaceStation, Xpass, etc.
    """
    
    def __init__(self, ip: str, port: int = 443, username: str = 'admin', 
                 password: str = 'admin', use_https: bool = True):
        """
        Initialize Suprema device.
        
        Args:
            ip: Device IP address
            port: API port (default 443 for HTTPS)
            username: Admin username
            password: Admin password
            use_https: Use HTTPS (default True)
        """
        super().__init__(ip, port, username, password)
        self.device_type = "suprema"
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{ip}:{port}/api"
        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification for self-signed certs
        self.token = None
        self.token_expiry = 0
        self.timeout = 10
        self.door_count = 0
        self.user_count = 0
        self.event_count = 0
        
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
    def connect(self) -> bool:
        """
        Connect to Suprema device using REST API.
        
        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to Suprema device at {self.ip}:{self.port}")
            
            # Authenticate and get token
            if self._login():
                # Get device info
                self._get_device_info()
                
                # Get system stats
                self._get_system_stats()
                
                self.connected = True
                logger.info(f"[OK] Connected to Suprema {self.model} (SN: {self.serial_number})")
                logger.info(f"   Firmware: {self.firmware_version}")
                logger.info(f"   Doors: {self.door_count}, Users: {self.user_count}")
                return True
            else:
                logger.error("[ERROR] Failed to authenticate")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error(f"[ERROR] Connection error: Device at {self.ip}:{self.port} not reachable")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"[ERROR] Connection timeout: Device at {self.ip}:{self.port} not responding")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from the device.
        
        Returns:
            True if disconnected successfully
        """
        if self.token:
            try:
                self._logout()
            except:
                pass
        
        self.session.close()
        self.connected = False
        self.token = None
        logger.info(f"Disconnected from Suprema device at {self.ip}:{self.port}")
        return True
    
    def _login(self) -> bool:
        """
        Login to Suprema device and get access token.
        
        Returns:
            True if login successful
        """
        try:
            url = f"{self.base_url}/login"
            
            # Suprema uses basic auth or token-based auth
            if self.username and self.password:
                # Try basic auth first
                auth = (self.username, self.password)
                response = self.session.get(url, auth=auth, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get('access_token')
                    self.token_expiry = time.time() + data.get('expires_in', 3600)
                    return True
                
                # Try form-based login
                login_data = {
                    'username': self.username,
                    'password': self.password
                }
                
                response = self.session.post(url, data=login_data, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get('token') or data.get('access_token')
                    
                    # Set token for subsequent requests
                    if self.token:
                        self.session.headers.update({
                            'Authorization': f'Bearer {self.token}',
                            'Content-Type': 'application/json'
                        })
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def _logout(self):
        """Logout from device."""
        try:
            url = f"{self.base_url}/logout"
            self.session.post(url, timeout=self.timeout)
        except:
            pass
    
    def _ensure_token(self) -> bool:
        """Ensure token is valid, refresh if needed."""
        if self.token and time.time() < self.token_expiry:
            return True
        
        # Token expired, re-login
        return self._login()
    
    def _api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make API request to Suprema device.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Response JSON or None
        """
        if not self._ensure_token():
            logger.error("No valid token")
            return None
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=self.timeout)
            else:
                logger.error(f"Unsupported method: {method}")
                return None
            
            if response.status_code in [200, 201, 204]:
                return response.json() if response.content else {}
            elif response.status_code == 401:
                # Token expired
                self.token = None
                return self._api_request(method, endpoint, data)
            else:
                logger.error(f"API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None
    
    def _get_device_info(self):
        """Get device information."""
        try:
            # Get device info
            response = self._api_request('GET', '/devices/info')
            
            if response:
                self.model = response.get('model', 'Unknown')
                self.serial_number = response.get('serial', '')
                self.firmware_version = response.get('firmware', '')
                
                # Store additional info
                self.device_info = {
                    'model': self.model,
                    'serial': self.serial_number,
                    'firmware': self.firmware_version,
                    'mac': response.get('mac'),
                    'device_name': response.get('name'),
                    'timezone': response.get('timezone'),
                    'platform': response.get('platform')
                }
                
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
    
    def _get_system_stats(self):
        """Get system statistics."""
        try:
            # Get door count
            response = self._api_request('GET', '/doors')
            if response:
                self.door_count = len(response.get('records', []))
            
            # Get user count
            response = self._api_request('GET', '/users/count')
            if response:
                self.user_count = response.get('count', 0)
            
            # Get event count
            response = self._api_request('GET', '/events/count')
            if response:
                self.event_count = response.get('count', 0)
                
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
    
    def get_users(self, offset: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get users from the device.
        
        Args:
            offset: Pagination offset
            limit: Number of users per page
            
        Returns:
            List of user dictionaries
        """
        if not self.connected:
            logger.error("Device not connected")
            return []
        
        users = []
        try:
            logger.info("Fetching users from Suprema device...")
            
            # Get users with pagination
            response = self._api_request('GET', f'/users?offset={offset}&limit={limit}')
            
            if response:
                records = response.get('records', [])
                
                for record in records:
                    user = {
                        'id': record.get('user_id'),
                        'user_id': record.get('user_id'),
                        'name': record.get('name'),
                        'email': record.get('email'),
                        'department': record.get('department'),
                        'title': record.get('title'),
                        'phone': record.get('phone'),
                        'status': record.get('status'),
                        'user_type': record.get('user_type'),
                        'fingerprint_count': record.get('fingerprint_count', 0),
                        'card_count': record.get('card_count', 0),
                        'face_count': record.get('face_count', 0),
                        'pin_configured': record.get('pin_configured', False),
                        'access_groups': record.get('access_groups', []),
                        'created_at': record.get('created_at'),
                        'updated_at': record.get('updated_at')
                    }
                    
                    # Get user's cards
                    cards_response = self._api_request('GET', f'/users/{user["id"]}/cards')
                    if cards_response:
                        user['cards'] = cards_response.get('records', [])
                    
                    users.append(user)
            
            logger.info(f"[OK] Retrieved {len(users)} users from Suprema device")
            return users
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting users: {e}")
            return []
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User dictionary or None
        """
        if not self.connected:
            return None
        
        try:
            response = self._api_request('GET', f'/users/{user_id}')
            
            if response:
                user = {
                    'id': response.get('user_id'),
                    'user_id': response.get('user_id'),
                    'name': response.get('name'),
                    'email': response.get('email'),
                    'department': response.get('department'),
                    'title': response.get('title'),
                    'phone': response.get('phone'),
                    'status': response.get('status'),
                    'user_type': response.get('user_type'),
                    'fingerprint_count': response.get('fingerprint_count', 0),
                    'card_count': response.get('card_count', 0),
                    'face_count': response.get('face_count', 0),
                    'pin_configured': response.get('pin_configured', False),
                    'access_groups': response.get('access_groups', []),
                    'photo': response.get('photo'),
                    'created_at': response.get('created_at'),
                    'updated_at': response.get('updated_at')
                }
                
                # Get user's cards
                cards_response = self._api_request('GET', f'/users/{user_id}/cards')
                if cards_response:
                    user['cards'] = cards_response.get('records', [])
                
                return user
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
        
        return None
    
    def add_user(self, user_id: str, name: str, **kwargs) -> bool:
        """
        Add a user to the device.
        
        Args:
            user_id: User ID
            name: User name
            **kwargs: Additional fields (email, department, etc.)
            
        Returns:
            True if successful
        """
        if not self.connected:
            logger.error("Device not connected")
            return False
        
        try:
            user_data = {
                'user_id': user_id,
                'name': name,
                'status': kwargs.get('status', 'active'),
                'user_type': kwargs.get('user_type', 'user'),
                'email': kwargs.get('email', ''),
                'department': kwargs.get('department', ''),
                'title': kwargs.get('title', ''),
                'phone': kwargs.get('phone', ''),
                'access_groups': kwargs.get('access_groups', [])
            }
            
            # Add PIN if provided
            if 'pin' in kwargs:
                user_data['pin'] = kwargs['pin']
            
            response = self._api_request('POST', '/users', user_data)
            
            if response:
                logger.info(f"[OK] Added user {name} (ID: {user_id})")
                
                # Add cards if provided
                if 'cards' in kwargs:
                    for card in kwargs['cards']:
                        self.add_card(user_id, card)
                
                self.user_count += 1
                return True
            else:
                logger.error(f"[ERROR] Failed to add user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error adding user: {e}")
            return False
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        Update an existing user.
        
        Args:
            user_id: User ID to update
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            update_data = {}
            
            # Only include fields that are provided
            fields = ['name', 'email', 'department', 'title', 'phone', 
                     'status', 'user_type', 'access_groups']
            
            for field in fields:
                if field in kwargs:
                    update_data[field] = kwargs[field]
            
            if 'pin' in kwargs:
                update_data['pin'] = kwargs['pin']
            
            response = self._api_request('PUT', f'/users/{user_id}', update_data)
            
            if response:
                logger.info(f"[OK] Updated user {user_id}")
                return True
            else:
                logger.error(f"[ERROR] Failed to update user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error updating user: {e}")
            return False
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user from the device.
        
        Args:
            user_id: User ID to delete
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            response = self._api_request('DELETE', f'/users/{user_id}')
            
            if response is not None:  # 204 response returns None
                logger.info(f"[OK] Deleted user {user_id}")
                self.user_count -= 1
                return True
            else:
                logger.error(f"[ERROR] Failed to delete user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error deleting user: {e}")
            return False
    
    def delete_all_users(self) -> bool:
        """Delete all users from device."""
        if not self.connected:
            return False
        
        try:
            # Get all users
            users = self.get_users(limit=1000)
            
            for user in users:
                self.delete_user(user['id'])
                time.sleep(0.1)  # Avoid overwhelming the device
            
            logger.info(f"[OK] Deleted all users")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Error deleting all users: {e}")
            return False
    
    def add_card(self, user_id: str, card_number: str, card_type: str = 'rfid') -> bool:
        """
        Add a card to a user.
        
        Args:
            user_id: User ID
            card_number: Card number
            card_type: Card type (rfid, smart, etc.)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            card_data = {
                'card_id': card_number,
                'card_type': card_type,
                'status': 'active'
            }
            
            response = self._api_request('POST', f'/users/{user_id}/cards', card_data)
            
            if response:
                logger.info(f"[OK] Added card {card_number} to user {user_id}")
                return True
            else:
                logger.error(f"[ERROR] Failed to add card to user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error adding card: {e}")
            return False
    
    def delete_card(self, user_id: str, card_number: str) -> bool:
        """
        Delete a card from a user.
        
        Args:
            user_id: User ID
            card_number: Card number
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            response = self._api_request('DELETE', f'/users/{user_id}/cards/{card_number}')
            
            if response is not None:
                logger.info(f"[OK] Deleted card {card_number} from user {user_id}")
                return True
            else:
                logger.error(f"[ERROR] Failed to delete card from user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error deleting card: {e}")
            return False
    
    def send_command(self, command: str, params: Optional[Dict] = None) -> Any:
        """
        Send a command to the device.
        
        Args:
            command: Command to send
            params: Command parameters
            
        Returns:
            Command response
        """
        if not self.connected:
            logger.error("Device not connected")
            return None
        
        try:
            if command == "open_door":
                door_id = params.get('door_id', 1) if params else 1
                return self.open_door(door_id)
            elif command == "get_time":
                return self.get_device_time()
            elif command == "set_time":
                dt = params.get('datetime') if params else None
                return self.set_device_time()
            elif command == "get_status":
                return self.get_device_status()
            elif command == "reboot":
                return self.reboot_device()
            elif command == "get_config":
                return self.get_device_config()
            elif command == "get_events":
                if params is not None:
                    start = params.get('start_time')
                    end = params.get('end_time')
                    limit = params.get('limit', 100)
                else:
                    start = None
                    end = None
                    limit = 100
                return self.get_events(start, end, limit)
            else:
                logger.warning(f"Unknown command: {command}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending command {command}: {e}")
            return None
    
    def open_door(self, door_id: int = 1, duration: int = 5) -> bool:
        """
        Open a specific door.
        
        Args:
            door_id: Door number
            duration: How long to hold door open (seconds)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Get door ID from parameters
            doors = self._api_request('GET', '/doors')
            
            if doors and 'records' in doors:
                # Find the door by number/index
                for door in doors['records']:
                    if door.get('door_id') == str(door_id) or door.get('index') == door_id:
                        actual_door_id = door.get('id')
                        
                        # Open door
                        response = self._api_request('POST', f'/doors/{actual_door_id}/open', {
                            'duration': duration
                        })
                        
                        if response:
                            logger.info(f"[OK] Door {door_id} opened for {duration} seconds")
                            return True
            
            # If no door found, try direct command
            response = self._api_request('POST', f'/doors/{door_id}/open')
            
            if response:
                logger.info(f"[OK] Door {door_id} opened")
                return True
            else:
                logger.error(f"[ERROR] Failed to open door {door_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error opening door: {e}")
            return False
    
    def get_events(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, 
               limit: int = 100) -> List[Dict]:
        """
        Get access events from device.
        
        Args:
            start_time: Start time for events
            end_time: End time for events
            limit: Maximum number of events
            
        Returns:
            List of event dictionaries
        """
        if not self.connected:
            return []
        
        # Set defaults if not provided
        if start_time is None:
            start_time = datetime.now().replace(hour=0, minute=0, second=0)
        if end_time is None:
            end_time = datetime.now()
        
        events = []
        try:
            # Build query parameters
            params = f"?limit={limit}"
            
            # Add time parameters if they exist (they always will now because of defaults above)
            params += f"&start_time={start_time.isoformat()}"
            params += f"&end_time={end_time.isoformat()}"
            
            response = self._api_request('GET', f'/events{params}')
            
            if response:
                records = response.get('records', [])
                
                for record in records:
                    timestamp = record.get('timestamp')
                    event = {
                        'id': record.get('id'),
                        'user_id': record.get('user_id'),
                        'user_name': record.get('user_name'),
                        'door_id': record.get('door_id'),
                        'door_name': record.get('door_name'),
                        'event_type': record.get('event_type'),
                        'event_type_name': record.get('event_type_name'),
                        'timestamp': timestamp,
                        'datetime': datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else None,
                        'status': record.get('status'),
                        'verification_mode': record.get('verification_mode'),
                        'device_id': self.serial_number
                    }
                    events.append(event)
                
                logger.info(f"[OK] Retrieved {len(events)} events")
            else:
                logger.warning("Failed to get events")
                
        except Exception as e:
            logger.error(f"[ERROR] Error getting events: {e}")
        
        return events
    
    def get_device_time(self) -> Optional[datetime]:
        """
        Get device current time.
        
        Returns:
            Device datetime or None
        """
        if not self.connected:
            return None
        
        try:
            response = self._api_request('GET', '/system/time')
            
            if response:
                time_str = response.get('time')
                if time_str:
                    return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
        except Exception as e:
            logger.error(f"Error getting device time: {e}")
        
        return None
    
    def set_device_time(self, dt: Optional[datetime] = None) -> bool:
        """
        Set device time.
        
        Args:
            dt: Datetime to set (default: current time)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        if dt is None:
            dt = datetime.now()
        
        try:
            time_data = {
                'time': dt.isoformat()
            }
            
            response = self._api_request('PUT', '/system/time', time_data)
            
            if response:
                logger.info(f"[OK] Device time set to {dt}")
                return True
            else:
                logger.error("[ERROR] Failed to set device time")
                return False
                
        except Exception as e:
            logger.error(f"Error setting device time: {e}")
            return False
    
    def reboot_device(self) -> bool:
        """
        Reboot the device.
        
        Returns:
            True if reboot command sent successfully
        """
        if not self.connected:
            return False
        
        try:
            response = self._api_request('POST', '/system/reboot')
            
            if response:
                logger.info("[OK] Device reboot command sent")
                self.connected = False
                return True
            else:
                logger.error("[ERROR] Failed to send reboot command")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error rebooting device: {e}")
            return False
    
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get device status.
        
        Returns:
            Device status dictionary
        """
        status = {
            'connected': self.connected,
            'device_type': self.device_type,
            'model': self.model,
            'serial': self.serial_number,
            'firmware': self.firmware_version,
            'ip': self.ip,
            'port': self.port,
            'door_count': self.door_count,
            'user_count': self.user_count,
            'event_count': self.event_count
        }
        
        try:
            # Get system status
            response = self._api_request('GET', '/system/status')
            
            if response:
                status['system_status'] = response.get('status')
                status['uptime'] = response.get('uptime')
                status['cpu_usage'] = response.get('cpu_usage')
                status['memory_usage'] = response.get('memory_usage')
                status['temperature'] = response.get('temperature')
                
        except Exception as e:
            logger.debug(f"Could not get detailed status: {e}")
        
        return status
    
    def get_device_config(self) -> Dict[str, Any]:
        """
        Get device configuration.
        
        Returns:
            Device configuration dictionary
        """
        if not self.connected:
            return {}
        
        config = {}
        
        try:
            # Get network config
            response = self._api_request('GET', '/config/network')
            if response:
                config['network'] = response
            
            # Get access config
            response = self._api_request('GET', '/config/access')
            if response:
                config['access'] = response
            
            # Get door configs
            response = self._api_request('GET', '/doors')
            if response:
                config['doors'] = response.get('records', [])
            
            # Get system config
            response = self._api_request('GET', '/config/system')
            if response:
                config['system'] = response
            
        except Exception as e:
            logger.error(f"Error getting device config: {e}")
        
        return config
    
    def backup_config(self) -> Optional[bytes]:
        """
        Backup device configuration.
        
        Returns:
            Configuration data as bytes or None
        """
        if not self.connected:
            return None
        
        try:
            response = self._api_request('GET', '/config/backup')
            
            if response:
                # Response might contain base64 encoded config
                config_data = response.get('data')
                if config_data:
                    return base64.b64decode(config_data)
                else:
                    return json.dumps(response).encode()
            
        except Exception as e:
            logger.error(f"Error backing up config: {e}")
        
        return None
    
    def restore_config(self, config_data: bytes) -> bool:
        """
        Restore device configuration.
        
        Args:
            config_data: Configuration data from backup
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Try to parse as JSON
            try:
                config_json = json.loads(config_data.decode())
                response = self._api_request('POST', '/config/restore', config_json)
            except:
                # Send as base64
                config_b64 = base64.b64encode(config_data).decode()
                response = self._api_request('POST', '/config/restore', {
                    'data': config_b64
                })
            
            if response:
                logger.info("[OK] Configuration restored successfully")
                return True
            else:
                logger.error("[ERROR] Failed to restore configuration")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring config: {e}")
            return False
    
    def __str__(self) -> str:
        status = "Connected" if self.connected else "Disconnected"
        return f"Suprema {self.model} at {self.ip}:{self.port} [{status}]"