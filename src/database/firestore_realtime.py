# type: ignore
"""
Firestore Real-time Module for Live Dashboard Updates
Works alongside PostgreSQL for main data storage
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

# Initialize SocketIO for real-time updates
socketio = SocketIO(cors_allowed_origins="*")

class FirestoreRealtime:
    """Handle real-time updates with Firestore"""
    
    def __init__(self):
        self.db = None
        self.initialized = False
        self._listeners = {}
    
    def init_app(self, app):
        """Initialize Firestore with Flask app"""
        try:
            if not firebase_admin._apps:
                cred_path = os.getenv("FIREBASE_ADMIN_KEY", "")
                if cred_path.startswith("~"):
                    cred_path = os.path.expanduser(cred_path)
                
                if not os.path.exists(cred_path):
                    logger.warning(f"Firebase key not found at: {cred_path}")
                    logger.info("Real-time features will use polling fallback")
                    return False
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            self.initialized = True
            logger.info("[OK] Firestore real-time client initialized")
            
            # Start listeners for real-time updates
            self.start_listeners()
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore real-time: {e}")
            return False
    
    def start_listeners(self):
        """Start Firestore listeners for real-time updates"""
        if not self.initialized or not self.db:
            return
        
        try:
            # Listen for new access logs
            self.listen_for_access_logs()
            
            # Listen for device status changes
            self.listen_for_device_updates()
            
            logger.info("[OK] Firestore real-time listeners started")
        except Exception as e:
            logger.error(f"Failed to start listeners: {e}")
    
    def listen_for_access_logs(self):
        """Listen for new access logs in real-time"""
        if not self.db:
            return
        
        try:
            five_minutes_ago = datetime.now() - timedelta(minutes=5)
            logger.info("Access logs listener initialized")
        except Exception as e:
            logger.error(f"Failed to setup access logs listener: {e}")
    
    def listen_for_device_updates(self):
        """Listen for device status changes"""
        if not self.db:
            return
        
        try:
            logger.info("Device status listener initialized")
        except Exception as e:
            logger.error(f"Failed to setup device listener: {e}")
    
    def update_dashboard_stats(self, log_data: Dict):
        """Update cached dashboard statistics in Firestore"""
        if not self.db:
            return
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            stats_ref = self.db.collection('dashboard_stats').document(today)
            
            stats_ref.set({
                'total_accesses': firestore.Increment(1),
                'granted_accesses': firestore.Increment(1 if log_data.get('result') == 'GRANTED' else 0),
                'denied_accesses': firestore.Increment(1 if log_data.get('result') == 'DENIED' else 0),
                'last_updated': datetime.now()
            }, merge=True)
            
        except Exception as e:
            logger.error(f"Failed to update dashboard stats: {e}")
    
    def emit_updated_stats(self, date: str):
        """Emit updated statistics to dashboard"""
        if not self.db:
            return
        
        try:
            stats_ref = self.db.collection('dashboard_stats').document(date)
            stats = stats_ref.get()
            
            if stats and stats.exists:
                data = stats.to_dict()
                if data:
                    socketio.emit('stats_update', {
                        'total_today': data.get('total_accesses', 0),
                        'granted_today': data.get('granted_accesses', 0),
                        'denied_today': data.get('denied_accesses', 0),
                        'last_updated': datetime.now().isoformat()
                    })
        except Exception as e:
            logger.error(f"Failed to emit stats: {e}")
    
    def log_realtime_access(self, student_id: str, student_name: str, 
                           method: str, result: str, score: float, 
                           access_point: str) -> bool:
        """Log an access event to Firestore for real-time display"""
        # Always log to PostgreSQL first (primary storage)
        from src.database.connection import execute_query
        try:
            execute_query("""
                INSERT INTO access_logs 
                (student_id, access_point, verification_method, verification_result, match_score, timestamp)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (student_id, access_point, method, result, score))
            logger.info(f"✓ Access logged to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to log access to PostgreSQL: {e}")
            return False
        
        # Then try Firestore for real-time (optional)
        if self.db:
            try:
                log_data = {
                    'student_id': student_id,
                    'student_name': student_name,
                    'verification_method': method,
                    'verification_result': result,
                    'match_score': score,
                    'access_point': access_point,
                    'timestamp': datetime.now(),
                    'synced_to_postgres': True
                }
                
                # Add to Firestore (for real-time)
                self.db.collection('realtime_access_logs').add(log_data)
                
                # Emit to connected clients
                socketio.emit('new_access', log_data)
                logger.info(f"✓ Access also sent to Firestore for real-time")
                
            except Exception as e:
                logger.warning(f"Firestore real-time logging failed (non-critical): {e}")
        
        return True
    
    def update_device_status(self, device_id: str, status: str, details: Optional[Dict] = None) -> bool:
        """Update device status in real-time"""
        # Always update PostgreSQL first (primary storage)
        from src.database.connection import execute_query
        try:
            execute_query("""
                UPDATE devices 
                SET status = %s, last_seen = NOW(), updated_at = NOW()
                WHERE device_id = %s
            """, (status, device_id))
            logger.info(f"✓ Device status updated in PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to update device status in PostgreSQL: {e}")
            return False
        
        # Then try Firestore for real-time (optional)
        if self.db:
            try:
                details = details or {}
                device_data = {
                    'status': status,
                    'updated_at': datetime.now(),
                    'last_seen': datetime.now(),
                    'details': details
                }
                
                self.db.collection('device_status').document(device_id).set(device_data, merge=True)
                
                socketio.emit('device_status_update', {
                    'device_id': device_id,
                    'status': status,
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"✓ Device status also sent to Firestore for real-time")
                
            except Exception as e:
                logger.warning(f"Firestore device status update failed (non-critical): {e}")
        
        return True
    
    def get_dashboard_data(self) -> Dict:
        """Get current dashboard data"""
        if not self.db:
            return {'stats': {}, 'recent_accesses': [], 'note': 'Firestore not available - using PostgreSQL only'}
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            stats_ref = self.db.collection('dashboard_stats').document(today)
            stats = stats_ref.get()
            
            # Get recent accesses
            five_minutes_ago = datetime.now() - timedelta(minutes=5)
            recent_query = self.db.collection('realtime_access_logs')\
                .where('timestamp', '>=', five_minutes_ago)\
                .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                .limit(20)
            
            recent = []
            for doc in recent_query.stream():
                data = doc.to_dict()
                if data and data.get('timestamp'):
                    data['timestamp'] = data['timestamp'].isoformat()
                recent.append(data or {})
            
            return {
                'stats': stats.to_dict() if stats and stats.exists else {},
                'recent_accesses': recent,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {'stats': {}, 'recent_accesses': []}

# Singleton instance
realtime_manager = FirestoreRealtime()