"""
Firestore Real Data Sync - Store actual biometric system data
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
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
            # Get Firebase key path from environment
            cred_path = os.getenv("FIREBASE_ADMIN_KEY", "")
            
            # Expand user path if needed (for ~/)
            if cred_path.startswith("~"):
                cred_path = os.path.expanduser(cred_path)
            
            # Also check for the key in current directory
            if not cred_path or not os.path.exists(cred_path):
                # Try common locations
                possible_paths = [
                    cred_path,
                    "firebase-admin-key.json",
                    "biometric-access-system-firebase-adminsdk-fbsvc-3351fb54da.json",
                    os.path.join(os.path.expanduser("~"), ".secrets", "biometric-system", "firebase-admin-key.json"),
                    os.path.join(os.path.expanduser("~"), ".secrets", "biometric-system", "biometric-access-system-firebase-adminsdk-fbsvc-3351fb54da.json"),
                ]
                
                for path in possible_paths:
                    if path and os.path.exists(path):
                        cred_path = path
                        break
            
            if not os.path.exists(cred_path):
                logger.error(f"Firebase key not found at: {cred_path}")
                print(f"\n❌ Firebase key not found!")
                print(f"   Looked for: {cred_path}")
                print("\n   Please ensure:")
                print("   1. FIREBASE_ADMIN_KEY is set in .env file")
                print("   2. The file exists at that location")
                print("   3. You've created a Firestore database in Firebase Console")
                return False
            
            print(f"✓ Found Firebase key at: {cred_path}")
            
            # Initialize Firebase if not already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized")
            
            self.db = firestore.client()
            self.initialized = True
            print("✓ Firestore connected successfully")
            logger.info("[OK] Firestore connected for real data")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            print(f"❌ Firestore initialization failed: {e}")
            return False
    
    # ==================== STUDENTS ====================
    
    def sync_student_to_firestore(self, student_data: Dict) -> bool:
        """Sync a student record to Firestore"""
        if not self.db:
            return False
        
        try:
            student_id = student_data.get('student_id')
            if not student_id:
                return False
            
            # Prepare data for Firestore
            firestore_data = {
                'student_id': student_id,
                'registration_number': student_data.get('registration_number'),
                'first_name': student_data.get('first_name'),
                'last_name': student_data.get('last_name'),
                'full_name': f"{student_data.get('first_name', '')} {student_data.get('last_name', '')}".strip(),
                'email': student_data.get('email'),
                'phone': student_data.get('phone'),
                'course': student_data.get('course'),
                'year_of_study': student_data.get('year_of_study'),
                'is_active': student_data.get('is_active', True),
                'profile_image': student_data.get('profile_image'),
                'updated_at': datetime.now(),
                'synced_from_postgres': True
            }
            
            # Add to Firestore
            self.db.collection('students').document(student_id).set(firestore_data, merge=True)
            logger.info(f"✓ Student {student_id} synced to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync student to Firestore: {e}")
            return False
    
    def get_student_from_firestore(self, student_id: str) -> Optional[Dict]:
        """Get student from Firestore"""
        if not self.db:
            return None
        
        try:
            doc = self.db.collection('students').document(student_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to get student from Firestore: {e}")
            return None
    
    def get_all_students_from_firestore(self) -> List[Dict]:
        """Get all students from Firestore"""
        if not self.db:
            return []
        
        try:
            students = []
            docs = self.db.collection('students').where('is_active', '==', True).stream()
            for doc in docs:
                data = doc.to_dict()
                if data:
                    students.append(data)
            return students
        except Exception as e:
            logger.error(f"Failed to get students from Firestore: {e}")
            return []
    
    # ==================== ACCESS LOGS ====================
    
    def log_access_to_firestore(self, access_data: Dict) -> bool:
        """Log a real access event to Firestore"""
        if not self.db:
            return False
        
        try:
            # Prepare access log for Firestore
            log_data = {
                'student_id': access_data.get('student_id'),
                'student_name': access_data.get('student_name'),
                'registration_number': access_data.get('registration_number'),
                'access_point': access_data.get('access_point'),
                'verification_method': access_data.get('verification_method'),
                'verification_result': access_data.get('verification_result'),
                'match_score': access_data.get('match_score', 0),
                'timestamp': datetime.now(),
                'device_id': access_data.get('device_id'),
                'details': access_data.get('details', {})
            }
            
            # Add to Firestore collection
            self.db.collection('access_logs').add(log_data)
            logger.info(f"✓ Access logged to Firestore: {access_data.get('student_name')} - {access_data.get('verification_result')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log access to Firestore: {e}")
            return False
    
    def get_recent_access_logs(self, limit: int = 50) -> List[Dict]:
        """Get recent access logs from Firestore"""
        if not self.db:
            return []
        
        try:
            logs = []
            docs = self.db.collection('access_logs')\
                .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()
            
            for doc in docs:
                data = doc.to_dict()
                if data and data.get('timestamp'):
                    data['timestamp'] = data['timestamp'].isoformat()
                logs.append(data or {})
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get access logs from Firestore: {e}")
            return []
    
    # ==================== DEVICES ====================
    
    def sync_device_to_firestore(self, device_data: Dict) -> bool:
        """Sync device status to Firestore"""
        if not self.db:
            return False
        
        try:
            device_id = device_data.get('device_id')
            if not device_id:
                return False
            
            device_info = {
                'device_id': device_id,
                'device_name': device_data.get('device_name'),
                'device_type': device_data.get('device_type'),
                'location': device_data.get('location'),
                'status': device_data.get('status', 'offline'),
                'ip_address': device_data.get('ip_address'),
                'last_seen': datetime.now(),
                'updated_at': datetime.now()
            }
            
            self.db.collection('devices').document(device_id).set(device_info, merge=True)
            logger.info(f"✓ Device {device_id} synced to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync device to Firestore: {e}")
            return False
    
    def update_device_status_realtime(self, device_id: str, status: str) -> bool:
        """Update device status in real-time"""
        if not self.db:
            return False
        
        try:
            self.db.collection('devices').document(device_id).update({
                'status': status,
                'last_seen': datetime.now(),
                'updated_at': datetime.now()
            })
            logger.info(f"✓ Device {device_id} status updated to {status} in Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update device status in Firestore: {e}")
            return False
    
    # ==================== ADMINISTRATORS ====================
    
    def sync_admin_to_firestore(self, admin_data: Dict) -> bool:
        """Sync admin user to Firestore"""
        if not self.db:
            return False
        
        try:
            admin_id = str(admin_data.get('admin_id'))
            if not admin_id:
                return False
            
            admin_info = {
                'admin_id': admin_id,
                'username': admin_data.get('username'),
                'full_name': admin_data.get('full_name'),
                'email': admin_data.get('email'),
                'role': admin_data.get('role', 'staff'),
                'is_active': admin_data.get('is_active', True),
                'updated_at': datetime.now()
            }
            
            self.db.collection('administrators').document(admin_id).set(admin_info, merge=True)
            logger.info(f"✓ Admin {admin_data.get('username')} synced to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync admin to Firestore: {e}")
            return False
    
    # ==================== DASHBOARD STATS ====================
    
    def update_dashboard_stats(self, stats_data: Dict) -> bool:
        """Update real-time dashboard statistics"""
        if not self.db:
            return False
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            stats_ref = self.db.collection('dashboard_stats').document(today)
            
            stats_ref.set({
                'total_students': stats_data.get('total_students', 0),
                'total_accesses_today': stats_data.get('total_accesses_today', 0),
                'granted_today': stats_data.get('granted_today', 0),
                'denied_today': stats_data.get('denied_today', 0),
                'online_devices': stats_data.get('online_devices', 0),
                'last_updated': datetime.now()
            }, merge=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update dashboard stats: {e}")
            return False
    
    # ==================== BIOMETRIC TEMPLATES ====================
    
    def sync_biometric_template(self, student_id: str, template_type: str, 
                                 template_data: bytes, quality_score: float) -> bool:
        """Sync biometric template to Firestore"""
        if not self.db:
            return False
        
        try:
            import base64
            
            template_b64 = base64.b64encode(template_data).decode('utf-8')
            
            template_info = {
                'student_id': student_id,
                'template_type': template_type,
                'template_data': template_b64,
                'quality_score': quality_score,
                'enrolled_at': datetime.now(),
                'synced_from_postgres': True
            }
            
            # Store as subcollection under student
            template_id = f"{template_type}_{int(datetime.now().timestamp())}"
            self.db.collection('students').document(student_id)\
                .collection('biometric_templates').document(template_id).set(template_info)
            
            logger.info(f"✓ Biometric template for {student_id} synced to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync biometric template: {e}")
            return False

# Singleton instance
firestore_sync = FirestoreSync()