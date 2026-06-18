from enum import Enum
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request
import logging

logger = logging.getLogger(__name__)

class Role(str, Enum):
    SUPERADMIN = 'superadmin'
    ADMIN = 'admin'
    OPERATOR = 'operator'
    STAFF = 'staff'  # Alias for operator

class Permissions:
    """Define permissions for each role based on database roles."""
    
    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        """
        Check if a role has specific permission.
        Uses database roles: superadmin, admin, staff (operator)
        """
        # Normalize role
        role_lower = role.lower()
        if role_lower == 'super-admin' or role_lower == 'super_admin':
            role_lower = 'superadmin'
        elif role_lower == 'staff':
            role_lower = 'operator'
        
        # Define permissions (this matches your database roles)
        permissions = {
            'superadmin': {
                'manage_admins': True,
                'manage_students': True,
                'manage_devices': True,
                'view_reports': True,
                'system_config': True,
                'manage_logs': True,
                'enrollment': True,
                'verification': True,
                'database_management': True,
                'backup': True,
                'restore': True,
                'audit_logs': True,
                '*': True  # All permissions
            },
            'admin': {
                'manage_admins': False,
                'manage_students': True,
                'manage_devices': True,
                'view_reports': True,
                'system_config': True,
                'manage_logs': True,
                'enrollment': True,
                'verification': True,
                'database_management': False,
                'backup': True,
                'restore': False,
                'audit_logs': True
            },
            'operator': {
                'manage_admins': False,
                'manage_students': True,
                'manage_devices': False,
                'view_reports': True,
                'system_config': False,
                'manage_logs': False,
                'enrollment': True,
                'verification': True,
                'database_management': False,
                'backup': False,
                'restore': False,
                'audit_logs': False,
                'view_students': True,
                'view_logs': True
            }
        }
        
        # Check if role exists
        if role_lower not in permissions:
            logger.warning(f"Unknown role: {role}")
            return False
        
        # Check for wildcard permission
        if '*' in permissions[role_lower]:
            return True
        
        # Check specific permission
        return permissions[role_lower].get(permission, False)
    
    @staticmethod
    def get_role_level(role: str) -> int:
        """Get numeric role level for comparison."""
        role_levels = {
            'superadmin': 100,
            'admin': 50,
            'operator': 10,
            'staff': 10
        }
        return role_levels.get(role.lower(), 0)
    
    @staticmethod
    def is_at_least(role: str, minimum_role: str) -> bool:
        """Check if role is at least minimum_role."""
        return Permissions.get_role_level(role) >= Permissions.get_role_level(minimum_role)

def has_permission(permission: str):
    """Decorator to check if current user has permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            
            user_role = session['role']
            
            if not Permissions.has_permission(user_role, permission):
                logger.warning(f"User {session.get('username')} denied permission: {permission}")
                
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                flash(f'You do not have permission: {permission}', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator