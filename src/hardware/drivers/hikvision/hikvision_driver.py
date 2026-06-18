"""
Real Hikvision Access Control Device Driver
Uses Hikvision ISAPI protocol
"""

import requests
import base64
import hashlib
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List, Tuple, cast
from datetime import datetime
from requests.auth import HTTPDigestAuth
from ..base_device import BaseDevice

import logging
logger = logging.getLogger(__name__)

class HikvisionDevice(BaseDevice):
    """
    Real Hikvision Access Control Device Driver
    Supports:
    - Hikvision Access Control Panels
    - Hikvision Door Controllers
    - Hikvision Face Recognition Terminals
    - Models: DS-K series, DS-2 series, etc.
    """
    
    def __init__(self, ip: str, port: int = 80, username: str = 'admin', password: str = 'admin123'):
        """
        Initialize Hikvision device.
        
        Args:
            ip: Device IP address
            port: HTTP port (default 80, can be 443 for HTTPS)
            username: Admin username
            password: Admin password
        """
        super().__init__(ip, port, username, password)
        self.device_type = "hikvision"
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.auth = HTTPDigestAuth(username, password)
        self.timeout = 10
        self.door_count = 0
        self.card_count = 0
        self.user_count = 0
        self.device_info = {}
        
    def connect(self) -> bool:
        """
        Connect to Hikvision device using ISAPI protocol.
        
        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to Hikvision device at {self.ip}:{self.port}")
            
            # Test connection with device info request
            url = f"{self.base_url}/ISAPI/System/deviceInfo"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                # Parse device info from XML
                root = ET.fromstring(response.text)
                
                # Extract device information
                self.model = self._get_xml_value(root, 'model') or "Unknown"
                self.serial_number = self._get_xml_value(root, 'serialNumber') or ""
                self.firmware_version = self._get_xml_value(root, 'firmwareVersion') or ""
                self.device_name = self._get_xml_value(root, 'deviceName') or ""
                
                # Store all device info
                self.device_info = {
                    'model': self.model,
                    'serial': self.serial_number,
                    'firmware': self.firmware_version,
                    'name': self.device_name,
                    'mac': self._get_xml_value(root, 'macAddress'),
                    'manufacturer': self._get_xml_value(root, 'manufacturer'),
                    'device_type': self._get_xml_value(root, 'deviceType')
                }
                
                # Get door count
                self._get_door_count()
                
                # Get card count
                self._get_card_count()
                
                # Get user count
                self._get_user_count()
                
                self.connected = True
                logger.info(f"[OK] Connected to Hikvision {self.model} (SN: {self.serial_number})")
                logger.info(f"   Firmware: {self.firmware_version}")
                logger.info(f"   Doors: {self.door_count}, Cards: {self.card_count}, Users: {self.user_count}")
                return True
            else:
                logger.error(f"[ERROR] Failed to connect. Status code: {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error(f"[ERROR] Connection error: Device at {self.ip}:{self.port} not reachable")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"[ERROR] Connection timeout: Device at {self.ip}:{self.port} not responding")
            return False
        except ET.ParseError as e:
            logger.error(f"[ERROR] XML parsing error: {e}")
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
        self.session.close()
        self.connected = False
        logger.info(f"Disconnected from Hikvision device at {self.ip}:{self.port}")
        return True
    
    def _get_xml_value(self, root: ET.Element, path: str) -> Optional[str]:
        """Get value from XML element."""
        try:
            element = root.find(f'.//{path}')
            return element.text if element is not None else None
        except:
            return None
    
    def _get_door_count(self):
        """Get number of doors on the controller."""
        try:
            url = f"{self.base_url}/ISAPI/accessControl/doorInfo"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                doors = root.findall('.//Door')
                self.door_count = len(doors)
            else:
                # Try alternative endpoint
                url = f"{self.base_url}/ISAPI/AccessControl/Door/param"
                response = self.session.get(url, auth=self.auth, timeout=self.timeout)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    doors = root.findall('.//Door')
                    self.door_count = len(doors)
                else:
                    self.door_count = 1  # Assume at least 1 door
        except Exception as e:
            logger.warning(f"Could not determine door count: {e}")
            self.door_count = 1
    
    def _get_card_count(self):
        """Get number of cards in the system."""
        try:
            url = f"{self.base_url}/ISAPI/accessControl/cardInfo/count"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                count_elem = root.find('.//cardNumber')
                if count_elem is not None and count_elem.text is not None:
                    self.card_count = int(count_elem.text)
                else:
                    self.card_count = 0    
        except:
            self.card_count = 0
    
    def _get_user_count(self):
        """Get number of users in the system."""
        try:
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/count"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                count_elem = root.find('.//userNumber')
                if count_elem is not None and count_elem.text is not None:
                    self.user_count = int(count_elem.text)
                else:
                    self.user_count = 0    
        except:
            self.user_count = 0
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users/cards from the device.
        
        Returns:
            List of user dictionaries
        """
        if not self.connected:
            logger.error("Device not connected")
            return []
        
        users = []
        try:
            logger.info("Fetching users from Hikvision device...")
            
            # Try card info search first
            users = self._get_users_from_cards()
            
            # If no users found, try user info search
            if not users:
                users = self._get_users_from_userinfo()
            
            logger.info(f"[OK] Retrieved {len(users)} users from Hikvision device")
            return users
            
        except Exception as e:
            logger.error(f"[ERROR] Error getting users: {e}")
            return []
    
    def _get_users_from_cards(self) -> List[Dict[str, Any]]:
        """Get users from card info endpoint."""
        users = []
        try:
            # Hikvision uses pagination, fetch in chunks
            page_size = 100
            start = 0
            
            while True:
                # Generate search ID safely
                current_time = int(time.time())
                search_id = f"search_{current_time}_{start}"
                
                url = f"{self.base_url}/ISAPI/accessControl/cardInfo/search"
                
                # Create search XML
                search_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
                <cardInfoSearchCondition>
                    <searchID>{search_id}</searchID>
                    <searchResultPosition>{start}</searchResultPosition>
                    <maxResults>{page_size}</maxResults>
                </cardInfoSearchCondition>'''
                
                headers = {'Content-Type': 'application/xml'}
                response = self.session.post(url, auth=self.auth, data=search_xml, 
                                           headers=headers, timeout=self.timeout)
                
                if response.status_code != 200:
                    break
                
                root = ET.fromstring(response.text)
                cards = root.findall('.//CardInfo')
                
                if not cards:
                    break
                
                for card in cards:
                    # Safely convert XML values to strings with defaults
                    employee_no = self._get_xml_value(card, 'employeeNo')
                    user_id = employee_no if employee_no is not None else ""
                    
                    card_no = self._get_xml_value(card, 'cardNo')
                    card_id = card_no if card_no is not None else ""
                    
                    name_val = self._get_xml_value(card, 'name')
                    name = name_val if name_val is not None else f"User_{user_id}"
                    
                    dept_val = self._get_xml_value(card, 'department')
                    department = dept_val if dept_val is not None else ""
                    
                    status_val = self._get_xml_value(card, 'status')
                    status = status_val if status_val is not None else "unknown"
                    
                    card_type_val = self._get_xml_value(card, 'cardType')
                    card_type = card_type_val if card_type_val is not None else "unknown"
                    
                    valid_from_val = self._get_xml_value(card, 'validFrom')
                    valid_start = valid_from_val if valid_from_val is not None else ""
                    
                    valid_to_val = self._get_xml_value(card, 'validTo')
                    valid_end = valid_to_val if valid_to_val is not None else ""
                    
                    pin_val = self._get_xml_value(card, 'password')
                    pin_code = pin_val if pin_val is not None else ""
                    
                    user: Dict[str, Any] = {
                        'id': user_id,
                        'card_id': card_id,
                        'employee_id': user_id,
                        'name': name,
                        'department': department,
                        'status': status,
                        'card_type': card_type,
                        'valid_start': valid_start,
                        'valid_end': valid_end,
                        'pin_code': pin_code,
                        'door_rights': [],
                        'source': 'card_info'
                    }
                    
                    # Get door permissions
                    doors = card.findall('.//doorRight/doorName')
                    door_list = [d.text for d in doors if d.text]
                    user['door_rights'] = door_list
                    
                    users.append(user)
                
                start += page_size
            
        except Exception as e:
            logger.debug(f"Card info search failed: {e}")
        
        return users
    
    def _get_users_from_userinfo(self) -> List[Dict[str, Any]]:
        """Get users from user info endpoint."""
        users = []
        try:
            # Generate search ID safely
            current_time = int(time.time())
            search_id = f"user_search_{current_time}"
            
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Search"
            
            search_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <UserInfoSearchCondition>
                <searchID>{search_id}</searchID>
                <maxResults>100</maxResults>
            </UserInfoSearchCondition>'''
            
            headers = {'Content-Type': 'application/xml'}
            response = self.session.post(url, auth=self.auth, data=search_xml,
                                       headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                user_infos = root.findall('.//UserInfo')
                
                for user_info in user_infos:
                    # Safely convert XML values to strings with defaults
                    employee_no = self._get_xml_value(user_info, 'employeeNo')
                    user_id = employee_no if employee_no is not None else ""
                    
                    name_val = self._get_xml_value(user_info, 'name')
                    name = name_val if name_val is not None else f"User_{user_id}"
                    
                    dept_val = self._get_xml_value(user_info, 'department')
                    department = dept_val if dept_val is not None else ""
                    
                    status_val = self._get_xml_value(user_info, 'status')
                    status = status_val if status_val is not None else "unknown"
                    
                    user_type_val = self._get_xml_value(user_info, 'userType')
                    user_type = user_type_val if user_type_val is not None else "normal"
                    
                    valid_from_val = self._get_xml_value(user_info, 'validFrom')
                    valid_start = valid_from_val if valid_from_val is not None else ""
                    
                    valid_to_val = self._get_xml_value(user_info, 'validTo')
                    valid_end = valid_to_val if valid_to_val is not None else ""
                    
                    user: Dict[str, Any] = {
                        'id': user_id,
                        'employee_id': user_id,
                        'name': name,
                        'department': department,
                        'status': status,
                        'user_type': user_type,
                        'valid_start': valid_start,
                        'valid_end': valid_end,
                        'door_rights': [],
                        'source': 'user_info',
                        'card_id': ""  # Initialize with default
                    }
                    
                    # Get associated cards
                    cards = user_info.findall('.//card/cardNo')
                    if cards and cards[0].text:
                        user['card_id'] = cards[0].text
                    
                    users.append(user)
        
        except Exception as e:
            logger.debug(f"User info search failed: {e}")
        
        return users
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific user by ID.
        
        Args:
            user_id: User/Employee ID
            
        Returns:
            User dictionary or None
        """
        if not self.connected:
            return None
        
        try:
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={user_id}"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                # Convert Optional[str] to str with proper handling
                emp_no = self._get_xml_value(root, 'employeeNo')
                user_id_val = emp_no if emp_no is not None else ""
                
                name_val = self._get_xml_value(root, 'name')
                name = name_val if name_val is not None else ""
                
                dept_val = self._get_xml_value(root, 'department')
                department = dept_val if dept_val is not None else ""
                
                status_val = self._get_xml_value(root, 'status')
                status = status_val if status_val is not None else "unknown"
                
                user_type_val = self._get_xml_value(root, 'userType')
                user_type = user_type_val if user_type_val is not None else "normal"
                
                valid_from_val = self._get_xml_value(root, 'validFrom')
                valid_start = valid_from_val if valid_from_val is not None else ""
                
                valid_to_val = self._get_xml_value(root, 'validTo')
                valid_end = valid_to_val if valid_to_val is not None else ""
                
                user: Dict[str, Any] = {
                    'id': user_id_val,
                    'name': name,
                    'department': department,
                    'status': status,
                    'user_type': user_type,
                    'valid_start': valid_start,
                    'valid_end': valid_end,
                }
                
                # Get cards
                cards = []
                for card in root.findall('.//card'):
                    card_no_val = self._get_xml_value(card, 'cardNo')
                    card_no = card_no_val if card_no_val is not None else ""
                    
                    card_type_val = self._get_xml_value(card, 'cardType')
                    card_type = card_type_val if card_type_val is not None else "unknown"
                    
                    card_info = {
                        'card_no': card_no,
                        'card_type': card_type,
                    }
                    cards.append(card_info)
                
                user['cards'] = cards
                
                return user
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
        
        return None
    
    def add_user(self, user_id: str, name: str, card_number: Optional[str] = None, 
                 pin_code: Optional[str] = None, door_rights: Optional[List[int]] = None,
                 department: str = "", valid_start: Optional[str] = None,
                 valid_end: Optional[str] = None) -> bool:
        """
        Add a user/card to the device.
        
        Args:
            user_id: User/Employee ID
            name: User name
            card_number: Card number (if None, auto-generate)
            pin_code: PIN code for verification
            door_rights: List of door IDs this user can access
            department: Department name
            valid_start: Valid from date (YYYY-MM-DD)
            valid_end: Valid to date (YYYY-MM-DD)
            
        Returns:
            True if successful
        """
        if not self.connected:
            logger.error("Device not connected")
            return False
        
        try:
            # Generate card number if not provided
            if not card_number:
                card_number = self._generate_card_number()
            
            # Format dates
            if not valid_start:
                valid_start = datetime.now().strftime('%Y-%m-%d')
            if not valid_end:
                valid_end = (datetime.now().replace(year=datetime.now().year + 5)
                           .strftime('%Y-%m-%d'))
            
            # Default door rights
            if not door_rights:
                door_rights = [1]
            
            # Build door rights XML
            door_rights_xml = ""
            for door_id in door_rights:
                door_rights_xml += f'<doorRight><doorNo>{door_id}</doorNo></doorRight>'
            
            # Create user info XML
            user_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <UserInfo>
                <employeeNo>{user_id}</employeeNo>
                <name>{name}</name>
                <userType>normal</userType>
                <department>{department}</department>
                <status>0</status>
                <Valid>
                    <beginTime>{valid_start}T00:00:00</beginTime>
                    <endTime>{valid_end}T23:59:59</endTime>
                </Valid>
                <doorRight>
                    {door_rights_xml}
                </doorRight>
                <card>
                    <cardNo>{card_number}</cardNo>
                    <cardType>normalCard</cardType>
                </card>
            </UserInfo>'''
            
            # Add PIN if provided
            if pin_code:
                user_xml = user_xml.replace('</UserInfo>', f'<password>{pin_code}</password></UserInfo>')
            
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record"
            headers = {'Content-Type': 'application/xml'}
            
            response = self.session.post(url, auth=self.auth, data=user_xml,
                                       headers=headers, timeout=self.timeout)
            
            if response.status_code in [200, 201]:
                logger.info(f"[OK] Added user {name} (ID: {user_id}, Card: {card_number})")
                self.user_count += 1
                self.card_count += 1
                return True
            else:
                logger.error(f"[ERROR] Failed to add user. Status: {response.status_code}")
                logger.debug(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error adding user: {e}")
            return False
    
    def _generate_card_number(self) -> str:
        """Generate a unique card number."""
        # Format: 8-digit number starting with 1
        import random
        timestamp = int(time.time()) % 10000000
        return f"1{timestamp:07d}"
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        Update an existing user.
        
        Args:
            user_id: User ID to update
            **kwargs: Fields to update (name, department, etc.)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Get existing user first
            existing_user = self.get_user(user_id)
            if not existing_user:
                logger.error(f"User {user_id} not found")
                return False
            
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Modify?format=json"
            
            # Build update XML
            update_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <UserInfo>
                <employeeNo>{user_id}</employeeNo>'''
            
            if 'name' in kwargs:
                update_xml += f'<name>{kwargs["name"]}</name>'
            if 'department' in kwargs:
                update_xml += f'<department>{kwargs["department"]}</department>'
            if 'status' in kwargs:
                update_xml += f'<status>{kwargs["status"]}</status>'
            
            update_xml += '</UserInfo>'
            
            headers = {'Content-Type': 'application/xml'}
            response = self.session.put(url, auth=self.auth, data=update_xml,
                                      headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
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
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Delete?format=json"
            
            delete_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <UserInfoDelCond>
                <EmployeeNoList>
                    <EmployeeNo>{user_id}</EmployeeNo>
                </EmployeeNoList>
            </UserInfoDelCond>'''
            
            headers = {'Content-Type': 'application/xml'}
            response = self.session.put(url, auth=self.auth, data=delete_xml,
                                      headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info(f"[OK] Deleted user {user_id}")
                self.user_count -= 1
                return True
            else:
                logger.error(f"[ERROR] Failed to delete user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error deleting user: {e}")
            return False
    
    def delete_card(self, card_number: str) -> bool:
        """
        Delete a card from the device.
        
        Args:
            card_number: Card number to delete
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            url = f"{self.base_url}/ISAPI/accessControl/cardInfo/delete"
            
            delete_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <CardInfoDelCondition>
                <cardNo>{card_number}</cardNo>
            </CardInfoDelCondition>'''
            
            headers = {'Content-Type': 'application/xml'}
            response = self.session.put(url, auth=self.auth, data=delete_xml,
                                      headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info(f"[OK] Deleted card {card_number}")
                self.card_count -= 1
                return True
            else:
                logger.error(f"[ERROR] Failed to delete card {card_number}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error deleting card: {e}")
            return False
    
    def delete_all_users(self) -> bool:
        """Delete all users from device."""
        if not self.connected:
            return False
        
        try:
            users = self.get_users()
            success_count = 0
            
            for user in users:
                user_id = user.get('id')
                if user_id and self.delete_user(str(user_id)):
                    success_count += 1
                time.sleep(0.1)  # Small delay to avoid overwhelming the device
            
            logger.info(f"[OK] Deleted {success_count}/{len(users)} users")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"[ERROR] Error deleting all users: {e}")
            return False
    
    def send_command(self, command: str, params: Optional[Dict] = None) -> Any:
        """
        Send a raw command to the device.
        
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
            elif command == "get_status":
                return self.get_device_status()
            elif command == "reboot":
                return self.reboot_device()
            elif command == "get_time":
                return self.get_device_time()
            elif command == "set_time":
                dt = params.get('datetime') if params else None
                return self.set_device_time(dt)
            elif command == "get_config":
                return self.get_device_config()
            else:
                # Generic command
                url = f"{self.base_url}/ISAPI/{command}"
                response = self.session.get(url, auth=self.auth, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.text
                else:
                    logger.error(f"Command failed: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error sending command {command}: {e}")
            return None
    
    def open_door(self, door_id: int = 1, duration: int = 3) -> bool:
        """
        Open a specific door.
        
        Args:
            door_id: Door number (1-based)
            duration: How long to hold door open (seconds)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Try different endpoints based on model
            endpoints = [
                f"/ISAPI/accessControl/door/{door_id}/open",
                f"/ISAPI/AccessControl/Door/{door_id}/open",
                f"/ISAPI/accessControl/remoteControl/door/{door_id}/open"
            ]
            
            for endpoint in endpoints:
                url = f"{self.base_url}{endpoint}"
                response = self.session.put(url, auth=self.auth, timeout=self.timeout)
                
                if response.status_code == 200:
                    logger.info(f"[OK] Door {door_id} opened for {duration} seconds")
                    return True
            
            logger.error(f"[ERROR] Failed to open door {door_id}")
            return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error opening door: {e}")
            return False
    
    def get_door_status(self, door_id: int = 1) -> Dict[str, Any]:
        """
        Get door status.
        
        Args:
            door_id: Door number
            
        Returns:
            Door status dictionary
        """
        if not self.connected:
            return {}
        
        try:
            url = f"{self.base_url}/ISAPI/accessControl/door/{door_id}/status"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                # Convert Optional[str] to str with proper handling
                door_status_val = self._get_xml_value(root, 'doorStatus')
                door_status = door_status_val if door_status_val is not None else "unknown"
                
                online_val = self._get_xml_value(root, 'online')
                online = online_val if online_val is not None else "unknown"
                
                lock_status_val = self._get_xml_value(root, 'lockStatus')
                lock_status = lock_status_val if lock_status_val is not None else "unknown"
                
                status: Dict[str, Any] = {
                    'door_id': door_id,
                    'door_status': door_status,
                    'online': online,
                    'lock_status': lock_status
                }
                
                return status
            else:
                logger.error(f"Failed to get door status: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting door status: {e}")
            return {}
    
    def get_events(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, 
                   max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Get access events from device.
        
        Args:
            start_time: Start time for events
            end_time: End time for events
            max_results: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self.connected:
            return []
        
        if not start_time:
            start_time = datetime.now().replace(hour=0, minute=0, second=0)
        if not end_time:
            end_time = datetime.now()
        
        events = []
        try:
            # Generate search ID safely
            current_time = int(time.time())
            search_id = f"event_search_{current_time}"
            
            url = f"{self.base_url}/ISAPI/AccessControl/AccessEvent"
            
            # Format times: YYYY-MM-DDTHH:MM:SS
            start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')
            end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S')
            
            search_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <AccessEventCond>
                <searchID>{search_id}</searchID>
                <timeRangeList>
                    <timeRange>
                        <startTime>{start_str}</startTime>
                        <endTime>{end_str}</endTime>
                    </timeRange>
                </timeRangeList>
                <maxResults>{max_results}</maxResults>
            </AccessEventCond>'''
            
            headers = {'Content-Type': 'application/xml'}
            response = self.session.post(url, auth=self.auth, data=search_xml,
                                       headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                for event in root.findall('.//AccessEvent'):
                    # Convert Optional[str] to str with proper handling
                    serial_no_val = self._get_xml_value(event, 'serialNo')
                    event_id = serial_no_val if serial_no_val is not None else ""
                    
                    card_no_val = self._get_xml_value(event, 'cardNo')
                    card_number = card_no_val if card_no_val is not None else ""
                    
                    emp_no_val = self._get_xml_value(event, 'employeeNo')
                    employee_id = emp_no_val if emp_no_val is not None else ""
                    
                    door_no_val = self._get_xml_value(event, 'doorNo')
                    door_id = door_no_val if door_no_val is not None else ""
                    
                    door_name_val = self._get_xml_value(event, 'doorName')
                    door_name = door_name_val if door_name_val is not None else ""
                    
                    event_type_val = self._get_xml_value(event, 'eventType')
                    event_type = event_type_val if event_type_val is not None else ""
                    
                    event_type_name_val = self._get_xml_value(event, 'eventTypeName')
                    event_type_name = event_type_name_val if event_type_name_val is not None else ""
                    
                    time_val = self._get_xml_value(event, 'time')
                    event_time = time_val if time_val is not None else ""
                    
                    status_val = self._get_xml_value(event, 'status')
                    status = status_val if status_val is not None else ""
                    
                    status_name_val = self._get_xml_value(event, 'statusName')
                    status_name = status_name_val if status_name_val is not None else ""
                    
                    event_data: Dict[str, Any] = {
                        'id': event_id,
                        'card_number': card_number,
                        'employee_id': employee_id,
                        'door_id': door_id,
                        'door_name': door_name,
                        'event_type': event_type,
                        'event_type_name': event_type_name,
                        'event_time': event_time,
                        'status': status,
                        'status_name': status_name,
                        'device_id': self.serial_number
                    }
                    events.append(event_data)
                
                logger.info(f"[OK] Retrieved {len(events)} events from {start_str} to {end_str}")
            else:
                logger.warning(f"Failed to get events. Status: {response.status_code}")
                
        except Exception as e:
            logger.error(f"[ERROR] Error getting events: {e}")
        
        return events
    
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get device status.
        
        Returns:
            Device status dictionary
        """
        if not self.connected:
            return {}
        
        status: Dict[str, Any] = {
            'connected': self.connected,
            'device_type': self.device_type,
            'model': self.model,
            'serial': self.serial_number,
            'firmware': self.firmware_version,
            'ip': self.ip,
            'port': self.port,
            'door_count': self.door_count,
            'card_count': self.card_count,
            'user_count': self.user_count
        }
        
        try:
            # Get device health status
            url = f"{self.base_url}/ISAPI/System/status"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                device_status_val = self._get_xml_value(root, 'deviceStatus')
                device_status = device_status_val if device_status_val is not None else "unknown"
                
                uptime_val = self._get_xml_value(root, 'uptime')
                uptime = uptime_val if uptime_val is not None else "0"
                
                status['device_status'] = device_status
                status['uptime'] = uptime
                
        except Exception as e:
            logger.debug(f"Could not get detailed status: {e}")
        
        return status
    
    def reboot_device(self) -> bool:
        """
        Reboot the device.
        
        Returns:
            True if reboot command sent successfully
        """
        if not self.connected:
            return False
        
        try:
            url = f"{self.base_url}/ISAPI/System/reboot"
            response = self.session.put(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info("[OK] Device reboot command sent")
                self.connected = False  # Device will reboot
                return True
            else:
                logger.error("[ERROR] Failed to send reboot command")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Error rebooting device: {e}")
            return False
    
    def get_device_time(self) -> Optional[datetime]:
        """
        Get device current time.
        
        Returns:
            Device datetime or None
        """
        if not self.connected:
            return None
        
        try:
            url = f"{self.base_url}/ISAPI/System/time"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                time_str = self._get_xml_value(root, 'localTime')
                if time_str:
                    return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
            
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
            time_str = dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            time_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Time>
                <localTime>{time_str}</localTime>
                <timeZone>+8:00</timeZone>
            </Time>'''
            
            url = f"{self.base_url}/ISAPI/System/time"
            headers = {'Content-Type': 'application/xml'}
            response = self.session.put(url, auth=self.auth, data=time_xml,
                                      headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                logger.info(f"[OK] Device time set to {time_str}")
                return True
            else:
                logger.error("[ERROR] Failed to set device time")
                return False
                
        except Exception as e:
            logger.error(f"Error setting device time: {e}")
            return False
    
    def get_device_config(self) -> Dict[str, Any]:
        """
        Get device configuration.
        
        Returns:
            Device configuration dictionary
        """
        if not self.connected:
            return {}
        
        config: Dict[str, Any] = {}
        
        try:
            # Get network config
            url = f"{self.base_url}/ISAPI/System/Network/interfaces/1"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                ip_addr_val = self._get_xml_value(root, 'ipAddress')
                ip_addr = ip_addr_val if ip_addr_val is not None else ""
                
                subnet_val = self._get_xml_value(root, 'subnetMask')
                subnet = subnet_val if subnet_val is not None else ""
                
                gateway_val = self._get_xml_value(root, 'gateway')
                gateway = gateway_val if gateway_val is not None else ""
                
                mac_val = self._get_xml_value(root, 'macAddress')
                mac = mac_val if mac_val is not None else ""
                
                config['network'] = {
                    'ip': ip_addr,
                    'subnet': subnet,
                    'gateway': gateway,
                    'mac': mac
                }
            
            # Get access control config
            url = f"{self.base_url}/ISAPI/AccessControl/param"
            response = self.session.get(url, auth=self.auth, timeout=self.timeout)
            
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                verify_mode_val = self._get_xml_value(root, 'verifyMode')
                verify_mode = verify_mode_val if verify_mode_val is not None else ""
                
                door_open_time_val = self._get_xml_value(root, 'doorOpenTime')
                door_open_time = door_open_time_val if door_open_time_val is not None else ""
                
                alarm_time_val = self._get_xml_value(root, 'alarmTime')
                alarm_time = alarm_time_val if alarm_time_val is not None else ""
                
                config['access_control'] = {
                    'verify_mode': verify_mode,
                    'door_open_time': door_open_time,
                    'alarm_time': alarm_time
                }
            
        except Exception as e:
            logger.error(f"Error getting device config: {e}")
        
        return config
    
    def __str__(self) -> str:
        status = "Connected" if self.connected else "Disconnected"
        return f"Hikvision {self.model} at {self.ip}:{self.port} [{status}]"