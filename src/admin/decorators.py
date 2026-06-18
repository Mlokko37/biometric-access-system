from functools import wraps
from flask import session, redirect, url_for, flash, jsonify, request, current_app
import logging

logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or 'username' not in session:
            # For API requests, return JSON error
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*required_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'admin_id' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login'))
            
            if 'role' not in session:
                logger.warning(f"User {session.get('username')} has no role in session")
                flash('Invalid session. Please log in again.', 'danger')
                return redirect(url_for('logout'))
            
            # Normalize role names
            user_role = session['role'].lower()
            
            # Handle different role naming conventions
            role_map = {
                'super-admin': 'superadmin',
                'super_admin': 'superadmin',
                'staff': 'operator'
            }
            
            if user_role in role_map:
                user_role = role_map[user_role]
            
            # Normalize required roles
            normalized_required = []
            for role in required_roles:
                role_lower = role.lower()
                if role_lower in role_map:
                    normalized_required.append(role_map[role_lower])
                else:
                    normalized_required.append(role_lower)
            
            # Check if user has required role
            if user_role not in normalized_required:
                logger.warning(f"User {session.get('username')} with role {user_role} "
                             f"attempted to access {request.path}")
                
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_required(permission_name: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login'))
            
            # Get user's role and check permissions
            user_role = session['role'].lower()
            
            # Define permissions based on roles
            role_permissions = {
                'superadmin': ['*'],  # All permissions
                'admin': ['view_reports', 'manage_students', 'manage_devices', 'view_logs'],
                'operator': ['view_reports', 'view_students', 'view_logs']
            }
            
            has_permission = False
            if user_role in role_permissions:
                if '*' in role_permissions[user_role]:
                    has_permission = True
                elif permission_name in role_permissions[user_role]:
                    has_permission = True
            
            if not has_permission:
                if request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'Insufficient permissions',
                        'message': f'You need {permission_name} permission'
                    }), 403
                
                flash(f'You need {permission_name} permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def api_login_required(f):
    """API-specific login decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function