"""
Firestore Real Data Sync - Store actual biometric system data
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

class FirestoreSync:
    """Sync real data between PostgreSQL and Firestore"""
    
    def __init__(self):
        self.db = None
        self.initialized = False
    
    def init_firestore(self):
        """Initialize Firestore connection"""
        try:
            cred_path = os.getenv("FIREBASE_ADMIN_KEY", "")
            
            if cred_path.startswith("~"):
                cred_path = os.path.expanduser(cred_path)
            
            if not os.path.exists(cred_path):
                print(f"Firebase key not found: {cred_path}")
                return False
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            self.initialized = True
            print("[OK] Firestore connected")
            return True
            
        except Exception as e:
            print(f"Failed to initialize Firestore: {e}")
            return False
    
    def sync_student_to_firestore(self, student_data: Dict) -> bool:
        """Sync a student record to Firestore"""
        if not self.db:
            return False
        
        try:
            # Get student_id and convert to string
            student_id = student_data.get('student_id')
            if student_id is None:
                return False
            
            # Convert all values to string safely
            def to_str(val):
                if val is None:
                    return ''
                return str(val)
            
            def to_int(val):
                if val is None:
                    return 0
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return 0
            
            student_id_str = to_str(student_id)
            first_name = to_str(student_data.get('first_name', ''))
            last_name = to_str(student_data.get('last_name', ''))
            
            firestore_data = {
                'student_id': student_id_str,
                'registration_number': to_str(student_data.get('registration_number', '')),
                'first_name': first_name,
                'last_name': last_name,
                'full_name': f"{first_name} {last_name}".strip(),
                'email': to_str(student_data.get('email', '')),
                'phone': to_str(student_data.get('phone', '')),
                'course': to_str(student_data.get('course', '')),
                'year_of_study': to_int(student_data.get('year_of_study', 0)),
                'is_active': bool(student_data.get('is_active', True)),
                'profile_image': to_str(student_data.get('profile_image', '')),
                'updated_at': datetime.now(),
                'synced_from_postgres': True
            }
            
            self.db.collection('students').document(student_id_str).set(firestore_data, merge=True)
            return True
            
        except Exception as e:
            print(f"Failed to sync student to Firestore: {e}")
            return False
    
    def sync_admin_to_firestore(self, admin_data: Dict) -> bool:
        """Sync admin user to Firestore"""
        if not self.db:
            return False
        
        try:
            admin_id = admin_data.get('admin_id')
            if admin_id is None:
                return False
            
            def to_str(val):
                if val is None:
                    return ''
                return str(val)
            
            admin_id_str = to_str(admin_id)
            
            admin_info = {
                'admin_id': admin_id_str,
                'username': to_str(admin_data.get('username', '')),
                'full_name': to_str(admin_data.get('full_name', '')),
                'email': to_str(admin_data.get('email', '')),
                'role': to_str(admin_data.get('role', 'staff')),
                'is_active': bool(admin_data.get('is_active', True)),
                'updated_at': datetime.now()
            }
            
            self.db.collection('administrators').document(admin_id_str).set(admin_info, merge=True)
            return True
            
        except Exception as e:
            print(f"Failed to sync admin to Firestore: {e}")
            return False
    
    def log_access_to_firestore(self, access_data: Dict) -> bool:
        """Log a real access event to Firestore"""
        if not self.db:
            return False
        
        try:
            def to_str(val):
                if val is None:
                    return ''
                return str(val)
            
            log_data = {
                'student_id': to_str(access_data.get('student_id', '')),
                'student_name': to_str(access_data.get('student_name', '')),
                'registration_number': to_str(access_data.get('registration_number', '')),
                'access_point': to_str(access_data.get('access_point', '')),
                'verification_method': to_str(access_data.get('verification_method', '')),
                'verification_result': to_str(access_data.get('verification_result', '')),
                'match_score': float(access_data.get('match_score', 0)),
                'timestamp': access_data.get('timestamp', datetime.now()),
                'device_id': to_str(access_data.get('device_id', '')),
                'details': access_data.get('details', {})
            }
            
            self.db.collection('access_logs').add(log_data)
            return True
            
        except Exception as e:
            print(f"Failed to log access to Firestore: {e}")
            return False
    
    def sync_device_to_firestore(self, device_data: Dict) -> bool:
        """Sync device status to Firestore"""
        if not self.db:
            return False
        
        try:
            device_id = device_data.get('device_id')
            if device_id is None:
                return False
            
            def to_str(val):
                if val is None:
                    return ''
                return str(val)
            
            device_id_str = to_str(device_id)
            
            device_info = {
                'device_id': device_id_str,
                'device_name': to_str(device_data.get('device_name', '')),
                'device_type': to_str(device_data.get('device_type', '')),
                'location': to_str(device_data.get('location', '')),
                'status': to_str(device_data.get('status', 'offline')),
                'ip_address': to_str(device_data.get('ip_address', '')),
                'last_seen': datetime.now(),
                'updated_at': datetime.now()
            }
            
            self.db.collection('devices').document(device_id_str).set(device_info, merge=True)
            return True
            
        except Exception as e:
            print(f"Failed to sync device to Firestore: {e}")
            return False

# Singleton instance
firestore_sync = FirestoreSync()