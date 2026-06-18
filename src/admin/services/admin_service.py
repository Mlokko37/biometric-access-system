import psycopg2
import os
import bcrypt
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class AdminService:
    """Service for admin operations with real database."""
    
    def __init__(self):
        self.db_config = self._get_db_config()
    
    def _get_db_config(self):
        """Get database configuration from environment."""
        return {
            'dbname': os.getenv('DB_NAME', 'biometric_access_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', '2546'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432))
        }
    
    def _get_connection(self):
        """Get a database connection."""
        return psycopg2.connect(**self.db_config)
    
    def create_admin(self, username: str, password: str, full_name: str, 
                     email: str = '', role: str = 'operator') -> bool:
        """Create a new admin with hashed password."""
        try:
            # Hash password
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO administrators 
                        (username, password_hash, full_name, email, role, is_active, created_at)
                        VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                        ON CONFLICT (username) DO NOTHING
                        RETURNING admin_id
                    """, (username, password_hash, full_name, email, role))
                    
                    if cur.fetchone():
                        conn.commit()
                        logger.info(f"Admin {username} created successfully")
                        return True
                    
                    logger.warning(f"Username {username} already exists")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating admin: {e}")
            return False
    
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate admin and return admin data if successful."""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT admin_id, username, password_hash, full_name, 
                            email, role, is_active, created_at, last_login, 
                            profile_image
                        FROM administrators 
                        WHERE username = %s
                    """, (username,))
                    
                    admin = cur.fetchone()
                    if not admin:
                        logger.warning(f"Login attempt with unknown username: {username}")
                        return None
                    
                    if not admin['is_active']:
                        logger.warning(f"Login attempt on inactive account: {username}")
                        return {'error': 'Account is deactivated'}
                    
                    if bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
                        cur.execute("""
                            UPDATE administrators 
                            SET last_login = NOW() 
                            WHERE admin_id = %s
                        """, (admin['admin_id'],))
                        conn.commit()
                        
                        return {
                            'admin_id': admin['admin_id'],
                            'username': admin['username'],
                            'full_name': admin['full_name'],
                            'email': admin['email'],
                            'role': admin['role'],
                            'is_active': admin['is_active'],
                            'created_at': admin['created_at'],
                            'last_login': admin['last_login'],
                            'profile_image': admin.get('profile_image', '')
                        }
                    
                    logger.warning(f"Invalid password for user: {username}")
                    return None
                    
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_admin_by_id(self, admin_id: int) -> Optional[Dict[str, Any]]:
        """Get admin details by ID."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT admin_id, username, full_name, email, role, 
                               is_active, created_at, last_login, profile_image
                        FROM administrators 
                        WHERE admin_id = %s
                    """, (admin_id,))
                    
                    admin = cur.fetchone()
                    if admin:
                        return {
                            'admin_id': admin[0],
                            'username': admin[1],
                            'full_name': admin[2],
                            'email': admin[3],
                            'role': admin[4],
                            'is_active': admin[5],
                            'created_at': admin[6],
                            'last_login': admin[7],
                            'profile_image': admin[8]
                        }
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting admin: {e}")
            return None
    
    def get_all_admins(self) -> List[Dict[str, Any]]:
        """Get all admins."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT admin_id, username, full_name, email, role, 
                               is_active, created_at, last_login
                        FROM administrators 
                        ORDER BY created_at DESC
                    """)
                    
                    admins = []
                    for row in cur.fetchall():
                        admins.append({
                            'admin_id': row[0],
                            'username': row[1],
                            'full_name': row[2],
                            'email': row[3],
                            'role': row[4],
                            'is_active': row[5],
                            'created_at': row[6],
                            'last_login': row[7]
                        })
                    
                    return admins
                    
        except Exception as e:
            logger.error(f"Error getting admins: {e}")
            return []
    
    def change_password(self, admin_id: int, old_password: str, new_password: str) -> bool:
        """Change admin password with verification."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Get current hash
                    cur.execute("""
                        SELECT password_hash FROM administrators 
                        WHERE admin_id = %s AND is_active = TRUE
                    """, (admin_id,))
                    
                    result = cur.fetchone()
                    if not result:
                        return False
                    
                    current_hash = result[0]
                    
                    # Verify old password
                    if not bcrypt.checkpw(old_password.encode('utf-8'), current_hash.encode('utf-8')):
                        return False
                    
                    # Hash new password
                    salt = bcrypt.gensalt()
                    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
                    
                    # Update password
                    cur.execute("""
                        UPDATE administrators 
                        SET password_hash = %s, updated_at = NOW()
                        WHERE admin_id = %s
                    """, (new_hash, admin_id))
                    
                    conn.commit()
                    logger.info(f"Password changed for admin {admin_id}")
                    return True
                    
        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False
    
    def reset_password(self, admin_id: int, new_password: str) -> bool:
        """Reset password (admin/superadmin only)."""
        try:
            # Hash new password
            salt = bcrypt.gensalt()
            new_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
            
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE administrators 
                        SET password_hash = %s, updated_at = NOW()
                        WHERE admin_id = %s
                    """, (new_hash, admin_id))
                    
                    conn.commit()
                    logger.info(f"Password reset for admin {admin_id}")
                    return True
                    
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return False
    
    def update_admin_profile(self, admin_id: int, full_name: Optional[str] = None, 
                           email: Optional[str] = None, role: Optional[str] = None,
                           profile_image: Optional[str] = None) -> bool:
        """Update admin profile information."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    update_fields = []
                    params = []
                    
                    if full_name:
                        update_fields.append("full_name = %s")
                        params.append(full_name)
                    
                    if email:
                        update_fields.append("email = %s")
                        params.append(email)
                    
                    if role:
                        update_fields.append("role = %s")
                        params.append(role)
                    
                    if profile_image:
                        update_fields.append("profile_image = %s")
                        params.append(profile_image)
                    
                    if not update_fields:
                        return False
                    
                    update_fields.append("updated_at = NOW()")
                    params.append(admin_id)
                    
                    query = f"""
                        UPDATE administrators 
                        SET {', '.join(update_fields)}
                        WHERE admin_id = %s
                    """
                    
                    cur.execute(query, params)
                    conn.commit()
                    
                    logger.info(f"Profile updated for admin {admin_id}")
                    return cur.rowcount > 0
                    
        except Exception as e:
            logger.error(f"Profile update error: {e}")
            return False
    
    def delete_admin(self, admin_id: int) -> bool:
        """Soft delete an admin account."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE administrators 
                        SET is_active = FALSE, updated_at = NOW()
                        WHERE admin_id = %s
                    """, (admin_id,))
                    
                    conn.commit()
                    logger.info(f"Admin {admin_id} deactivated")
                    return cur.rowcount > 0
                    
        except Exception as e:
            logger.error(f"Delete admin error: {e}")
            return False
    
    def reactivate_admin(self, admin_id: int) -> bool:
        """Reactivate a deactivated admin."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE administrators 
                        SET is_active = TRUE, updated_at = NOW()
                        WHERE admin_id = %s
                    """, (admin_id,))
                    
                    conn.commit()
                    logger.info(f"Admin {admin_id} reactivated")
                    return cur.rowcount > 0
                    
        except Exception as e:
            logger.error(f"Reactivate admin error: {e}")
            return False