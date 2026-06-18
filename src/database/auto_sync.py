"""
Automatic Firebase Sync - Triggers on database changes
No manual scripts needed!
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from src.database.firestore_sync import firestore_sync

logger = logging.getLogger(__name__)

class AutoSync:
    """Automatically sync database changes to Firestore"""
    
    @staticmethod
    def _get_db():
        """Get Firestore database instance, initializing if needed"""
        if firestore_sync.db is None:
            firestore_sync.init_firestore()
        return firestore_sync.db
    
    @staticmethod
    def sync_student_after_save(student_id: int, student_data: Dict[str, Any]) -> bool:
        """Sync student after INSERT or UPDATE"""
        try:
            db = AutoSync._get_db()
            if db is None:
                logger.warning("Firestore not available, skipping sync")
                return False
            
            # Convert to string for Firestore
            student_id_str = str(student_id)
            
            # Prepare data with safe conversions
            def safe_str(val: Any) -> str:
                return str(val) if val is not None else ''
            
            def safe_int(val: Any) -> int:
                try:
                    return int(val) if val is not None else 0
                except (ValueError, TypeError):
                    return 0
            
            def safe_bool(val: Any) -> bool:
                return bool(val) if val is not None else True
            
            data = {
                'student_id': student_id_str,
                'registration_number': safe_str(student_data.get('registration_number', '')),
                'first_name': safe_str(student_data.get('first_name', '')),
                'last_name': safe_str(student_data.get('last_name', '')),
                'full_name': f"{safe_str(student_data.get('first_name', ''))} {safe_str(student_data.get('last_name', ''))}".strip(),
                'email': safe_str(student_data.get('email', '')),
                'phone': safe_str(student_data.get('phone', '')),
                'course': safe_str(student_data.get('course', '')),
                'year_of_study': safe_int(student_data.get('year_of_study', 0)),
                'is_active': safe_bool(student_data.get('is_active', True)),
                'profile_image': safe_str(student_data.get('profile_image', '')),
                'updated_at': datetime.now(),
                'auto_synced': True
            }
            
            # Save to Firestore
            db.collection('students').document(student_id_str).set(data, merge=True)
            logger.info(f"✅ Auto-synced student {student_id_str} to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Auto-sync failed for student {student_id}: {e}")
            return False
    
    @staticmethod
    def sync_admin_after_save(admin_id: int, admin_data: Dict[str, Any]) -> bool:
        """Sync admin after INSERT or UPDATE"""
        try:
            db = AutoSync._get_db()
            if db is None:
                logger.warning("Firestore not available, skipping sync")
                return False
            
            admin_id_str = str(admin_id)
            
            def safe_str(val: Any) -> str:
                return str(val) if val is not None else ''
            
            def safe_bool(val: Any) -> bool:
                return bool(val) if val is not None else True
            
            data = {
                'admin_id': admin_id_str,
                'username': safe_str(admin_data.get('username', '')),
                'full_name': safe_str(admin_data.get('full_name', '')),
                'email': safe_str(admin_data.get('email', '')),
                'role': safe_str(admin_data.get('role', 'staff')),
                'is_active': safe_bool(admin_data.get('is_active', True)),
                'updated_at': datetime.now(),
                'auto_synced': True
            }
            
            db.collection('administrators').document(admin_id_str).set(data, merge=True)
            logger.info(f"✅ Auto-synced admin {admin_id_str} to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Auto-sync failed for admin {admin_id}: {e}")
            return False
    
    @staticmethod
    def log_access_auto(student_id: int, access_data: Dict[str, Any]) -> bool:
        """Auto-log access events to Firestore"""
        try:
            db = AutoSync._get_db()
            if db is None:
                logger.warning("Firestore not available, skipping log")
                return False
            
            def safe_str(val: Any) -> str:
                return str(val) if val is not None else ''
            
            def safe_float(val: Any) -> float:
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0
            
            log_entry = {
                'student_id': safe_str(student_id),
                'student_name': safe_str(access_data.get('student_name', 'Unknown')),
                'registration_number': safe_str(access_data.get('registration_number', '')),
                'access_point': safe_str(access_data.get('access_point', 'Main Gate')),
                'verification_method': safe_str(access_data.get('verification_method', 'fingerprint')),
                'verification_result': safe_str(access_data.get('verification_result', 'GRANTED')),
                'match_score': safe_float(access_data.get('match_score', 0)),
                'timestamp': datetime.now(),
                'auto_logged': True
            }
            
            db.collection('access_logs').add(log_entry)
            logger.info(f"✅ Auto-logged access for student {student_id} to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Auto-log failed for student {student_id}: {e}")
            return False
    
    @staticmethod
    def delete_student(student_id: int) -> bool:
        """Delete student from Firestore when deleted from PostgreSQL"""
        try:
            db = AutoSync._get_db()
            if db is None:
                logger.warning("Firestore not available, skipping delete")
                return False
            
            db.collection('students').document(str(student_id)).delete()
            logger.info(f"✅ Deleted student {student_id} from Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Delete from Firestore failed for student {student_id}: {e}")
            return False

auto_sync = AutoSync()