"""
Real ZKTeco Access Control Device Driver
Uses ZKTeco PUSH protocol and SDK communication
"""

import socket
import struct
import hashlib
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from ..base_device import BaseDevice

import logging
logger = logging.getLogger(__name__)

class ZKTecoDevice(BaseDevice):
    """
    Real ZKTeco Access Control Device Driver
    Supports:
    - ZKTeco Access Control Panels
    - ZKTeco Biometric Devices
    - ZKTeco Fingerprint/Face Terminals
    - Models: inBio series, F series, etc.
    """
    
    # ZKTeco communication constants
    COMMAND_CONNECT = 1000
    COMMAND_EXIT = 1001
    COMMAND_ENABLE_DEVICE = 1002
    COMMAND_DISABLE_DEVICE = 1003
    COMMAND_ACK_OK = 2000
    COMMAND_ACK_ERROR = 2001
    COMMAND_ACK_DATA = 2002
    COMMAND_PREPARE_DATA = 1500
    COMMAND_DATA = 1501
    COMMAND_FREE_DATA = 1502
    
    COMMAND_GET_FIRMWARE_VERSION = 1100
    COMMAND_GET_SERIAL_NUMBER = 1101
    COMMAND_GET_DEVICE_NAME = 1102
    COMMAND_GET_TIME = 1103
    COMMAND_SET_TIME = 1104
    
    COMMAND_READ_ALL_USER_ID = 1120
    COMMAND_READ_ALL_TEMPLATE = 1121
    COMMAND_UPLOAD_USER = 1122
    COMMAND_DELETE_USER = 1123
    COMMAND_CLEAR_DATA = 1124
    
    COMMAND_TEST_TEMP = 1300
    COMMAND_CAPTURE_FINGER = 1301
    
    def __init__(self, ip: str, port: int = 4370, username: str = 'admin', password: str = 'admin'):
        """
        Initialize ZKTeco device.
        
        Args:
            ip: Device IP address
            port: Communication port (default 4370 for ZKTeco)
            username: Admin username
            password: Admin password
        """
        super().__init__(ip, port, username, password)
        self.device_type = "zkteco"
        self.sock = None
        self.session_id = 0
        self.reply_id = 0
        self.recv_timeout = 10
        self.connection_thread = None
        self.keep_alive = False
        self.user_count = 0
        self.fp_count = 0
        self.log_count = 0
        
    def connect(self) -> bool:
        """
        Connect to ZKTeco device using proprietary protocol.
        
        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to ZKTeco device at {self.ip}:{self.port}")
            
            # Create TCP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.recv_timeout)
            self.sock.connect((self.ip, self.port))
            
            # Send connect command
            self.session_id = 0
            self.reply_id = 0
            
            # Initial handshake
            response = self._send_command(self.COMMAND_CONNECT, b'')
            
            if response:
                # Parse response
                data = self._decode_response(response)
                if data:
                    self.session_id = data.get('session_id', 0)
                    self.reply_id = data.get('reply_id', 0)
                    
                    # Authenticate
                    if self._authenticate():
                        # Get device info
                        self._get_device_info()
                        
                        # Get statistics
                        self._get_device_stats()
                        
                        self.connected = True
                        
                        # Start keep-alive thread
                        self._start_keep_alive()
                        
                        logger.info(f"[OK] Connected to ZKTeco {self.model} (SN: {self.serial_number})")
                        logger.info(f"   Firmware: {self.firmware_version}")
                        logger.info(f"   Users: {self.user_count}, Templates: {self.fp_count}, Logs: {self.log_count}")
                        return True
            
            logger.error("[ERROR] Failed to connect: Authentication failed")
            return False
            
        except socket.timeout:
            logger.error(f"[ERROR] Connection timeout: Device at {self.ip}:{self.port} not responding")
            return False
        except socket.error as e:
            logger.error(f"[ERROR] Socket error: {e}")
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
        self.keep_alive = False
        
        if self.connection_thread:
            self.connection_thread.join(timeout=2)
        
        if self.sock:
            try:
                self._send_command(self.COMMAND_EXIT, b'')
                self.sock.close()
            except:
                pass
            self.sock = None
        
        self.connected = False
        logger.info(f"Disconnected from ZKTeco device at {self.ip}:{self.port}")
        return True
    
    def _authenticate(self) -> bool:
        """Authenticate with the device."""
        try:
            # ZKTeco uses password-based authentication
            if not self.password:
                return True  # Some devices don't require password
            
            # Send authentication command
            password_hash = hashlib.md5(self.password.encode()).hexdigest()
            auth_data = struct.pack('<I', 0) + password_hash.encode()[:32]
            
            response = self._send_command(1102, auth_data)
            
            return response is not None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _send_command(self, command: int, data: bytes) -> Optional[bytes]:
        """
        Send a command to the device.
        
        Args:
            command: Command code
            data: Command data
            
        Returns:
            Response data or None
        """
        if self.sock is None:
            logger.error("Socket not connected")
            return None
            
        try:
            # Build command packet
            self.reply_id += 1
            
            # Header: command (4 bytes), session_id (4 bytes), reply_id (4 bytes)
            header = struct.pack('<III', command, self.session_id, self.reply_id)
            
            # Calculate checksum
            checksum = self._calculate_checksum(header + data)
            
            # Full packet: header + checksum (2 bytes) + data
            packet = header + struct.pack('<H', checksum) + data
            
            # Send packet
            self.sock.send(packet)
            
            # Receive response
            response = self.sock.recv(1024)
            
            if len(response) < 8:
                return None
            
            # Parse header
            recv_command, recv_session, recv_reply = struct.unpack('<III', response[:12])
            
            # Check if this is a response to our command
            if recv_reply != self.reply_id:
                logger.warning(f"Reply ID mismatch: expected {self.reply_id}, got {recv_reply}")
            
            # Get data (skip header and checksum)
            data_start = 14  # 12 bytes header + 2 bytes checksum
            
            return response[data_start:] if len(response) > data_start else b''
            
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return None
    
    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate ZKTeco checksum."""
        checksum = 0
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                checksum += (data[i] & 0xFF) | ((data[i + 1] & 0xFF) << 8)
            else:
                checksum += (data[i] & 0xFF)
        return checksum & 0xFFFF
    
    def _decode_response(self, response: bytes) -> Optional[Dict]:
        """Decode device response."""
        if not response:
            return None
        
        try:
            # Parse response based on command type
            data = {
                'raw': response,
                'session_id': self.session_id,
                'reply_id': self.reply_id
            }
            
            # Add command-specific decoding
            if len(response) >= 4:
                data['command'] = struct.unpack('<I', response[:4])[0]
            
            return data
            
        except Exception as e:
            logger.error(f"Error decoding response: {e}")
            return None
    
    def _get_device_info(self):
        """Get device information."""
        try:
            # Get firmware version
            response = self._send_command(self.COMMAND_GET_FIRMWARE_VERSION, b'')
            if response and len(response) >= 20:
                self.firmware_version = response.decode('utf-8', errors='ignore').strip('\x00')
            
            # Get serial number
            response = self._send_command(self.COMMAND_GET_SERIAL_NUMBER, b'')
            if response and len(response) >= 16:
                self.serial_number = response.decode('utf-8', errors='ignore').strip('\x00')
            
            # Get device name
            response = self._send_command(self.COMMAND_GET_DEVICE_NAME, b'')
            if response and len(response) >= 16:
                self.model = response.decode('utf-8', errors='ignore').strip('\x00')
            
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
    
    def _get_device_stats(self):
        """Get device statistics."""
        try:
            # Get user count
            response = self._send_command(1120, b'')  # Read all user IDs
            if response and len(response) >= 4:
                self.user_count = struct.unpack('<I', response[:4])[0]
            
            # Get template count
            response = self._send_command(1121, b'')  # Read all templates
            if response and len(response) >= 4:
                self.fp_count = struct.unpack('<I', response[:4])[0]
            
            # Get log count
            response = self._send_command(1503, b'')  # Read log count
            if response and len(response) >= 4:
                self.log_count = struct.unpack('<I', response[:4])[0]
                
        except Exception as e:
            logger.error(f"Error getting device stats: {e}")
    
    def _start_keep_alive(self):
        """Start keep-alive thread."""
        self.keep_alive = True
        
        def keep_alive():
            while self.keep_alive and self.connected:
                try:
                    # Send keep-alive command
                    self._send_command(0, b'')
                    time.sleep(30)  # Send every 30 seconds
                except:
                    self.connected = False
                    break
        
        self.connection_thread = threading.Thread(target=keep_alive, daemon=True)
        self.connection_thread.start()
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users from the device.
        
        Returns:
            List of user dictionaries
        """
        if not self.connected:
            logger.error("Device not connected")
            return []
        
        users = []
        try:
            logger.info("Fetching users from ZKTeco device...")
            
            # Get all user IDs
            response = self._send_command(self.COMMAND_READ_ALL_USER_ID, b'')
            
            if response and len(response) > 4:
                # Parse user IDs
                user_count = struct.unpack('<I', response[:4])[0]
                
                offset = 4
                for i in range(user_count):
                    if offset + 28 > len(response):
                        break
                    
                    # Parse user record (format varies by model)
                    user_id = response[offset:offset+9].decode('utf-8', errors='ignore').strip('\x00')
                    name = response[offset+9:offset+17].decode('utf-8', errors='ignore').strip('\x00')
                    privilege = response[offset+27]
                    
                    user = {
                        'id': user_id,
                        'user_id': user_id,
                        'name': name if name else f"User_{user_id}",
                        'privilege': privilege,
                        'card_number': '',
                        'fingerprint_count': 0,
                        'password': ''
                    }
                    
                    # Get fingerprint count for this user
                    fp_count = self._get_user_fp_count(user_id)
                    user['fingerprint_count'] = fp_count
                    
                    users.append(user)
                    offset += 28
            
            logger.info(f"[OK] Retrieved {len(users)} users from ZKTeco device")
            return users
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting users: {e}")
            return []
    
    def _get_user_fp_count(self, user_id: str) -> int:
        """Get fingerprint count for a user."""
        try:
            # Command to get user template info
            data = user_id.encode('utf-8').ljust(9, b'\x00')
            response = self._send_command(1121, data)
            
            if response and len(response) >= 4:
                return struct.unpack('<I', response[:4])[0]
            
        except Exception as e:
            logger.debug(f"Error getting FP count for user {user_id}: {e}")
        
        return 0
    
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
            # Command to get specific user
            data = user_id.encode('utf-8').ljust(9, b'\x00')
            response = self._send_command(1120, data)
            
            if response and len(response) >= 28:
                # Parse user record
                user_id = response[0:9].decode('utf-8', errors='ignore').strip('\x00')
                name = response[9:17].decode('utf-8', errors='ignore').strip('\x00')
                privilege = response[27]
                
                user = {
                    'id': user_id,
                    'user_id': user_id,
                    'name': name if name else f"User_{user_id}",
                    'privilege': privilege,
                    'card_number': '',
                    'fingerprint_count': self._get_user_fp_count(user_id),
                    'password': ''
                }
                
                return user
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
        
        return None
    
    def add_user(self, user_id: str, name: str, privilege: int = 0, 
            password: Optional[str] = None, card_number: Optional[str] = None) -> bool:
        """
        Add a user to the device.
        
        Args:
            user_id: User ID
            name: User name
            privilege: Privilege level (0=user, 1=enroller, 2=admin)
            password: PIN code
            card_number: Card number
            
        Returns:
            True if successful
        """
        if not self.connected:
            logger.error("Device not connected")
            return False
        
        try:
            # Prepare user data
            # Format: UserID(9) + Name(8) + Password(8) + Privilege(1) + Enabled(1)
            user_data = user_id.encode('utf-8').ljust(9, b'\x00')
            user_data += name.encode('utf-8')[:8].ljust(8, b'\x00')
            
            if password:
                user_data += password.encode('utf-8')[:8].ljust(8, b'\x00')
            else:
                user_data += b'\x00' * 8
            
            user_data += struct.pack('<B', privilege)  # Privilege
            user_data += b'\x01'  # Enabled
            
            # Add card if provided
            if card_number:
                # Card format depends on model
                card_data = card_number.encode('utf-8').ljust(10, b'\x00')
                user_data += card_data
            
            response = self._send_command(self.COMMAND_UPLOAD_USER, user_data)
            
            if response:
                logger.info(f"[OK] Added user {name} (ID: {user_id})")
                self.user_count += 1
                return True
            else:
                logger.error(f"[ERROR] Failed to add user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error adding user: {e}")
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
            data = user_id.encode('utf-8').ljust(9, b'\x00')
            response = self._send_command(self.COMMAND_DELETE_USER, data)
            
            if response:
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
            response = self._send_command(self.COMMAND_CLEAR_DATA, b'')
            
            if response:
                logger.info("[OK] Deleted all users")
                self.user_count = 0
                self.fp_count = 0
                return True
            else:
                logger.error("[ERROR] Failed to delete all users")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error deleting all users: {e}")
            return False
    
    def enroll_fingerprint(self, user_id: str, finger_id: int = 0) -> bool:
        """
        Enroll a fingerprint for a user.
        
        Args:
            user_id: User ID
            finger_id: Finger index (0-9)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Start fingerprint capture
            response = self._send_command(self.COMMAND_CAPTURE_FINGER, b'')
            
            if not response:
                logger.error("Failed to start fingerprint capture")
                return False
            
            # Wait for fingerprint
            time.sleep(2)
            
            # Upload fingerprint template
            data = user_id.encode('utf-8').ljust(9, b'\x00')
            data += struct.pack('<B', finger_id)
            
            response = self._send_command(1302, data)  # Upload template
            
            if response:
                logger.info(f"[OK] Enrolled fingerprint for user {user_id}, finger {finger_id}")
                return True
            else:
                logger.error("Failed to upload fingerprint")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error enrolling fingerprint: {e}")
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
                return self.set_device_time(params.get('datetime') if params else None)
            elif command == "get_status":
                return self.get_device_status()
            elif command == "restart":
                return self.restart_device()
            elif command == "enable_device":
                return self._send_command(self.COMMAND_ENABLE_DEVICE, b'')
            elif command == "disable_device":
                return self._send_command(self.COMMAND_DISABLE_DEVICE, b'')
            elif command == "test_fingerprint":
                return self._send_command(self.COMMAND_TEST_TEMP, b'')
            else:
                logger.warning(f"Unknown command: {command}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending command {command}: {e}")
            return None
    
    def open_door(self, door_id: int = 1) -> bool:
        """
        Open a specific door.
        
        Args:
            door_id: Door number (usually 1 for single door)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Command to open door
            data = struct.pack('<I', door_id)
            response = self._send_command(1400, data)  # Open door command
            
            if response:
                logger.info(f"[OK] Door {door_id} opened")
                return True
            else:
                logger.error(f"[ERROR] Failed to open door {door_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error opening door: {e}")
            return False
    
    def get_attendance_logs(self, start_time: Optional[datetime] = None, 
                       end_time: Optional[datetime] = None) -> List[Dict]:
        """
        Get attendance logs from device.
        
        Args:
            start_time: Start time for logs
            end_time: End time for logs
            
        Returns:
            List of attendance log dictionaries
        """
        if not self.connected:
            return []
        
        logs = []
        try:
            # Command to read attendance logs
            response = self._send_command(1501, b'')  # Read logs
            
            if response and len(response) > 8:
                log_count = struct.unpack('<I', response[:4])[0]
                
                offset = 4
                for i in range(log_count):
                    if offset + 16 > len(response):
                        break
                    
                    # Parse log entry (format varies by model)
                    user_id = response[offset:offset+9].decode('utf-8', errors='ignore').strip('\x00')
                    timestamp_raw = struct.unpack('<I', response[offset+9:offset+13])[0]
                    
                    # Convert timestamp (ZKTeco uses custom format)
                    if timestamp_raw > 0:
                        log_time = datetime(2000, 1, 1) + timedelta(seconds=timestamp_raw)
                    else:
                        log_time = datetime.now()
                    
                    log = {
                        'user_id': user_id,
                        'timestamp': log_time.isoformat(),
                        'datetime': log_time,
                        'status': response[offset+13],
                        'verified': response[offset+14],
                        'device_id': self.serial_number
                    }
                    
                    logs.append(log)
                    offset += 16
            
            logger.info(f"[OK] Retrieved {len(logs)} attendance logs")
            return logs
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting attendance logs: {e}")
            return []
    
    def get_device_time(self) -> Optional[datetime]:
        """
        Get device current time.
        
        Returns:
            Device datetime or None
        """
        if not self.connected:
            return None
        
        try:
            response = self._send_command(self.COMMAND_GET_TIME, b'')
            
            if response and len(response) >= 4:
                timestamp = struct.unpack('<I', response[:4])[0]
                # ZKTeco timestamp is seconds since 2000-01-01
                return datetime(2000, 1, 1) + timedelta(seconds=timestamp)
            
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
        
        if not dt:
            dt = datetime.now()
        
        try:
            # Convert to ZKTeco timestamp
            base = datetime(2000, 1, 1)
            timestamp = int((dt - base).total_seconds())
            
            data = struct.pack('<I', timestamp)
            response = self._send_command(self.COMMAND_SET_TIME, data)
            
            if response:
                logger.info(f"[OK] Device time set to {dt}")
                return True
            else:
                logger.error("[ERROR] Failed to set device time")
                return False
                
        except Exception as e:
            logger.error(f"Error setting device time: {e}")
            return False
    
    def restart_device(self) -> bool:
        """
        Restart the device.
        
        Returns:
            True if restart command sent successfully
        """
        if not self.connected:
            return False
        
        try:
            response = self._send_command(1401, b'')  # Restart command
            
            if response:
                logger.info("[OK] Device restart command sent")
                self.connected = False
                return True
            else:
                logger.error("[ERROR] Failed to send restart command")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error restarting device: {e}")
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
            'user_count': self.user_count,
            'fingerprint_count': self.fp_count,
            'log_count': self.log_count,
            'session_id': self.session_id
        }
        
        # Get device state
        try:
            response = self._send_command(1105, b'')  # Get device state
            
            if response and len(response) >= 4:
                state = struct.unpack('<I', response[:4])[0]
                status['device_state'] = state
                status['enabled'] = (state == 1)
                
        except:
            pass
        
        return status
    
    def __str__(self) -> str:
        status = "Connected" if self.connected else "Disconnected"
        return f"ZKTeco {self.model} at {self.ip}:{self.port} [{status}]"

from datetime import timedelta  # Add this import at the top