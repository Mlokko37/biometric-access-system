import bcrypt
from flask_login import UserMixin
from typing import Optional
from .services.admin_service import AdminService
import logging

logger = logging.getLogger(__name__)

class AdminUser(UserMixin):
    """Admin user model for Flask-Login integration with real database."""
    
    def __init__(self, admin_data: dict):
        self.id = str(admin_data['admin_id'])
        self.admin_id = admin_data['admin_id']
        self.username = admin_data['username']
        self.full_name = admin_data['full_name']
        self.email = admin_data.get('email', '')
        self.role = admin_data.get('role', 'operator')
        self.is_active = admin_data.get('is_active', True)
        self.created_at = admin_data.get('created_at')
        self.last_login = admin_data.get('last_login')
        self.profile_image = admin_data.get('profile_image')
    
    @staticmethod
    def get(user_id: str):
        """Get user by ID for Flask-Login from real database."""
        try:
            from src.database.connection import execute_query
            
            result = execute_query(
                "SELECT admin_id, username, password_hash, full_name, email, role, is_active, created_at, last_login, profile_image FROM administrators WHERE admin_id = %s AND is_active = TRUE",
                (user_id,)
            )
            
            if result and len(result) > 0:
                row = result[0]
                admin_data = {
                    'admin_id': row[0],
                    'username': row[1],
                    'full_name': row[3],
                    'email': row[4],
                    'role': row[5],
                    'is_active': row[6],
                    'created_at': row[7],
                    'last_login': row[8],
                    'profile_image': row[9]
                }
                return AdminUser(admin_data)
        except Exception as e:
            logger.error(f"Error loading user from database: {e}")
        return None
    
    def verify_password(self, password: str) -> bool:
        """Verify password using bcrypt with real database."""
        try:
            from src.database.connection import execute_query
            
            result = execute_query(
                "SELECT password_hash FROM administrators WHERE admin_id = %s AND is_active = TRUE",
                (self.admin_id,)
            )
            
            if result and result[0]:
                stored_hash = result[0][0]
                return bcrypt.checkpw(
                    password.encode('utf-8'),
                    stored_hash.encode('utf-8')
                )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
        return False

def create_default_admin():
    """Create default admin account if it doesn't exist."""
    try:
        from src.database.connection import execute_query
        
        # Check if admin exists
        result = execute_query(
            "SELECT admin_id FROM administrators WHERE username = %s",
            ('superadmin',)
        )
        
        if not result:
            # Create superadmin
            password_hash = bcrypt.hashpw('Admin@123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            execute_query("""
                INSERT INTO administrators 
                (username, password_hash, full_name, email, role, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            """, ('superadmin', password_hash, 'System Super Administrator', 
                  'superadmin@school.edu', 'superadmin'))
            
            logger.info("[OK] Default admin account created: superadmin / Admin@123")
        else:
            logger.info("[OK] Default admin account already exists")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to create default admin: {str(e)}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    create_default_admin()