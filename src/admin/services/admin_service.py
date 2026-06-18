import psycopg2
import os
import bcrypt
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Use the shared connection pool that respects DATABASE_URL
from src.database.connection import execute_query

logger = logging.getLogger(__name__)

class AdminService:
    """Service for admin operations using the shared database connection pool."""
    
    def create_admin(self, username: str, password: str, full_name: str, 
                     email: str = '', role: str = 'operator') -> bool:
        """Create a new admin with hashed password."""
        try:
            # Hash password
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            
            # Check if user already exists
            existing = execute_query(
                "SELECT admin_id FROM administrators WHERE username = %s",
                (username,)
            )
            if existing:
                logger.warning(f"Username {username} already exists")
                return False
            
            # Insert new admin
            execute_query("""
                INSERT INTO administrators 
                (username, password_hash, full_name, email, role, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            """, (username, password_hash, full_name, email, role))
            
            logger.info(f"Admin {username} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating admin: {e}")
            return False
    
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate admin and return admin data if successful."""
        try:
            result = execute_query("""
                SELECT admin_id, username, password_hash, full_name, 
                       email, role, is_active, created_at, last_login, 
                       profile_image
                FROM administrators 
                WHERE username = %s
            """, (username,))
            
            if not result:
                logger.warning(f"Login attempt with unknown username: {username}")
                return None
            
            admin = result[0]
            
            if not admin['is_active']:
                logger.warning(f"Login attempt on inactive account: {username}")
                return {'error': 'Account is deactivated'}
            
            if bcrypt.checkpw(password.encode('utf-8'), admin['password_hash'].encode('utf-8')):
                # Update last_login
                execute_query("""
                    UPDATE administrators 
                    SET last_login = NOW() 
                    WHERE admin_id = %s
                """, (admin['admin_id'],))
                
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
            result = execute_query("""
                SELECT admin_id, username, full_name, email, role, 
                       is_active, created_at, last_login, profile_image
                FROM administrators 
                WHERE admin_id = %s
            """, (admin_id,))
            
            if result:
                admin = result[0]
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
            return None
            
        except Exception as e:
            logger.error(f"Error getting admin: {e}")
            return None
    
    def get_all_admins(self) -> List[Dict[str, Any]]:
        """Get all admins."""
        try:
            result = execute_query("""
                SELECT admin_id, username, full_name, email, role, 
                       is_active, created_at, last_login
                FROM administrators 
                ORDER BY created_at DESC
            """)
            
            admins = []
            if result:
                for row in result:
                    admins.append({
                        'admin_id': row['admin_id'],
                        'username': row['username'],
                        'full_name': row['full_name'],
                        'email': row['email'],
                        'role': row['role'],
                        'is_active': row['is_active'],
                        'created_at': row['created_at'],
                        'last_login': row['last_login']
                    })
            return admins
            
        except Exception as e:
            logger.error(f"Error getting admins: {e}")
            return []
    
    def change_password(self, admin_id: int, old_password: str, new_password: str) -> bool:
        """Change admin password with verification."""
        try:
            # Get current hash
            result = execute_query("""
                SELECT password_hash FROM administrators 
                WHERE admin_id = %s AND is_active = TRUE
            """, (admin_id,))
            
            if not result:
                return False
            
            current_hash = result[0]['password_hash']
            
            # Verify old password
            if not bcrypt.checkpw(old_password.encode('utf-8'), current_hash.encode('utf-8')):
                return False
            
            # Hash new password
            salt = bcrypt.gensalt()
            new_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
            
            # Update password
            execute_query("""
                UPDATE administrators 
                SET password_hash = %s, updated_at = NOW()
                WHERE admin_id = %s
            """, (new_hash, admin_id))
            
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
            
            execute_query("""
                UPDATE administrators 
                SET password_hash = %s, updated_at = NOW()
                WHERE admin_id = %s
            """, (new_hash, admin_id))
            
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
            updates = []
            params = []
            
            if full_name is not None:
                updates.append("full_name = %s")
                params.append(full_name)
            
            if email is not None:
                updates.append("email = %s")
                params.append(email)
            
            if role is not None:
                updates.append("role = %s")
                params.append(role)
            
            if profile_image is not None:
                updates.append("profile_image = %s")
                params.append(profile_image)
            
            if not updates:
                return False
            
            updates.append("updated_at = NOW()")
            params.append(admin_id)
            
            query = f"""
                UPDATE administrators 
                SET {', '.join(updates)}
                WHERE admin_id = %s
            """
            
            execute_query(query, tuple(params))
            
            logger.info(f"Profile updated for admin {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Profile update error: {e}")
            return False
    
    def delete_admin(self, admin_id: int) -> bool:
        """Soft delete an admin account."""
        try:
            execute_query("""
                UPDATE administrators 
                SET is_active = FALSE, updated_at = NOW()
                WHERE admin_id = %s
            """, (admin_id,))
            
            logger.info(f"Admin {admin_id} deactivated")
            return True
            
        except Exception as e:
            logger.error(f"Delete admin error: {e}")
            return False
    
    def reactivate_admin(self, admin_id: int) -> bool:
        """Reactivate a deactivated admin."""
        try:
            execute_query("""
                UPDATE administrators 
                SET is_active = TRUE, updated_at = NOW()
                WHERE admin_id = %s
            """, (admin_id,))
            
            logger.info(f"Admin {admin_id} reactivated")
            return True
            
        except Exception as e:
            logger.error(f"Reactivate admin error: {e}")
            return False