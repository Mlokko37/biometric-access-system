import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

class LoggingManager:
    """Manages access logs and audit trails."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize logging manager."""
        if db_path is None:
            db_path = 'data/biometric_access.db'
        
        self.db_path = db_path
        self._ensure_database()
    
    def _ensure_database(self):
        """Ensure log tables exist in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create access logs table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    registration_number TEXT,
                    access_point TEXT NOT NULL,
                    verification_method TEXT NOT NULL,
                    verification_result TEXT NOT NULL,
                    match_score REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    additional_info TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            ''')
            
            # Create audit trail table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_trail (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_type TEXT NOT NULL,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create system events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("Logging database tables verified")
            
        except Exception as e:
            logger.error(f"Failed to ensure logging database: {str(e)}")
    
    def log_access(self, student_id: Optional[int], registration_number: Optional[str],
                  access_point: str, verification_method: str, result: str,
                  match_score: Optional[float] = None, additional_info: str = "") -> bool:
        """
        Log an access attempt.
        
        Args:
            student_id: Student ID (if known)
            registration_number: Registration number
            access_point: Where access was attempted
            verification_method: 'fingerprint', 'facial', or 'multi-modal'
            result: 'granted' or 'denied'
            match_score: Match score if available
            additional_info: Additional information
            
        Returns:
            bool: True if logged successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO access_logs 
                (student_id, registration_number, access_point, verification_method,
                 verification_result, match_score, additional_info)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                registration_number,
                access_point,
                verification_method,
                result,
                match_score,
                additional_info
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Access logged: {registration_number or 'Unknown'} - {result} at {access_point}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log access: {str(e)}")
            return False
    
    def log_audit(self, user_type: str, user_id: Optional[int], action: str,
                 details: str = "", ip_address: str = "") -> bool:
        """
        Log an audit trail entry.
        
        Args:
            user_type: 'admin', 'student', or 'system'
            user_id: User ID if applicable
            action: Action performed
            details: Action details
            ip_address: IP address if known
            
        Returns:
            bool: True if logged successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO audit_trail 
                (user_type, user_id, action, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_type, user_id, action, details, ip_address))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Audit logged: {user_type} {user_id} - {action}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log audit: {str(e)}")
            return False
    
    def log_system_event(self, event_type: str, event_level: str, message: str,
                        details: str = "") -> bool:
        """
        Log a system event.
        
        Args:
            event_type: Event type (e.g., 'startup', 'shutdown', 'error')
            event_level: 'info', 'warning', 'error', 'critical'
            message: Event message
            details: Additional details
            
        Returns:
            bool: True if logged successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_events 
                (event_type, event_level, message, details)
                VALUES (?, ?, ?, ?)
            ''', (event_type, event_level, message, details))
            
            conn.commit()
            conn.close()
            
            logger.info(f"System event logged: {event_type} - {message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log system event: {str(e)}")
            return False
    
    def get_access_logs(self, limit: int = 100, offset: int = 0,
                       filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Retrieve access logs.
        
        Args:
            limit: Maximum number of logs to retrieve
            offset: Offset for pagination
            filters: Optional filters (e.g., {'result': 'granted', 'date_from': '...'})
            
        Returns:
            List of log entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if students table exists    
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            students_table_exists = cursor.fetchone() is not None
            
            if students_table_exists:
                query = '''
                    SELECT al.*, s.first_name, s.last_name
                    FROM access_logs al
                    LEFT JOIN students s ON al.student_id = s.student_id
                    WHERE 1=1
                '''
            else:
                query = '''
                    SELECT al.*, NULL as first_name, NULL as last_name
                    FROM access_logs
                    WHERE 1=1
                '''    
            params = []
            
            # Apply filters
            if filters:
                if 'result' in filters:
                    query += ' AND verification_result = ?'
                    params.append(filters['result'])
                
                if 'method' in filters:
                    query += ' AND verification_method = ?'
                    params.append(filters['method'])
                
                if 'access_point' in filters:
                    query += ' AND access_point = ?'
                    params.append(filters['access_point'])
                
                if 'date_from' in filters:
                    query += ' AND timestamp >= ?'
                    params.append(filters['date_from'])
                
                if 'date_to' in filters:
                    query += ' AND timestamp <= ?'
                    params.append(filters['date_to'])
            
            # Order and limit
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            logs = []
            for row in rows:
                log = dict(row)
                logs.append(log)
            
            logger.debug(f"Retrieved {len(logs)} access logs")
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get access logs: {str(e)}")
            return []
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get access statistics.
        
        Args:
            days: Number of days to include
            
        Returns:
            Dictionary with statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Total accesses
            cursor.execute('SELECT COUNT(*) FROM access_logs')
            stats['total_accesses'] = cursor.fetchone()[0]
            
            # Granted vs denied
            cursor.execute('''
                SELECT verification_result, COUNT(*) 
                FROM access_logs 
                GROUP BY verification_result
            ''')
            for result, count in cursor.fetchall():
                stats[f'{result}_accesses'] = count
            
            # Accesses by method
            cursor.execute('''
                SELECT verification_method, COUNT(*) 
                FROM access_logs 
                GROUP BY verification_method
            ''')
            methods = {}
            for method, count in cursor.fetchall():
                methods[method] = count
            stats['by_method'] = methods
            
            # Recent activity (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) FROM access_logs 
                WHERE timestamp >= datetime('now', '-1 day')
            ''')
            stats['last_24h'] = cursor.fetchone()[0]
            
            # Busiest access point
            cursor.execute('''
                SELECT access_point, COUNT(*) as count
                FROM access_logs 
                GROUP BY access_point 
                ORDER BY count DESC 
                LIMIT 1
            ''')
            busiest = cursor.fetchone()
            if busiest:
                stats['busiest_access_point'] = {
                    'point': busiest[0],
                    'count': busiest[1]
                }
            
            conn.close()
            
            logger.debug(f"Statistics generated for {days} days")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {}
    
    def export_logs(self, format: str = 'json', filepath: Optional[str] = None) -> bool:
        """
        Export logs to file.
        
        Args:
            format: Export format ('json', 'csv')
            filepath: Output file path
            
        Returns:
            bool: True if exported successfully
        """
        try:
            # Get all logs
            logs = self.get_access_logs(limit=1000)
            
            if not logs:
                logger.warning("No logs to export")
                return False
            
            if filepath is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = f'data/logs/export_{timestamp}.{format}'
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            if format == 'json':
                with open(filepath, 'w') as f:
                    json.dump(logs, f, indent=2, default=str)
            elif format == 'csv':
                import csv
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    if logs:
                        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
                        writer.writeheader()
                        writer.writerows(logs)
            else:
                logger.error(f"Unsupported export format: {format}")
                return False
            
            logger.info(f"Logs exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export logs: {str(e)}")
            return False

def test_logging_manager():
    """Test the logging manager."""
    print("Testing Logging Manager...")
    
    # Create test database
    import tempfile
    import os
    
    temp_db = tempfile.mktemp(suffix='.db')
    manager = LoggingManager(temp_db)
    
    # Test logging
    print("\n1. Logging Access Events:")
    manager.log_access(
        student_id=1,
        registration_number="TEST001",
        access_point="Main Gate",
        verification_method="fingerprint",
        result="granted",
        match_score=85.5
    )
    
    manager.log_access(
        student_id=None,
        registration_number=None,
        access_point="Library",
        verification_method="facial",
        result="denied",
        match_score=45.2,
        additional_info="Low match score"
    )
    
    print("[OK] Access events logged")
    
    # Test retrieving logs
    print("\n2. Retrieving Logs:")
    logs = manager.get_access_logs(limit=10)
    print(f"[OK] Retrieved {len(logs)} log entries")
    
    # Test statistics
    print("\n3. Generating Statistics:")
    stats = manager.get_statistics(days=7)
    print(f"[OK] Statistics: {stats}")
    
    # Test audit logging
    print("\n4. Audit Logging:")
    manager.log_audit(
        user_type="admin",
        user_id=1,
        action="login",
        details="Admin logged in",
        ip_address="192.168.1.100"
    )
    print("[OK] Audit event logged")
    
    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_logging_manager()