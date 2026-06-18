"""
Biometric Student Access System - Admin Panel
Main Flask application with PostgreSQL database integration.
Features:
- User authentication and authorization
- Biometric data management
- Access logging and reporting
"""
import os
import subprocess
import psutil
import platform
import socket
import sys
import logging
import secrets
import time
import csv
import bcrypt
import flask
from src.admin.access_point_api import access_point_api
from flask_wtf import CSRFProtect
from functools import wraps
from datetime import datetime, date, timedelta
from io import BytesIO, StringIO
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from src.database.firestore_sync import firestore_sync
from src.database.auto_sync import auto_sync

from flask import (
    Flask, render_template, request, redirect, session,
    url_for, flash, jsonify, abort, Response, g
)
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required, AnonymousUserMixin

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

VALID_ROLES = {"super-admin", "admin", "staff"}
DEFAULT_ROLE = "staff"

csrf = CSRFProtect()

def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================
def generate_api_key() -> str:
        """Generate a secure random API key."""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32)) 

# -------------------------------------------------------------------
# PostgreSQL Database Connection Functions - FIXED
# -------------------------------------------------------------------
from src.database.connection import (
    get_db_connection, 
    release_db_connection, 
    get_flask_db,
    execute_query as db_execute_query,
    init_app as init_db
)
logger.info("[OK] Using connection pool from src.database.connection")

# =====================================================================
# DATABASE HELPER FUNCTIONS - FIXED: Uses connection pool
# =====================================================================

def execute_query(query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[List[Tuple[Any, ...]]]:
    """
    Execute a PostgreSQL database query safely.
    FIXED: Uses connection pooling - ONE connection per request, not per query!
    """
    conn = None
    should_release = False
    
    try:
        # Use Flask's request-scoped connection if available
        if hasattr(g, 'db_conn') and g.db_conn:
            conn = g.db_conn
        else:
            conn = get_db_connection()
            should_release = True
        
        cur = conn.cursor()
        cur.execute(query, params or ())
        
        if query.strip().upper().startswith(('SELECT', 'WITH')):
            result = cur.fetchall()
        else:
            result = []
            conn.commit()
        
        cur.close()
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Error executing PostgreSQL query: {e}")
        logger.error(f"   Query: {query[:200]}...")
        if params:
            logger.error(f"   Params: {params}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return None
        
    finally:
        if should_release and 'conn' in locals() and conn:
            release_db_connection(conn)

def execute_query_with_conn(conn: Any, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[List[Tuple[Any, ...]]]:
    """
    Execute a PostgreSQL database query with existing connection.
    """
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        
        if query.strip().upper().startswith(('SELECT', 'WITH')):
            result = cur.fetchall()
        else:
            result = []
            conn.commit()
        
        cur.close()
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Error executing query with existing connection: {e}")
        logger.error(f"   Query: {query[:200]}...")
        conn.rollback()
        return None

# -------------------------------------------------------------------
# Password Helper Functions
# -------------------------------------------------------------------
def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        if not stored_hash or not provided_password:
            return False
        
        if stored_hash.startswith('$2') and len(stored_hash) > 50:
            return bcrypt.checkpw(
                provided_password.encode('utf-8'),
                stored_hash.encode('utf-8')
            )
        else:
            logger.warning("Password hash doesn't look like bcrypt, using fallback")
            return stored_hash == provided_password
            
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        return ""
    
def has_permission(user_role: str, min_required_role: str) -> bool:
    """Check if user has at least the required role level"""
    role_levels = {
        'user': 1,
        'staff': 2,
        'admin': 3,
        'superadmin': 4,
    }
    
    user_level = role_levels.get(user_role, 0)
    required_level = role_levels.get(min_required_role, 0)
    
    return user_level >= required_level

# -------------------------------------------------------------------
# Admin-only decorator (allows both admin and superadmin)
# -------------------------------------------------------------------
def admin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            abort(401)
        if not hasattr(current_user, 'role') or current_user.role not in ['superadmin', 'admin']:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

# -------------------------------------------------------------------
# SuperAdmin-only decorator
# -------------------------------------------------------------------
def superadmin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_user.is_authenticated:
            abort(401)
        if not hasattr(current_user, 'role') or current_user.role != 'superadmin':
            abort(403)
        return f(*args, **kwargs)
    return wrapper

# -------------------------------------------------------------------
# Role-based decorator
# -------------------------------------------------------------------
def role_required(*allowed_roles: str):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if not hasattr(current_user, 'role') or current_user.role not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------------------------------------------------
# Permission-based decorator
# -------------------------------------------------------------------
def permission_required(min_role: str) -> Callable[..., Any]:
    """Require at least the specified role level"""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if not hasattr(current_user, 'role') or not has_permission(current_user.role, min_role):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# -------------------------------------------------------------------
# Timed cache decorator
# -------------------------------------------------------------------
def timed_cache(seconds: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        cache: Dict[str, Tuple[float, Any]] = {}
        @wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            now = time.time()
            cache_key = f"{fn.__name__}:{str(args)}:{str(kwargs)}"
            if cache_key not in cache or now - cache[cache_key][0] > seconds:
                cache[cache_key] = (now, fn(*args, **kwargs))
            return cache[cache_key][1]
        return inner
    return wrapper

# -------------------------------------------------------------------
# Date Filter Builder for PostgreSQL
# -------------------------------------------------------------------
def build_date_filter(args: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """Build WHERE clause for date filtering in PostgreSQL."""
    conditions: List[str] = []
    params: List[Any] = []
    
    today = date.today()
    
    date_range = args.get("range")
    if date_range == "today":
        conditions.append("DATE(al.timestamp) = %s")
        params.append(today)
    elif date_range == "month":
        conditions.append("DATE_TRUNC('month', al.timestamp) = DATE_TRUNC('month', CURRENT_DATE)")
    
    start = args.get("start")
    end = args.get("end")
    
    if start:
        conditions.append("al.timestamp >= %s")
        params.append(start)
    if end:
        conditions.append("al.timestamp <= %s")
        params.append(end)
    
    return " AND ".join(conditions) if conditions else "1=1", params

# -------------------------------------------------------------------
# Simple User Class with bcrypt support
# -------------------------------------------------------------------
class SimpleUser(UserMixin):
    def __init__(self, user_id: str, username: str, role: str, password_hash: str = "", 
                 full_name: str = "", profile_image: str = "", email: str = ""):
        self.id = user_id
        self.username = username
        self.role = role.lower() if role else ''
        self.password_hash = password_hash
        self.full_name = full_name
        self.profile_image = profile_image  # ADD THIS
        self.email = email  # ADD THIS
    
    def verify_password(self, password: str) -> bool:
        return verify_password(self.password_hash, password)
    
    def is_admin(self) -> bool:
        return self.role in ['admin', 'superadmin', 'super_admin']
    
    def is_superadmin(self) -> bool:
        return self.role in ['superadmin', 'super_admin']
    
    @property
    def display_name(self):
        return self.full_name or self.username

# -------------------------------------------------------------------
# Anonymous User Class
# -------------------------------------------------------------------        
class AnonymousUser(AnonymousUserMixin):
    role = "guest"

# -------------------------------------------------------------------
# App Factory
# -------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(__name__)
      
    app.config['DEBUG'] = True
    app.config['SECRET_KEY'] = os.getenv('APP_SECRET_KEY', secrets.token_hex(32))
    app.config['WTF_CSRF_ENABLED'] = True 
    app.register_blueprint(access_point_api)

    from src.services.face_recognition_service import get_face_recognition_service
    face_service = get_face_recognition_service() 
    
    csrf.init_app(app)

    if app.debug:
        app.config.update(SESSION_COOKIE_SECURE=False)

    # ---------------- Initialize Real-time Features ----------------
    from src.database.firestore_realtime import realtime_manager, socketio
    realtime_manager.init_app(app)
    socketio.init_app(app)
    firestore_sync.init_firestore()

    def save_uploaded_file(file, student_id, registration_number, folder='students'):
        """
        Save uploaded file and return filename.
        Professional file handling with proper validation.
        """
        if not file or not file.filename:
            return None
        
        # Validate file type
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in ALLOWED_EXTENSIONS:
            return None
        
        # Validate file size (max 5MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 5 * 1024 * 1024:
            return None
        
        # Create upload directory
        static_folder = app.static_folder or os.path.join(app.root_path, 'static')
        upload_dir = os.path.join(static_folder, 'uploads', folder)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename - REPLACE SLASHES WITH UNDERSCORES
        from datetime import datetime
        import uuid
        
        # Convert registration number to safe filename (replace / with _)
        safe_reg = registration_number.replace('/', '_').replace('\\', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{folder}_{safe_reg}_{timestamp}_{unique_id}.{file_ext}"
        
        # Save file
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return filename

    # ========== Ensure Upload Directories ==========
    def ensure_upload_directories():
        """Ensure all upload directories exist"""
        static_folder = app.static_folder
        if not static_folder:
            static_folder = os.path.join(app.root_path, 'static')
        
        upload_dirs = [
            os.path.join(static_folder, 'uploads'),
            os.path.join(static_folder, 'uploads', 'students'),
            os.path.join(static_folder, 'uploads', 'profiles')
        ]
        
        for directory in upload_dirs:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")

    # Call it immediately
    ensure_upload_directories()
    
    # ---------------- Database Teardown ----------------
    @app.teardown_appcontext
    def close_db_connection(error=None):
        """Release database connection at the end of each request."""
        if hasattr(g, 'db_conn'):
            conn = g.db_conn
            if conn:
                release_db_connection(conn)
            del g.db_conn

    # ---------------- Real-time API Routes ----------------
    @app.route('/api/realtime/log_access', methods=['POST'])
    @login_required
    def realtime_log_access():
        """Log access and broadcast to all dashboards"""
        try:
            data = request.get_json()
            
            student_id = data.get('student_id')
            student_name = data.get('student_name', 'Unknown')
            method = data.get('verification_method')
            result = data.get('verification_result')
            score = data.get('match_score', 0)
            access_point = data.get('access_point', 'Main Gate')
            
            success = realtime_manager.log_realtime_access(
                student_id=student_id,
                student_name=student_name,
                method=method,
                result=result,
                score=score,
                access_point=access_point
            )
            
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error logging realtime access: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/realtime/dashboard_data')
    @login_required
    def realtime_dashboard_data():
        """Get real-time dashboard data"""
        data = realtime_manager.get_dashboard_data()
        return jsonify(data)

    @app.route('/api/realtime/device_status', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def realtime_update_device_status():
        """Update device status in real-time"""
        try:
            data = request.get_json()
            device_id = data.get('device_id')
            status = data.get('status')
            details = data.get('details', {})
            
            success = realtime_manager.update_device_status(device_id, status, details)
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return jsonify({'success': False, 'error': str(e)})

        # ---------------- Socket.IO Event Handlers ----------------
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection to SocketIO"""
        from flask import request as req
        from flask_socketio import emit
        logger.info(f"Client connected: {req.sid}")
        emit('connected', {'status': 'connected', 'message': 'Connected to real-time updates'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        from flask import request as req
        from flask_socketio import emit
        logger.info(f"Client disconnected: {req.sid}")

    @socketio.on('subscribe_dashboard')
    def handle_subscribe():
        """Client subscribes to dashboard updates"""
        from flask import request as req
        from flask_socketio import emit
        logger.info(f"Client subscribed to dashboard updates")
        data = realtime_manager.get_dashboard_data()
        emit('dashboard_init', data)

    # ---------------- Flask-Login ----------------
    login_manager = LoginManager()
    login_manager.anonymous_user = AnonymousUser
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[SimpleUser]:
        """Load user by ID for Flask-Login from PostgreSQL."""
        try:
            result = execute_query("""
                SELECT admin_id, username, password_hash, role, full_name, 
                    profile_image, email
                FROM administrators 
                WHERE admin_id = %s AND is_active = TRUE
            """, (user_id,))
            
            if result and len(result) > 0 and result[0]:
                row = result[0]
                return SimpleUser(
                    user_id=str(row[0]),
                    username=row[1],
                    password_hash=row[2],
                    role=row[3] if row[3] else "staff",
                    full_name=row[4] if len(row) > 4 else "",
                    profile_image=row[5] if len(row) > 5 else "",
                    email=row[6] if len(row) > 6 else ""
                )
        except Exception as e:
            logger.error(f"Error loading user from PostgreSQL: {e}")
        return None

    # ---------------- ROUTES ----------------
    @app.route('/')
    def index() -> Any:
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return redirect(url_for('dashboard'))

    # ---------------- LOGIN ---------------- 
    @app.route('/login', methods=['GET', 'POST'])
    def login() -> Any:
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('Username and password are required', 'danger')
                return render_template('login.html')
            
            try:
                from .services.admin_service import AdminService
                admin_service = AdminService()
                admin_data = admin_service.authenticate_admin(username, password)
                
                if admin_data:
                    if 'error' in admin_data:
                        flash(admin_data['error'], 'danger')
                        return render_template('login.html')
                    
                    full_name = admin_data.get('full_name', '')
                    if not full_name:
                        full_name = username.replace('_', ' ').replace('.', ' ').title()
                    
                    user = SimpleUser(
                        user_id=str(admin_data['admin_id']),
                        username=admin_data['username'],
                        role=admin_data['role'],
                        password_hash='',
                        full_name=full_name,
                        profile_image=admin_data.get('profile_image', ''),
                        email=admin_data.get('email', '')
                    )
                    
                    login_user(user, remember=True)
                    
                    session['admin_id'] = admin_data['admin_id']
                    session['username'] = admin_data['username']
                    session['full_name'] = full_name
                    session['role'] = admin_data['role']
                    session['email'] = admin_data.get('email', '')
                    session['profile_image'] = admin_data.get('profile_image', '')
                    
                    flash(f'Welcome back, {full_name}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password', 'danger')
                    
            except Exception as e:
                logger.error(f"Login error: {e}")
                flash('An error occurred during login', 'danger')
        
        return render_template('login.html')
    # ---------------- LOGOUT ----------------
    @app.route('/logout')
    @login_required
    def logout() -> Any:
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for('login'))

    # ---------------- DASHBOARD ----------------
    @app.route('/dashboard')
    @login_required
    def dashboard() -> Any:
        try:
            total_students_result = execute_query("SELECT COUNT(*) FROM students WHERE is_active = TRUE")
            total_students = total_students_result[0][0] if total_students_result and total_students_result[0] else 0
            
            today = date.today().isoformat()
            today_accesses_result = execute_query(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp) = %s",
                (today,)
            )
            today_accesses = today_accesses_result[0][0] if today_accesses_result and today_accesses_result[0] else 0
            
            granted_today_result = execute_query(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp) = %s AND verification_result = 'GRANTED'",
                (today,)
            )
            granted_today = granted_today_result[0][0] if granted_today_result and granted_today_result[0] else 0
            
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            weekly_accesses_result = execute_query(
                "SELECT COUNT(*) FROM access_logs WHERE timestamp >= %s",
                (week_ago,)
            )
            weekly_accesses = weekly_accesses_result[0][0] if weekly_accesses_result and weekly_accesses_result[0] else 0
            
            recent_activities_result = execute_query("""
                SELECT 
                    al.timestamp,
                    al.verification_method,
                    al.verification_result,
                    al.access_point,
                    COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') as student_name
                FROM access_logs al
                LEFT JOIN students s ON al.student_id = s.student_id
                ORDER BY al.timestamp DESC
                LIMIT 10
            """)
            
            recent_activities = []
            if recent_activities_result:
                for row in recent_activities_result:
                    recent_activities.append({
                        'timestamp': row[0],
                        'method': row[1],
                        'result': row[2],
                        'access_point': row[3],
                        'student_name': row[4]
                    })
            
            access_distribution_result = execute_query("""
                SELECT access_point, COUNT(*) as count
                FROM access_logs 
                WHERE access_point IS NOT NULL
                GROUP BY access_point
                ORDER BY count DESC
                LIMIT 5
            """)
            
            access_distribution = []
            if access_distribution_result:
                for row in access_distribution_result:
                    access_distribution.append({
                        'access_point': row[0],
                        'count': row[1]
                    })
            
            devices = []
            active_devices = 0
            devices_count = 0
            
            try:
                table_exists = execute_query("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'devices'
                    )
                """)
                
                if table_exists and table_exists[0][0]:
                    devices_data = execute_query("""
                        SELECT device_id, device_name, device_type, location, status, last_seen, ip_address
                        FROM devices
                        ORDER BY 
                            CASE status 
                                WHEN 'online' THEN 1
                                WHEN 'maintenance' THEN 2
                                WHEN 'offline' THEN 3
                                ELSE 4
                            END,
                            device_name
                    """)
                    
                    if devices_data:
                        for row in devices_data:
                            devices.append({
                                'device_id': row[0],
                                'device_name': row[1],
                                'device_type': row[2],
                                'location': row[3],
                                'status': row[4],
                                'last_seen': row[5],
                                'ip_address': row[6]
                            })
                        
                        active_devices = sum(1 for d in devices if d.get('status') == 'online')
                        devices_count = len(devices)
            except Exception as e:
                logger.warning(f"Could not fetch devices: {e}")
            
            system_status = "Online" if active_devices > 0 else "Offline"
            
            system_info = {
                'database_status': 'Connected',
                'storage_usage': 'Normal',
                'memory_usage': '45%',
                'network_status': 'Online',
                'last_backup': '2024-06-01 02:00:00',
                'server_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'total_students': total_students,
                'total_access_today': today_accesses,
                'access_granted_today': granted_today,
                'access_denied_today': today_accesses - granted_today,
                'system_health': 'Good',
                'connected_devices': devices_count,
                'online_devices': active_devices,
                'offline_devices': devices_count - active_devices,
                'device_status': {d['device_name']: d['status'] for d in devices} if devices else {},
                'total_access_points': len(access_distribution),
                'top_access_points': access_distribution,
                'active_devices': active_devices,
                'uptime': '24h 15m'
            }
            
            return render_template(
                'dashboard.html',
                user=current_user,
                total_students=total_students,
                today_accesses=today_accesses,
                weekly_accesses=weekly_accesses,
                granted_today=granted_today,
                recent_activities=recent_activities,
                access_distribution=access_distribution,
                system_info=system_info,
                devices=devices,
                devices_count=devices_count,
                active_devices=active_devices,
                offline_devices=devices_count - active_devices,
                system_status=system_status
            )
            
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")
            return render_template(
                'dashboard.html',
                user=current_user,
                total_students=0,
                today_accesses=0,
                weekly_accesses=0,
                granted_today=0,
                recent_activities=[],
                access_distribution=[],
                system_info={
                    'database_status': 'Error',
                    'storage_usage': 'Unknown',
                    'active_devices': 0,
                    'uptime': '0h 0m'
                },
                devices=[],
                devices_count=0,
                active_devices=0,
                offline_devices=0,
                system_status="Error"
            )
    
    @app.route('/dashboard/quick_stats')
    @login_required
    @timed_cache(15)
    def dashboard_quick_stats():
        """Get real-time dashboard statistics from database"""
        error_message = None
        
        try:
            stats = execute_query("""
                SELECT 
                    (SELECT COUNT(*) FROM students WHERE is_active = TRUE) as total_students,
                    (SELECT COUNT(DISTINCT student_id) FROM access_logs 
                    WHERE DATE(timestamp) = CURRENT_DATE) as active_today,
                    (SELECT COUNT(*) FROM access_logs 
                    WHERE DATE(timestamp) = CURRENT_DATE 
                    AND verification_result = 'GRANTED') as granted_today,
                    (SELECT COUNT(*) FROM devices WHERE status = 'online') as online_devices,
                    (SELECT COUNT(*) FROM devices) as total_devices,
                    (SELECT COUNT(*) FROM access_logs 
                    WHERE timestamp >= NOW() - INTERVAL '7 days') as weekly_accesses
            """)
            
            if stats and stats[0]:
                return jsonify({
                    'students': stats[0][0] or 0,
                    'attendance_today': stats[0][1] or 0,
                    'granted_today': stats[0][2] or 0,
                    'devices_online': stats[0][3] or 0,
                    'total_devices': stats[0][4] or 0,
                    'weekly': stats[0][5] or 0,
                    'last_updated': datetime.now().isoformat()
                })
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error getting quick stats: {error_message}")
        
        response = {
            'students': 0,
            'attendance_today': 0,
            'granted_today': 0,
            'devices_online': 0,
            'total_devices': 0,
            'weekly': 0,
            'last_updated': datetime.now().isoformat()
        }
        
        if error_message:
            response['error'] = error_message
            return jsonify(response), 500
        else:
            response['warning'] = 'No data available'
            return jsonify(response), 200

    @app.route('/dashboard/realtime')
    @login_required
    @timed_cache(10)
    def dashboard_realtime() -> Response:
        try:
            today = date.today().isoformat()
            
            active_sessions_result = execute_query(
                "SELECT COUNT(DISTINCT student_id) FROM access_logs WHERE DATE(timestamp) = %s",
                (today,)
            )
            active_sessions = active_sessions_result[0][0] if active_sessions_result and active_sessions_result[0] else 0
            
            granted_result = execute_query(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp) = %s AND verification_result = 'GRANTED'",
                (today,)
            )
            access_granted = granted_result[0][0] if granted_result and granted_result[0] else 0
            
            denied_result = execute_query(
                "SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp) = %s AND verification_result = 'DENIED'",
                (today,)
            )
            access_denied = denied_result[0][0] if denied_result and denied_result[0] else 0
            
            return jsonify({
                "active_sessions": active_sessions,
                "access_granted_today": access_granted,
                "access_denied_today": access_denied,
                "system_status": "online"
            })
        except Exception as e:
            logger.error(f"Error getting realtime stats: {e}")
            return jsonify({
                "active_sessions": 0,
                "access_granted_today": 0,
                "access_denied_today": 0,
                "system_status": "error"
            })
    
    @app.route('/dashboard/access_points')
    @login_required
    def get_access_points() -> Response:
        result = execute_query(
            "SELECT DISTINCT access_point FROM access_logs WHERE access_point IS NOT NULL ORDER BY access_point"
        )
        if result:
            points = [p[0] for p in result if p[0]]
            return jsonify(points)
        return jsonify([])

    # ---------------- SYSTEM SETTINGS ----------------
    @app.route('/system-settings')
    @login_required
    def system_settings() -> Any:
        try:
            settings_exists = execute_query("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'system_settings'
                )
            """)
            
            settings = {}
            if settings_exists and settings_exists[0][0]:
                settings_result = execute_query("SELECT setting_name, setting_value FROM system_settings")
                if settings_result:
                    for row in settings_result:
                        settings[row[0]] = row[1]
            else:
                settings = {
                    'system_name': 'Biometric Access System',
                    'session_timeout': '30',
                    'backup_frequency': 'daily',
                    'log_retention_days': '30',
                    'email_notifications': 'enabled',
                    'maintenance_mode': 'disabled',
                    'max_login_attempts': '5',
                    'auto_logout_minutes': '15',
                    'backup_path': '/backups/',
                    'log_level': 'INFO'
                }
            
            server_info = {
                'hostname': socket.gethostname(),
                'os': platform.system() + ' ' + platform.release(),
                'python_version': platform.python_version(),
                'cpu_cores': psutil.cpu_count(),
                'memory_total': f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                'disk_usage': f"{psutil.disk_usage('/').percent}%",
                'flask_version': flask.__version__,
                'uptime': str(datetime.now() - datetime.fromtimestamp(psutil.boot_time()))
            }
            
            return render_template(
                'system_settings.html',
                user=current_user,
                settings=settings,
                server_info=server_info
            )
            
        except Exception as e:
            logger.error(f"Error loading system settings: {e}")
            return render_template(
                'system_settings.html',
                user=current_user,
                settings={},
                server_info={},
                error=str(e)
            )

    @app.route('/camera-capture')
    @login_required
    def camera_capture():
        """Open camera capture page"""
        student_id = request.args.get('student_id')
        user_id = request.args.get('user_id')
        registration_number = request.args.get('registration_number', '')
        username = request.args.get('username', '')
        capture_type = request.args.get('type', 'student')  # 'student' or 'user'
        
        return render_template('camera_capture.html', 
                            student_id=student_id,
                            user_id=user_id,
                            registration_number=registration_number,
                            username=username,
                            capture_type=capture_type)

    @app.route('/students/save-photo', methods=['POST'])
    @login_required
    def save_student_photo():
        """Save photo captured from camera for students or users"""
        try:
            data = request.get_json()
            student_id = data.get('student_id')
            user_id = data.get('user_id')
            image_data = data.get('image_data')
            capture_type = data.get('capture_type', 'student')
            
            if not image_data:
                return jsonify({'success': False, 'error': 'No image data'})
            
            # Decode base64 image
            import base64
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            
            # Create upload directory
            static_folder = app.static_folder or os.path.join(app.root_path, 'static')
            
            if capture_type == 'student':
                upload_dir = os.path.join(static_folder, 'uploads', 'students')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Get student info
                reg_result = execute_query(
                    "SELECT registration_number FROM students WHERE student_id = %s",
                    (student_id,)
                )
                reg_number = reg_result[0][0] if reg_result else str(student_id)
                safe_reg = reg_number.replace('/', '_').replace('\\', '_')
                
                from datetime import datetime
                import uuid
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"students_{safe_reg}_{timestamp}_{unique_id}.jpg"
                
                # Save file
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                
                # Update database
                old_result = execute_query(
                    "SELECT profile_image FROM students WHERE student_id = %s",
                    (student_id,)
                )
                old_image = old_result[0][0] if old_result else None
                
                execute_query("""
                    UPDATE students SET profile_image = %s, updated_at = NOW()
                    WHERE student_id = %s
                """, (filename, student_id))
                
                # Delete old image
                if old_image:
                    old_path = os.path.join(upload_dir, old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                        
            else:  # user
                upload_dir = os.path.join(static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                from datetime import datetime
                import uuid
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                filename = f"profile_{user_id}_{timestamp}_{unique_id}.jpg"
                
                # Save file
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                
                # Update database
                old_result = execute_query(
                    "SELECT profile_image FROM administrators WHERE admin_id = %s",
                    (user_id,)
                )
                old_image = old_result[0][0] if old_result else None
                
                execute_query("""
                    UPDATE administrators SET profile_image = %s, updated_at = NOW()
                    WHERE admin_id = %s
                """, (filename, user_id))
                
                # Delete old image
                if old_image:
                    old_path = os.path.join(upload_dir, old_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
            
            return jsonify({'success': True, 'filename': filename})
            
        except Exception as e:
            logger.error(f"Error saving photo: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
# =====================================================================
# ACCESS POINTS - FIXED to link with devices
# =====================================================================

    @app.route('/access-points')
    @login_required
    @role_required('superadmin', 'admin')
    def access_points():
        """Access points management page - linked to devices."""
        try:
            # Create access_points table if not exists
            execute_query("""
                CREATE TABLE IF NOT EXISTS access_points (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    location VARCHAR(200),
                    device_id INTEGER REFERENCES devices(id),
                    device_type VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'active',
                    description TEXT,
                    last_activity TIMESTAMP,
                    total_accesses INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Get access points with device info
            points = execute_query("""
                SELECT 
                    ap.id, ap.name, ap.location, ap.device_type, ap.status,
                    ap.last_activity, ap.total_accesses, ap.description,
                    ap.created_at, ap.updated_at,
                    d.id as device_id, d.device_name, d.device_id as device_code,
                    d.device_type as actual_device_type
                FROM access_points ap
                LEFT JOIN devices d ON ap.device_id = d.id
                ORDER BY ap.name
            """)
            
            # Get all devices for dropdown
            devices = execute_query("""
                SELECT id, device_id, device_name, device_type, location, status
                FROM devices
                ORDER BY device_name
            """)
            
            device_list = []
            if devices:
                for row in devices:
                    device_list.append({
                        'id': row[0],
                        'device_id': row[1],
                        'device_name': row[2],
                        'device_type': row[3],
                        'location': row[4],
                        'status': row[5]
                    })
            
            access_points = []
            active_count = 0
            maintenance_count = 0
            inactive_count = 0
            labels = []
            data = []
            
            if points:
                for row in points:
                    point = {
                        'id': row[0],
                        'name': row[1],
                        'location': row[2],
                        'device_type': row[3] or 'Standard',
                        'status': row[4] if row[4] else 'active',
                        'last_activity': row[5],
                        'total_accesses': row[6] or 0,
                        'description': row[7] or '',
                        'created_at': row[8],
                        'updated_at': row[9],
                        'device_id': row[10],
                        'device_name': row[11],
                        'device_code': row[12],
                        'actual_device_type': row[13]
                    }
                    access_points.append(point)
                    labels.append(point['name'])
                    data.append(point['total_accesses'])
                    
                    if point['status'] == 'active':
                        active_count += 1
                    elif point['status'] == 'maintenance':
                        maintenance_count += 1
                    else:
                        inactive_count += 1
            
            return render_template('access_points.html',
                                access_points=access_points,
                                devices=device_list,
                                access_points_labels=labels,
                                access_points_data=data,
                                active_count=active_count,
                                maintenance_count=maintenance_count,
                                inactive_count=inactive_count,
                                user=current_user,
                                now=datetime.now)
        except Exception as e:
            logger.error(f"Error loading access points: {e}")
            return render_template('access_points.html', 
                                access_points=[],
                                devices=[],
                                user=current_user,
                                now=datetime.now)

    @app.route('/api/access-points/add', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def add_access_point():
        """Add a new access point linked to a device."""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            location = data.get('location', '').strip()
            device_id = data.get('device_id', '').strip()
            status = data.get('status', 'active')
            description = data.get('description', '').strip()
            
            if not name:
                return jsonify({'success': False, 'error': 'Access point name is required'})
            
            if not device_id:
                return jsonify({'success': False, 'error': 'Please select a device to assign'})
            
            # Get device info
            device = execute_query("""
                SELECT id, device_type FROM devices WHERE id = %s
            """, (device_id,))
            
            if not device:
                return jsonify({'success': False, 'error': 'Selected device not found'})
            
            device_type = device[0][1] if device else 'Standard'
            
            result = execute_query("""
                INSERT INTO access_points 
                (name, location, device_id, device_type, status, description, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (name, location, device_id, device_type, status, description))
            
            if result:
                return jsonify({'success': True, 'id': result[0][0]})
            return jsonify({'success': False, 'error': 'Failed to add access point'})
            
        except Exception as e:
            logger.error(f"Error adding access point: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/access-points/<int:point_id>')
    @login_required
    @role_required('superadmin', 'admin')
    def get_access_point(point_id):
        """Get access point details with device info."""
        try:
            result = execute_query("""
                SELECT 
                    ap.id, ap.name, ap.location, ap.device_type, ap.status,
                    ap.last_activity, ap.total_accesses, ap.description,
                    ap.created_at, ap.updated_at,
                    ap.device_id,
                    d.device_name, d.device_id as device_code
                FROM access_points ap
                LEFT JOIN devices d ON ap.device_id = d.id
                WHERE ap.id = %s
            """, (point_id,))
            
            if result:
                row = result[0]
                point = {
                    'id': row[0],
                    'name': row[1],
                    'location': row[2],
                    'device_type': row[3],
                    'status': row[4],
                    'last_activity': row[5],
                    'total_accesses': row[6] or 0,
                    'description': row[7],
                    'created_at': row[8],
                    'updated_at': row[9],
                    'device_id': row[10],
                    'device': {
                        'id': row[10],
                        'device_name': row[11],
                        'device_id': row[12]
                    } if row[10] else None
                }
                return jsonify({'success': True, 'point': point})
            return jsonify({'success': False, 'error': 'Access point not found'})
            
        except Exception as e:
            logger.error(f"Error getting access point: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/access-points/<int:point_id>/edit', methods=['PUT'])
    @login_required
    @role_required('superadmin', 'admin')
    def edit_access_point(point_id):
        """Edit access point."""
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            location = data.get('location', '').strip()
            device_id = data.get('device_id', '').strip()
            status = data.get('status', 'active')
            description = data.get('description', '').strip()
            
            if not name:
                return jsonify({'success': False, 'error': 'Access point name is required'})
            
            if not device_id:
                return jsonify({'success': False, 'error': 'Please select a device to assign'})
            
            # Get device info
            device = execute_query("""
                SELECT id, device_type FROM devices WHERE id = %s
            """, (device_id,))
            
            if not device:
                return jsonify({'success': False, 'error': 'Selected device not found'})
            
            device_type = device[0][1] if device else 'Standard'
            
            execute_query("""
                UPDATE access_points 
                SET name = %s, location = %s, device_id = %s, 
                    device_type = %s, status = %s, description = %s, 
                    updated_at = NOW()
                WHERE id = %s
            """, (name, location, device_id, device_type, status, description, point_id))
            
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Error editing access point: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/access-points/<int:point_id>/delete', methods=['DELETE'])
    @login_required
    @role_required('superadmin', 'admin')
    def delete_access_point(point_id):
        """Delete access point."""
        try:
            execute_query("DELETE FROM access_points WHERE id = %s", (point_id,))
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Error deleting access point: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/access-points/export')
    @login_required
    @role_required('superadmin', 'admin')
    def export_access_points():
        """Export access points to CSV."""
        try:
            points = execute_query("""
                SELECT 
                    ap.id, ap.name, ap.location, ap.device_type, ap.status,
                    ap.total_accesses, ap.created_at, ap.updated_at,
                    d.device_name as device_name
                FROM access_points ap
                LEFT JOIN devices d ON ap.device_id = d.id
                ORDER BY ap.name
            """)
            
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Name', 'Location', 'Device Type', 'Status', 
                            'Total Accesses', 'Device Name', 'Created At', 'Updated At'])
            
            if points:
                for row in points:
                    writer.writerow(row)
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=access_points.csv'}
            )
            
        except Exception as e:
            logger.error(f"Error exporting access points: {e}")
            return jsonify({'success': False, 'error': str(e)})
      
    @app.route('/update-settings', methods=['POST'])
    @login_required
    def update_settings() -> Any:
        if request.method != 'POST':
            abort(405)
        
        try:
            data = request.form.to_dict()
            
            execute_query("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id SERIAL PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            for key, value in data.items():
                execute_query("""
                    INSERT INTO system_settings (setting_name, setting_value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (setting_name) 
                    DO UPDATE SET setting_value = EXCLUDED.setting_value,
                                updated_at = CURRENT_TIMESTAMP
                """, (key, value))
            
            flash('System settings updated successfully!', 'success')
            return redirect(url_for('system_settings'))
                
        except Exception as e:
            logger.error(f"Error updating system settings: {e}")
            flash(f'Error updating settings: {str(e)}', 'danger')
            return redirect(url_for('system_settings'))
    
    @app.context_processor
    def utility_processor() -> Dict[str, Any]:
        from datetime import datetime
        
        def is_admin() -> bool:
            if not hasattr(current_user, 'role') or not current_user.is_authenticated:
                return False
            user_role = current_user.role.lower() if current_user.role else ''
            return user_role in ['admin', 'superadmin', 'super_admin']
        
        def is_superadmin() -> bool:
            if not hasattr(current_user, 'role') or not current_user.is_authenticated:
                return False
            user_role = current_user.role.lower() if current_user.role else ''
            return user_role in ['superadmin', 'super_admin']
        
        def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
            if value is None:
                return ''
            return value.strftime(format)
        
        return dict(
            now=datetime.now,
            today=datetime.now().date,
            is_admin=is_admin,
            is_superadmin=is_superadmin,
            format_datetime=format_datetime
        )
    
    # ---------------- DATABASE MANAGEMENT ----------------
    @app.route('/database')
    @login_required
    @role_required('superadmin')
    def database_management() -> Any:
        try:
            db_size_result = execute_query("""
                SELECT pg_database_size(current_database()) as size_bytes
            """)
            db_size_bytes = db_size_result[0][0] if db_size_result and db_size_result[0] else 0
            db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
            
            tables_result = execute_query("""
                SELECT 
                    table_name,
                    pg_relation_size(quote_ident(table_name)) as size_bytes,
                    (SELECT count(*) FROM information_schema.columns 
                     WHERE table_name = t.table_name) as column_count,
                    (SELECT count(*) FROM information_schema.table_privileges 
                     WHERE table_name = t.table_name) as privilege_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            
            tables = []
            if tables_result:
                for row in tables_result:
                    tables.append({
                        'name': row[0],
                        'size_mb': round(row[1] / (1024 * 1024), 2) if row[1] else 0,
                        'column_count': row[2],
                        'privilege_count': row[3]
                    })
            
            stats_result = execute_query("""
                SELECT 
                    (SELECT count(*) FROM students WHERE is_active = TRUE) as student_count,
                    (SELECT count(*) FROM administrators WHERE is_active = TRUE) as admin_count,
                    (SELECT count(*) FROM access_logs) as access_log_count,
                    (SELECT count(*) FROM devices) as device_count
            """)
            
            stats = {}
            if stats_result and stats_result[0]:
                stats = {
                    'students': stats_result[0][0] or 0,
                    'admins': stats_result[0][1] or 0,
                    'access_logs': stats_result[0][2] or 0,
                    'devices': stats_result[0][3] or 0
                }
            
            recent_backups = []
            
            return render_template(
                'database.html',
                user=current_user,
                db_size_mb=db_size_mb,
                tables=tables,
                stats=stats,
                recent_backups=recent_backups
            )
            
        except Exception as e:
            logger.error(f"Error loading database page: {e}")
            return render_template(
                'database.html',
                user=current_user,
                error=str(e)
            )
    
    @app.route('/database/backup', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def create_backup() -> Response:
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.sql"
            backup_path = os.path.join('backups', backup_filename)
            
            os.makedirs('backups', exist_ok=True)
            
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DB_NAME', 'biometric_access_db')
            db_user = os.getenv('DB_USER', 'postgres')
            db_password = os.getenv('DB_PASSWORD', '2546')
            
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
            
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-f', backup_path,
                '--clean',
                '--if-exists'
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': f'Backup created successfully: {backup_filename}',
                    'filename': backup_filename,
                    'size': os.path.getsize(backup_path),
                    'timestamp': timestamp
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Backup failed: {result.stderr}'
                })
                
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/database/restore', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def restore_backup() -> Response:
        try:
            data = request.get_json()
            if not data or 'filename' not in data:
                return jsonify({'success': False, 'error': 'No filename provided'})
            
            filename = data['filename']
            backup_path = os.path.join('backups', filename)
            
            if not os.path.exists(backup_path):
                return jsonify({'success': False, 'error': 'Backup file not found'})
            
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DB_NAME', 'biometric_access_db')
            db_user = os.getenv('DB_USER', 'postgres')
            db_password = os.getenv('DB_PASSWORD', '2546')
            
            env = os.environ.copy()
            if db_password:
                env['PGPASSWORD'] = db_password
            
            cmd = [
                'psql',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-d', db_name,
                '-f', backup_path
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': f'Database restored from: {filename}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Restore failed: {result.stderr}'
                })
                
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/database/query', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def execute_database_query() -> Response:
        try:
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({'success': False, 'error': 'No query provided'})
            
            query = data['query'].strip()
            
            destructive_keywords = ['DROP', 'TRUNCATE', 'DELETE FROM', 'UPDATE']
            if any(keyword in query.upper() for keyword in destructive_keywords):
                if not data.get('confirmed', False):
                    return jsonify({
                        'success': False,
                        'needs_confirmation': True,
                        'warning': 'This query contains potentially destructive operations. Please confirm.'
                    })
            
            result = execute_query(query)
            
            if result is None:
                return jsonify({'success': False, 'error': 'Query execution failed'})
            
            if query.strip().upper().startswith('SELECT'):
                columns = []
                if result and len(result) > 0:
                    try:
                        conn = get_db_connection()
                        if conn:
                            cur = conn.cursor()
                            try:
                                clean_query = query.rstrip(';')
                                cur.execute(f"SELECT * FROM ({clean_query}) as t LIMIT 0")
                                if cur.description:
                                    columns = [desc[0] for desc in cur.description]
                            except Exception as query_error:
                                logger.error(f"Error getting column names: {query_error}")
                                columns = []
                            finally:
                                cur.close()
                                release_db_connection(conn)
                    except Exception as e:
                        logger.error(f"Database connection error: {e}")
                        columns = []
                
                return jsonify({
                    'success': True,
                    'columns': columns,
                    'results': result,
                    'affected_rows': len(result)
                })
            else:
                return jsonify({
                    'success': True,
                    'message': 'Query executed successfully',
                    'affected_rows': len(result) if result else 0
                })
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/database/optimize', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def optimize_database() -> Response:
        try:
            tables_result = execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            optimized_tables = []
            if tables_result:
                for table in tables_result:
                    table_name = table[0]
                    execute_query(f'VACUUM ANALYZE "{table_name}"')
                    optimized_tables.append(table_name)
            
            return jsonify({
                'success': True,
                'message': f'Optimized {len(optimized_tables)} tables',
                'tables': optimized_tables
            })
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            return jsonify({'success': False, 'error': str(e)})
        
    @app.route('/database/optimize-table', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def optimize_single_table() -> Response:
        """Optimize a specific database table."""
        try:
            data = request.get_json()
            if not data or 'table' not in data:
                return jsonify({'success': False, 'error': 'No table name provided'})
            
            table_name = data['table']
            
            allowed_tables = execute_query("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            table_names = [t[0] for t in allowed_tables] if allowed_tables else []
            
            if table_name not in table_names:
                return jsonify({'success': False, 'error': 'Invalid table name'})
            
            execute_query(f'VACUUM ANALYZE "{table_name}"')
            
            return jsonify({
                'success': True,
                'message': f'Table "{table_name}" optimized successfully'
            })
            
        except Exception as e:
            logger.error(f"Error optimizing table: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    # ---------------- SYSTEM STATUS ----------------
    @app.route('/system/status')
    @login_required
    @role_required('superadmin', 'admin')
    def system_status_page():
        """System status page with real data."""
        try:
            import psutil
            import platform
            import flask
            
            system_info = {
                'os': platform.system(),
                'os_version': platform.version(),
                'python_version': platform.python_version(),
                'hostname': platform.node(),
                'architecture': platform.architecture()[0],
                'processor': platform.processor(),
                'flask_version': flask.__version__
            }
            
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            memory = psutil.virtual_memory()
            memory_info = {
                'percent': memory.percent,
                'total_gb': round(memory.total / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2)
            }
            
            disk = psutil.disk_usage('/')
            disk_info = {
                'percent': disk.percent,
                'total_gb': round(disk.total / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2)
            }
            
            net_io = psutil.net_io_counters()
            network_info = {
                'bytes_sent_mb': round(net_io.bytes_sent / (1024**2), 2),
                'bytes_recv_mb': round(net_io.bytes_recv / (1024**2), 2),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
            
            db_status = 'Connected'
            db_details = {}
            
            try:
                version_result = execute_query("SELECT version()")
                if version_result and version_result[0]:
                    db_version = version_result[0][0].split()[1]
                    db_details['version'] = db_version
                else:
                    db_details['version'] = 'Unknown'
                
                table_result = execute_query("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                db_details['table_count'] = table_result[0][0] if table_result else 0
                
                size_result = execute_query("""
                    SELECT pg_database_size(current_database()) as size_bytes
                """)
                if size_result and size_result[0]:
                    db_details['size_mb'] = round(size_result[0][0] / (1024 * 1024), 2)
                else:
                    db_details['size_mb'] = 0
                
                conn_result = execute_query("""
                    SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'
                """)
                db_details['active_connections'] = conn_result[0][0] if conn_result else 0
                
                cache_result = execute_query("""
                    SELECT 
                        round(blks_hit::numeric / (blks_read + blks_hit) * 100, 2) as cache_hit
                    FROM pg_stat_database 
                    WHERE datname = current_database()
                """)
                db_details['cache_hit_ratio'] = cache_result[0][0] if cache_result and cache_result[0][0] else 0
                
            except Exception as e:
                logger.error(f"Error getting database details: {e}")
                db_status = 'Error'
                db_details = {
                    'version': 'Unknown',
                    'table_count': 0,
                    'size_mb': 0,
                    'active_connections': 0,
                    'cache_hit_ratio': 0
                }
            
            app_stats = {
                'uptime': str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0],
                'active_sessions': 1,
                'request_count': 0,
                'avg_response_time': 0
            }
            
            services = []
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                    try:
                        pinfo = proc.info
                        services.append({
                            'pid': pinfo['pid'],
                            'name': pinfo['name'][:50] if pinfo['name'] else 'Unknown',
                            'cpu_percent': round(pinfo['cpu_percent'] or 0, 1),
                            'memory_percent': round(pinfo['memory_percent'] or 0, 1),
                            'status': pinfo['status']
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                services.sort(key=lambda x: x['cpu_percent'], reverse=True)
                services = services[:20]
                
            except Exception as e:
                logger.error(f"Error getting processes: {e}")
                services = []
            
            return render_template(
                'system_status.html',
                user=current_user,
                system_info=system_info,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                memory_info=memory_info,
                disk_info=disk_info,
                network_info=network_info,
                db_status=db_status,
                db_details=db_details,
                app_stats=app_stats,
                services=services
            )
            
        except Exception as e:
            logger.error(f"Error loading system status: {e}")
            return render_template(
                'system_status.html',
                user=current_user,
                error=str(e),
                system_info={},
                cpu_percent=0,
                cpu_count=0,
                memory_info={'percent': 0, 'total_gb': 0, 'used_gb': 0},
                disk_info={'percent': 0, 'total_gb': 0, 'used_gb': 0},
                network_info={'bytes_sent_mb': 0, 'bytes_recv_mb': 0},
                db_status='Error',
                db_details={'version': 'N/A', 'table_count': 0, 'size_mb': 0, 'active_connections': 0, 'cache_hit_ratio': 0},
                app_stats={'uptime': '0s', 'active_sessions': 0, 'request_count': 0, 'avg_response_time': 0},
                services=[]
            )
    
    @app.route('/system/health')
    @login_required
    @role_required('superadmin', 'admin')
    def system_health() -> Response:
        """Get real-time system health status"""
        try:
            import psutil
            
            health_status = {
                'status': 'healthy',
                'checks': []
            }
            
            cpu_percent = psutil.cpu_percent(interval=1)
            health_status['checks'].append({
                'component': 'CPU',
                'status': 'healthy' if cpu_percent < 70 else ('warning' if cpu_percent < 90 else 'error'),
                'value': f'{cpu_percent}%',
                'threshold': '90%'
            })
            
            memory = psutil.virtual_memory()
            health_status['checks'].append({
                'component': 'Memory',
                'status': 'healthy' if memory.percent < 70 else ('warning' if memory.percent < 85 else 'error'),
                'value': f'{memory.percent}%',
                'threshold': '85%'
            })
            
            disk = psutil.disk_usage('/')
            health_status['checks'].append({
                'component': 'Disk',
                'status': 'healthy' if disk.percent < 70 else ('warning' if disk.percent < 90 else 'error'),
                'value': f'{disk.percent}%',
                'threshold': '90%'
            })
            
            try:
                db_test = execute_query("SELECT 1")
                db_ok = db_test is not None
                health_status['checks'].append({
                    'component': 'Database',
                    'status': 'healthy' if db_ok else 'error',
                    'value': 'Connected' if db_ok else 'Disconnected',
                    'threshold': 'Connected'
                })
            except:
                health_status['checks'].append({
                    'component': 'Database',
                    'status': 'error',
                    'value': 'Error',
                    'threshold': 'Connected'
                })
            
            if any(check['status'] == 'error' for check in health_status['checks']):
                health_status['status'] = 'error'
            elif any(check['status'] == 'warning' for check in health_status['checks']):
                health_status['status'] = 'warning'
            
            health_status['timestamp'] = datetime.now().isoformat()
            
            return jsonify(health_status)
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }) 

    @app.route('/system/status-data')
    @login_required
    def system_status_data():
        """Get real-time system status data for auto-refresh"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            
            memory = psutil.virtual_memory()
            
            disk = psutil.disk_usage('/')
            
            net_io = psutil.net_io_counters()
            
            db_stats = execute_query("""
                SELECT 
                    (SELECT count(*) FROM information_schema.tables 
                    WHERE table_schema = 'public') as table_count,
                    (SELECT count(*) FROM pg_stat_activity) as connections,
                    (SELECT round(blks_hit::numeric/(blks_read+blks_hit)*100,2) 
                    FROM pg_stat_database WHERE datname = current_database()) as cache_hit
            """)
            
            data = {
                'success': True,
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'percent': memory.percent,
                    'total_gb': round(memory.total / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2)
                },
                'disk': {
                    'percent': disk.percent,
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2)
                },
                'network': {
                    'bytes_sent_mb': round(net_io.bytes_sent / (1024**2), 2),
                    'bytes_recv_mb': round(net_io.bytes_recv / (1024**2), 2),
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                },
                'database': {
                    'table_count': db_stats[0][0] if db_stats else 0,
                    'active_connections': db_stats[0][1] if db_stats else 0,
                    'cache_hit_ratio': db_stats[0][2] if db_stats else 0
                },
                'app': {
                    'uptime': str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0],
                    'active_sessions': 1,
                    'request_count': 0,
                    'avg_response_time': 0
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(data)
            
        except Exception as e:
            logger.error(f"Error getting system status data: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/system/processes')
    @login_required
    def system_processes():
        """Get list of running processes"""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    pinfo = proc.info
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'][:50],
                        'cpu_percent': round(pinfo['cpu_percent'] or 0, 1),
                        'memory_percent': round(pinfo['memory_percent'] or 0, 1),
                        'status': pinfo['status']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            
            return jsonify({
                'success': True,
                'processes': processes[:20]
            })
            
        except Exception as e:
            logger.error(f"Error getting processes: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/restart-system', methods=['POST'])
    @login_required
    def restart_system_api():
        """Restart system services"""
        try:
            logger.warning(f"System restart requested by user: {current_user.username}")
            
            return jsonify({
                'success': True,
                'message': 'System restart initiated',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error restarting system: {e}")
            return jsonify({'success': False, 'error': str(e)})   
    
    # ---------------- CONFIGURATION ----------------
    @app.route('/configuration')
    @login_required
    @role_required('superadmin', 'admin')
    def configuration() -> Any:
        try:
            config = {
                'app_name': 'Biometric Student Access System',
                'app_version': '1.0.0',
                'debug_mode': app.config.get('DEBUG', False),
                'secret_key_set': bool(app.config.get('SECRET_KEY')),
                'session_lifetime': app.config.get('PERMANENT_SESSION_LIFETIME', 1800),
                
                'database': {
                    'host': os.getenv('DB_HOST', 'localhost'),
                    'port': os.getenv('DB_PORT', '5432'),
                    'name': os.getenv('DB_NAME', 'biometric_access_db'),
                    'user': os.getenv('DB_USER', 'postgres')
                },
                
                'security': {
                    'password_min_length': 8,
                    'password_require_special': True,
                    'password_require_numbers': True,
                    'password_require_uppercase': True,
                    'max_login_attempts': 5,
                    'lockout_duration': 900
                },
                
                'biometric': {
                    'match_threshold': 75.0,
                    'max_attempts': 3,
                    'timeout_seconds': 30
                },
                
                'logging': {
                    'level': 'INFO',
                    'max_file_size_mb': 10,
                    'backup_count': 5
                },
                
                'backup': {
                    'auto_backup': True,
                    'backup_interval_hours': 24,
                    'keep_backups_days': 30,
                    'backup_path': 'backups/'
                }
            }
            
            if isinstance(config['session_lifetime'], timedelta):
                config['session_lifetime'] = config['session_lifetime'].total_seconds()
            
            return render_template(
                'configuration.html',
                user=current_user,
                config=config
            )
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return render_template(
                'configuration.html',
                user=current_user,
                error=str(e)
            )
    
    @app.route('/configuration/save', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def save_configuration() -> Response:
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No configuration data provided'})
            
            required_fields = ['app_name', 'debug_mode']
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'error': f'Missing required field: {field}'})
            
            logger.info(f"Configuration saved by user: {current_user.username}")
            
            return jsonify({
                'success': True,
                'message': 'Configuration saved successfully',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/configuration/export')
    @login_required
    @role_required('superadmin', 'admin')
    def export_configuration() -> Response:
        try:
            config_data = {
                'app': {
                    'name': 'Biometric Student Access System',
                    'version': '1.0.0',
                    'debug': app.config.get('DEBUG', False)
                },
                'database': {
                    'host': os.getenv('DB_HOST', 'localhost'),
                    'port': os.getenv('DB_PORT', '5432'),
                    'name': os.getenv('DB_NAME', 'biometric_access_db')
                },
                'exported_at': datetime.now().isoformat(),
                'exported_by': current_user.username
            }
            
            return jsonify(config_data)
            
        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    @app.route('/configuration/reset', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def reset_configuration() -> Response:
        try:
            data = request.get_json()
            if not data or not data.get('confirm', False):
                return jsonify({
                    'success': False,
                    'needs_confirmation': True,
                    'message': 'Are you sure you want to reset all configuration to defaults? This action cannot be undone.'
                })
            
            logger.warning(f"Configuration reset to defaults by user: {current_user.username}")
            
            return jsonify({
                'success': True,
                'message': 'Configuration reset to defaults',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error resetting configuration: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
# =====================================================================
# DEVICES MANAGEMENT - FIXED with API Keys
# =====================================================================

    @app.route('/devices')
    @login_required
    @role_required('superadmin', 'admin')
    def devices() -> Any:
        """List all registered devices with API keys."""
        try:
            # Check if devices table exists, create if not
            execute_query("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    device_id VARCHAR(100) UNIQUE NOT NULL,
                    device_name VARCHAR(100) NOT NULL,
                    device_type VARCHAR(50) NOT NULL,
                    location VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'offline',
                    last_seen TIMESTAMP,
                    ip_address VARCHAR(45),
                    api_key VARCHAR(64) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            
            devices_result = execute_query("""
                SELECT id, device_id, device_name, device_type, location, status, 
                    last_seen, ip_address, api_key, created_at
                FROM devices
                ORDER BY created_at DESC
            """)
            
            devices_list = []
            if devices_result:
                for row in devices_result:
                    devices_list.append({
                        'id': row[0],
                        'device_id': row[1],
                        'device_name': row[2],
                        'device_type': row[3],
                        'location': row[4],
                        'status': row[5],
                        'last_seen': row[6],
                        'ip_address': row[7],
                        'api_key': row[8],
                        'created_at': row[9]
                    })
            
            return render_template('devices.html', devices=devices_list, user=current_user, now=datetime.now)
            
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
            flash(f'Error loading devices: {str(e)}', 'error')
            return render_template('devices.html', devices=[], user=current_user, now=datetime.now)

    @app.route('/devices/add', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin')
    def add_device() -> Any:
        """Add a new device with auto-generated API key."""
        if request.method == 'POST':
            device_name = request.form.get('device_name', '').strip()
            device_type = request.form.get('device_type', '').strip()
            device_id = request.form.get('device_id', '').strip()
            location = request.form.get('location', '').strip()
            ip_address = request.form.get('ip_address', '').strip()
            status = request.form.get('status', 'offline')
            api_key = request.form.get('api_key', '').strip()
            
            if not device_name or not device_type or not device_id:
                flash('Device name, type, and ID are required', 'error')
                return render_template('add_device.html', user=current_user, api_key=api_key or generate_api_key())
            
            if not api_key:
                api_key = generate_api_key()
            
            try:
                # Check if device_id already exists
                existing = execute_query(
                    "SELECT device_id FROM devices WHERE device_id = %s",
                    (device_id,)
                )
                if existing:
                    flash('Device ID already exists', 'error')
                    return render_template('add_device.html', user=current_user, api_key=api_key)
                
                # Check if api_key already exists
                existing_key = execute_query(
                    "SELECT api_key FROM devices WHERE api_key = %s",
                    (api_key,)
                )
                if existing_key:
                    flash('API key already exists. Please regenerate.', 'error')
                    return render_template('add_device.html', user=current_user, api_key=generate_api_key())
                
                execute_query("""
                    INSERT INTO devices 
                    (device_id, device_name, device_type, location, ip_address, status, api_key, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (device_id, device_name, device_type, location, ip_address, status, api_key))
                
                flash('Device registered successfully!', 'success')
                return redirect(url_for('devices'))
                
            except Exception as e:
                logger.error(f"Error adding device: {e}")
                flash(f'Error adding device: {str(e)}', 'error')
                return render_template('add_device.html', user=current_user, api_key=api_key)
        
        # GET request - generate new API key
        api_key = generate_api_key()
        return render_template('add_device.html', user=current_user, api_key=api_key)

    @app.route('/devices/edit/<string:device_id>', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def edit_device(device_id: str) -> Any:
        """Edit device information including API key management."""
        if request.method == 'POST':
            device_name = request.form.get('device_name', '').strip()
            device_type = request.form.get('device_type', '').strip()
            location = request.form.get('location', '').strip()
            ip_address = request.form.get('ip_address', '').strip()
            status = request.form.get('status', 'offline')
            
            if not device_name or not device_type:
                flash('Device name and type are required', 'error')
                return redirect(url_for('edit_device', device_id=device_id))
            
            try:
                execute_query("""
                    UPDATE devices 
                    SET device_name = %s, device_type = %s, location = %s, 
                        ip_address = %s, status = %s, updated_at = NOW()
                    WHERE device_id = %s
                """, (device_name, device_type, location, ip_address, status, device_id))
                
                flash('Device updated successfully!', 'success')
                return redirect(url_for('devices'))
                
            except Exception as e:
                logger.error(f"Error updating device: {e}")
                flash(f'Error updating device: {str(e)}', 'error')
                return redirect(url_for('edit_device', device_id=device_id))
        
        # GET request
        device_result = execute_query("""
            SELECT id, device_id, device_name, device_type, location, status, 
                ip_address, api_key, created_at, updated_at
            FROM devices WHERE device_id = %s
        """, (device_id,))
        
        if not device_result:
            flash('Device not found', 'error')
            return redirect(url_for('devices'))
        
        row = device_result[0]
        device = {
            'id': row[0],
            'device_id': row[1],
            'device_name': row[2],
            'device_type': row[3],
            'location': row[4],
            'status': row[5],
            'ip_address': row[6],
            'api_key': row[7],
            'created_at': row[8],
            'updated_at': row[9]
        }
        
        return render_template('edit_device.html', device=device, user=current_user)

    @app.route('/devices/regenerate-api/<string:device_id>', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def regenerate_device_api_key(device_id: str) -> Response:
        """Regenerate API key for a device."""
        try:
            new_api_key = generate_api_key()
            
            # Check if new key already exists
            existing = execute_query(
                "SELECT api_key FROM devices WHERE api_key = %s",
                (new_api_key,)
            )
            if existing:
                new_api_key = generate_api_key()  # Try once more
            
            execute_query("""
                UPDATE devices 
                SET api_key = %s, updated_at = NOW()
                WHERE device_id = %s
            """, (new_api_key, device_id))
            
            return jsonify({'success': True, 'api_key': new_api_key})
            
        except Exception as e:
            logger.error(f"Error regenerating API key: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/devices/delete/<string:device_id>', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def delete_device(device_id: str) -> Any:
        """Delete a device."""
        try:
            execute_query("DELETE FROM devices WHERE device_id = %s", (device_id,))
            flash('Device deleted successfully!', 'success')
        except Exception as e:
            logger.error(f"Error deleting device: {e}")
            flash(f'Error deleting device: {str(e)}', 'error')
        
        return redirect(url_for('devices'))

    @app.route('/devices/status/<string:device_id>/<string:status>', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def update_device_status(device_id: str, status: str) -> Response:
        """Update device status."""
        try:
            if status not in ['online', 'offline', 'maintenance', 'inactive']:
                return jsonify({'success': False, 'error': 'Invalid status'})
            
            execute_query("""
                UPDATE devices 
                SET status = %s, last_seen = NOW(), updated_at = NOW() 
                WHERE device_id = %s
            """, (status, device_id))
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route("/staff")
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def staff_area() -> Any:
        return render_template('staff_area.html', user=current_user)

    @app.route('/students/data')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def students_data() -> Response:
        """JSON endpoint for students table data (used by AJAX)."""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            search = request.args.get('search', '').strip()
            offset = (page - 1) * per_page
            
            if search:
                count_query = """
                    SELECT COUNT(*) FROM students 
                    WHERE is_active = TRUE 
                    AND (registration_number ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s)
                """
                search_param = f'%{search}%'
                count_params = (search_param, search_param, search_param)
                
                data_query = """
                    SELECT
                        student_id,
                        registration_number,
                        first_name,
                        last_name,
                        course,
                        year_of_study,
                        email,
                        phone,
                        created_at
                    FROM students
                    WHERE is_active = TRUE 
                    AND (registration_number ILIKE %s OR first_name ILIKE %s OR last_name ILIKE %s)
                    ORDER BY registration_number
                    LIMIT %s OFFSET %s
                """
                data_params = (search_param, search_param, search_param, per_page, offset)
            else:
                count_query = "SELECT COUNT(*) FROM students WHERE is_active = TRUE"
                count_params = None
                
                data_query = """
                    SELECT
                        student_id,
                        registration_number,
                        first_name,
                        last_name,
                        course,
                        year_of_study,
                        email,
                        phone,
                        created_at
                    FROM students
                    WHERE is_active = TRUE
                    ORDER BY registration_number
                    LIMIT %s OFFSET %s
                """
                data_params = (per_page, offset)
            
            if count_params:
                count_result = execute_query(count_query, count_params)
            else:
                count_result = execute_query(count_query)
            
            total_count = count_result[0][0] if count_result and count_result[0] else 0
            
            result = execute_query(data_query, data_params)
            
            students = []
            if result:
                for row in result:
                    students.append({
                        "id": row[0],
                        "student_id": row[0],
                        "registration_number": row[1],
                        "name": f"{row[2]} {row[3]}",
                        "first_name": row[2],
                        "last_name": row[3],
                        "course": row[4] if row[4] else 'N/A',
                        "year_of_study": row[5] if row[5] else 'N/A',
                        "email": row[6] if row[6] else 'N/A',
                        "phone": row[7] if row[7] else 'N/A',
                        "created_at": row[8].isoformat() if row[8] else None,
                        "status": "active"
                    })
            
            return jsonify({
                "success": True,
                "students": students,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": (total_count + per_page - 1) // per_page
                }
            })
            
        except Exception as e:
            logger.error(f"Error loading students data: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "students": [],
                "pagination": {
                    "current_page": page if 'page' in locals() else 1,
                    "per_page": per_page if 'per_page' in locals() else 10,
                    "total_count": 0,
                    "total_pages": 0
                }
            })
            
    @app.route("/students")
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def students() -> Any:
        search_query = request.args.get('q', '').strip()
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)  
        offset = (page - 1) * per_page
        
        base_query = """
            SELECT
                student_id,
                registration_number,
                first_name,
                last_name,
                email,
                phone,
                course,
                year_of_study,
                profile_image,
                created_at,
                updated_at
            FROM students
            WHERE is_active = TRUE
        """
        
        if search_query:
            search_condition = """ AND (
                LOWER(registration_number) LIKE LOWER('%{}%') OR
                LOWER(first_name) LIKE LOWER('%{}%') OR
                LOWER(last_name) LIKE LOWER('%{}%') OR
                LOWER(first_name || ' ' || last_name) LIKE LOWER('%{}%')
            )""".format(search_query, search_query, search_query, search_query)
            
            base_query += search_condition
            count_query = f"SELECT COUNT(*) FROM students WHERE is_active = TRUE {search_condition}"
        else:
            count_query = "SELECT COUNT(*) FROM students WHERE is_active = TRUE"
        
        count_result = execute_query(count_query)
        total_count = count_result[0][0] if count_result and count_result[0] else 0
        
        base_query += " ORDER BY registration_number LIMIT %s OFFSET %s"
        
        result = execute_query(base_query, (per_page, offset))

        student_list: List[Dict[str, Any]] = []
        if result:
            for row in result:
                student_list.append({
                    "student_id": row[0],
                    "registration_number": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "email": row[4],
                    "phone": row[5],
                    "course": row[6],
                    "year_of_study": row[7],
                    "profile_image": row[8],
                    "created_at": row[9],
                    "updated_at": row[10]
                })

        total_pages = (total_count + per_page - 1) // per_page

        return render_template(
            "students.html", 
            students=student_list, 
            user=current_user,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_count=total_count,
            search_query=search_query
        )
    
    @app.route('/students/add', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def add_student() -> Any:
        if request.method == 'POST':
            try:
                registration_number = request.form.get('registration_number', '').strip()
                first_name = request.form.get('first_name', '').strip()
                last_name = request.form.get('last_name', '').strip()
                email = request.form.get('email', '').strip()
                phone = request.form.get('phone', '').strip()
                course = request.form.get('course', '').strip()
                year_of_study = request.form.get('year_of_study', '').strip()
                
                if not registration_number or not first_name or not last_name:
                    flash('Registration number, first name, and last name are required', 'error')
                    return render_template('add_student.html', user=current_user)
                
                existing = execute_query(
                    "SELECT student_id FROM students WHERE registration_number = %s",
                    (registration_number,)
                )
                
                if existing:
                    flash('Student with this registration number already exists', 'error')
                    return render_template('add_student.html', user=current_user)
                
                # Handle profile image upload
                profile_image = None
                if 'profile_image' in request.files:
                    file = request.files['profile_image']
                    if file and file.filename:
                        # Validate file type
                        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                        
                        if file_ext in allowed_extensions:
                            # Validate file size (max 5MB)
                            file.seek(0, os.SEEK_END)
                            file_size = file.tell()
                            file.seek(0)
                            
                            if file_size <= 5 * 1024 * 1024:  # 5MB
                                # Create upload directory if it doesn't exist
                                static_folder = app.static_folder
                                if not static_folder:
                                    static_folder = os.path.join(app.root_path, 'static')
                                
                                upload_dir = os.path.join(static_folder, 'uploads', 'students')
                                os.makedirs(upload_dir, exist_ok=True)
                                
                                # Generate unique filename - SANITIZE registration number
                                from datetime import datetime
                                import uuid
                                import re
                                
                                # Remove invalid characters from registration number for filename
                                safe_reg_number = re.sub(r'[<>:"/\\|?*]', '_', registration_number)
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                unique_id = str(uuid.uuid4())[:8]
                                filename = f"student_{safe_reg_number}_{timestamp}_{unique_id}.{file_ext}"
                                
                                file_path = os.path.join(upload_dir, filename)
                                file.save(file_path)
                                profile_image = filename
                                
                                logger.info(f"Student profile image saved: {filename}")
                            else:
                                flash('Profile image too large. Maximum size is 5MB.', 'warning')
                        else:
                            flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'warning')
                
                # Insert into PostgreSQL
                result = execute_query("""
                    INSERT INTO students 
                    (registration_number, first_name, last_name, email, phone, 
                    course, year_of_study, profile_image, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING student_id
                """, (
                    registration_number, first_name, last_name,
                    email, phone, course, year_of_study, 
                    profile_image, True
                ))
                
                # Get the new student_id
                if result and len(result) > 0:
                    row = result[0]
                    new_student_id = row[0] if isinstance(row, (list, tuple)) else row.get('student_id')
                    
                    if new_student_id:
                        # AUTO-SYNC: Automatically sync to Firestore
                        student_data = {
                            'registration_number': registration_number,
                            'first_name': first_name,
                            'last_name': last_name,
                            'email': email,
                            'phone': phone,
                            'course': course,
                            'year_of_study': year_of_study,
                            'profile_image': profile_image,
                            'is_active': True
                        }
                        auto_sync.sync_student_after_save(new_student_id, student_data)
                        
                        flash(f'Student {first_name} {last_name} added successfully!', 'success')
                    else:
                        flash('Student added but auto-sync failed', 'warning')
                
                return redirect(url_for('students'))
                
            except Exception as e:
                logger.error(f"Error adding student: {e}")
                flash(f'Error adding student: {str(e)}', 'error')
                return render_template('add_student.html', user=current_user)
        
        return render_template('add_student.html', user=current_user)

    @app.route('/students/edit/<string:student_id>', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def edit_student(student_id: str) -> Any:
        if request.method == 'GET':
            student_result = execute_query("""
                SELECT registration_number, first_name, last_name, email, 
                    phone, course, year_of_study, profile_image
                FROM students WHERE student_id = %s
            """, (student_id,))
            
            if not student_result:
                flash('Student not found', 'error')
                return redirect(url_for('students'))
            
            student = {
                'student_id': student_id,
                'registration_number': student_result[0][0],
                'first_name': student_result[0][1],
                'last_name': student_result[0][2],
                'email': student_result[0][3],
                'phone': student_result[0][4],
                'course': student_result[0][5],
                'year_of_study': student_result[0][6],
                'profile_image': student_result[0][7] if len(student_result[0]) > 7 else None
            }
            
            return render_template('edit_student.html', student=student, user=current_user)
        
        elif request.method == 'POST':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            course = request.form.get('course', '').strip()
            year_of_study = request.form.get('year_of_study', '').strip()
            
            if not first_name or not last_name:
                flash('First name and last name are required', 'error')
                return redirect(url_for('edit_student', student_id=student_id))
            
            # Handle profile image upload
            profile_image = None
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    # Validate file type
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    
                    if file_ext in allowed_extensions:
                        # Validate file size (max 5MB)
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)
                        
                        if file_size <= 5 * 1024 * 1024:
                            # Create upload directory
                            static_folder = app.static_folder
                            if not static_folder:
                                static_folder = os.path.join(app.root_path, 'static')
                            
                            upload_dir = os.path.join(static_folder, 'uploads', 'students')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Get current registration number for filename
                            reg_result = execute_query(
                                "SELECT registration_number FROM students WHERE student_id = %s",
                                (student_id,)
                            )
                            reg_number = reg_result[0][0] if reg_result else student_id
                            
                            # Generate unique filename
                            from datetime import datetime
                            import uuid
                            
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            unique_id = str(uuid.uuid4())[:8]
                            filename = f"student_{reg_number}_{timestamp}_{unique_id}.{file_ext}"
                            
                            file_path = os.path.join(upload_dir, filename)
                            file.save(file_path)
                            profile_image = filename
                            
                            # Delete old profile image if exists
                            old_image_result = execute_query(
                                "SELECT profile_image FROM students WHERE student_id = %s",
                                (student_id,)
                            )
                            if old_image_result and old_image_result[0][0]:
                                old_image_path = os.path.join(upload_dir, old_image_result[0][0])
                                if os.path.exists(old_image_path):
                                    try:
                                        os.remove(old_image_path)
                                    except Exception as e:
                                        logger.warning(f"Could not delete old student image: {e}")
                        else:
                            flash('Profile image too large. Maximum size is 5MB.', 'warning')
                    else:
                        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'warning')
            
            try:
                # Update PostgreSQL
                if profile_image:
                    execute_query("""
                        UPDATE students 
                        SET first_name = %s, last_name = %s, email = %s, 
                            phone = %s, course = %s, year_of_study = %s,
                            profile_image = %s, updated_at = NOW()
                        WHERE student_id = %s
                    """, (first_name, last_name, email, phone, course, year_of_study, 
                        profile_image, student_id))
                else:
                    execute_query("""
                        UPDATE students 
                        SET first_name = %s, last_name = %s, email = %s, 
                            phone = %s, course = %s, year_of_study = %s,
                            updated_at = NOW()
                        WHERE student_id = %s
                    """, (first_name, last_name, email, phone, course, year_of_study, student_id))
                
                flash('Student updated successfully!', 'success')
                return redirect(url_for('students'))
                
            except Exception as e:
                logger.error(f"Error updating student: {e}")
                flash(f'Error updating student: {str(e)}', 'error')
                return redirect(url_for('edit_student', student_id=student_id))
                
    @app.route('/students/delete/<string:student_id>', methods=['POST', 'DELETE', "GET"])
    @login_required
    @role_required('superadmin', 'admin')
    def delete_student(student_id: str) -> Any:
        try:
            execute_query(
                "UPDATE students SET is_active = FALSE, updated_at = NOW() WHERE student_id = %s",
                (student_id,)
            )

            if request.method == 'DELETE' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Student deleted successfully'})
            flash('Student deleted successfully!', 'success')
        except Exception as e:
            logger.error(f"Error deleting student: {e}")
            if request.method == 'DELETE' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)})
            flash(f'Error deleting student: {str(e)}', 'error')
        
        return redirect(url_for('students'))
    
    @app.route('/students/<string:student_id>/biometric/add', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def add_biometric(student_id: str) -> Any:
        """Add biometric template for a student."""
        try:
            student_result = execute_query("""
                SELECT 
                    student_id,
                    registration_number,
                    first_name,
                    last_name,
                    course,
                    email
                FROM students 
                WHERE student_id = %s AND is_active = TRUE
            """, (student_id,))
            
            if not student_result:
                flash('Student not found', 'error')
                return redirect(url_for('students'))
            
            row = student_result[0]
            student = {
                'student_id': row[0],
                'registration_number': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'course': row[4],
                'email': row[5]
            }
            
            templates_result = execute_query("""
                SELECT template_type, quality_score, created_at
                FROM biometric_templates
                WHERE student_id = %s
                ORDER BY created_at DESC
            """, (student_id,))
            
            existing_templates = []
            if templates_result:
                for row in templates_result:
                    existing_templates.append({
                        'type': row[0],
                        'quality': row[1],
                        'enrolled_at': row[2]
                    })
            
            if request.method == 'POST':
                template_type = request.form.get('template_type', '').strip()
                quality_score = request.form.get('quality_score', 85, type=float)
                
                template_data = None
                if template_type == 'fingerprint':
                    fingerprint_data = request.form.get('fingerprint_data', '')
                    if fingerprint_data:
                        import base64
                        template_data = base64.b64decode(fingerprint_data)
                elif template_type == 'facial':
                    facial_data = request.form.get('facial_data', '')
                    if facial_data:
                        import base64
                        template_data = base64.b64decode(facial_data)
                
                if not template_data:
                    flash('No biometric data captured', 'error')
                    return render_template(
                        'add_biometric.html',
                        student=student,
                        existing_templates=existing_templates,
                        user=current_user
                    )
                
                from src.database.connection import DatabaseConnection
                db = DatabaseConnection()
                success = db.save_biometric_template(
                    student_id=student_id,
                    template_type=template_type,
                    template_data=template_data,
                    quality_score=quality_score
                )
                
                if success:
                    flash(f'{template_type.title()} template enrolled successfully!', 'success')
                    return redirect(url_for('view_student', student_id=student_id))
                else:
                    flash('Failed to save biometric template', 'error')
            
            return render_template(
                'add_biometric.html',
                student=student,
                existing_templates=existing_templates,
                user=current_user
            )
            
        except Exception as e:
            logger.error(f"Error adding biometric: {e}")
            flash(f'Error adding biometric: {str(e)}', 'error')
            return redirect(url_for('students'))
    
    @app.route('/students/<string:student_id>/biometric/<string:template_type>', methods=['DELETE', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def delete_biometric(student_id: str, template_type: str) -> Response:
        """Delete a biometric template."""
        try:
            execute_query("""
                DELETE FROM biometric_templates 
                WHERE student_id = %s AND template_type = %s
            """, (student_id, template_type))
            
            return jsonify({'success': True, 'message': f'{template_type} template deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting biometric template: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/students/view/<string:student_id>')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def view_student(student_id: str) -> Any:
        """View student details."""
        try:
            student_result = execute_query("""
                SELECT 
                    student_id,
                    registration_number,
                    first_name,
                    last_name,
                    email,
                    phone,
                    course,
                    year_of_study,
                    created_at,
                    updated_at,
                    is_active
                FROM students 
                WHERE student_id = %s
            """, (student_id,))
            
            if not student_result:
                flash('Student not found', 'error')
                return redirect(url_for('students'))
            
            row = student_result[0]
            student = {
                'student_id': row[0],
                'registration_number': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'email': row[4],
                'phone': row[5],
                'course': row[6],
                'year_of_study': row[7],
                'created_at': row[8],
                'updated_at': row[9],
                'is_active': row[10]
            }
            
            templates_result = execute_query("""
                SELECT template_type, quality_score, created_at
                FROM biometric_templates
                WHERE student_id = %s
                ORDER BY created_at DESC
            """, (student_id,))
            
            templates = []
            if templates_result:
                for row in templates_result:
                    templates.append({
                        'type': row[0],
                        'quality': row[1],
                        'enrolled_at': row[2]
                    })
            
            logs_result = execute_query("""
                SELECT 
                    timestamp,
                    access_point,
                    verification_method,
                    verification_result,
                    match_score
                FROM access_logs
                WHERE student_id = %s
                ORDER BY timestamp DESC
                LIMIT 20
            """, (student_id,))
            
            access_logs = []
            if logs_result:
                for row in logs_result:
                    access_logs.append({
                        'timestamp': row[0],
                        'access_point': row[1],
                        'method': row[2],
                        'result': row[3],
                        'score': row[4]
                    })
            
            return render_template(
                'view_student.html',
                student=student,
                templates=templates,
                access_logs=access_logs,
                user=current_user
            )
            
        except Exception as e:
            logger.error(f"Error viewing student: {e}")
            flash(f'Error viewing student: {str(e)}', 'error')
            return redirect(url_for('students'))
    
    # ---------------- USER MANAGEMENT ----------------
    @app.route('/users')
    @login_required
    def user_management():
        """User management page"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT admin_id, username, full_name, email, role, is_active, 
                created_at, last_login, profile_image, display_name
            FROM administrators 
            ORDER BY created_at DESC
        """)
        
        rows = cur.fetchall()
        users = []
        
        for row in rows:
            user_dict = {
                'admin_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'role': row[4],
                'is_active': row[5],
                'created_at': row[6],
                'last_login': row[7],
                'profile_image': row[8],
                'display_name': row[9] or row[2]
            }
            
            users.append(user_dict)
        
        cur.close()
        conn.close()
        
        return render_template('users.html', users=users, current_user=current_user)
    
    @app.route('/users/create', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def create_user() -> Response:
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "No data provided"})
            
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            full_name = data.get('full_name', '').strip()
            email = data.get('email', '').strip()
            role = data.get('role', 'staff').strip()
            
            if not username or not password:
                return jsonify({"success": False, "error": "Username and password are required"})
            
            existing = execute_query(
                "SELECT admin_id FROM administrators WHERE username = %s",
                (username,)
            )
            
            if existing:
                return jsonify({"success": False, "error": "Username already exists"})
            
            password_hash = hash_password(password)
            
            execute_query(
                """
                INSERT INTO administrators 
                (username, password_hash, full_name, email, role, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                """,
                (username, password_hash, full_name, email, role)
            )
            
            return jsonify({"success": True, "message": "User created successfully"})
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    @app.route('/users/update/<int:user_id>', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def update_user(user_id: int) -> Response:
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "No data provided"})
            
            username = data.get('username')
            full_name = data.get('full_name')
            email = data.get('email')
            role = data.get('role')
            is_active = data.get('is_active')
            
            updates = []
            params = []
            
            if username is not None:
                updates.append("username = %s")
                params.append(username)
            
            if full_name is not None:
                updates.append("full_name = %s")
                params.append(full_name)
            
            if email is not None:
                updates.append("email = %s")
                params.append(email)
            
            if role is not None:
                updates.append("role = %s")
                params.append(role)
            
            if is_active is not None:
                updates.append("is_active = %s")
                params.append(is_active)
            
            if not updates:
                return jsonify({"success": False, "error": "No fields to update"})
            
            params.append(user_id)
            updates.append("updated_at = NOW()")
            
            query = f"""
                UPDATE administrators 
                SET {', '.join(updates)}
                WHERE admin_id = %s
            """
            
            execute_query(query, tuple(params))
            
            return jsonify({"success": True, "message": "User updated successfully"})
            
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return jsonify({"success": False, "error": str(e)})
        
    @app.route('/users/add', methods=['GET', 'POST'])
    @login_required
    def add_user():
        """Add a new user page"""
        if current_user.role not in ['admin', 'superadmin']:
            flash('You do not have permission to add users', 'danger')
            return redirect(url_for('user_management'))
        
        if request.method == 'POST':
            try:
                username = request.form.get('username')
                full_name = request.form.get('full_name')
                email = request.form.get('email')
                password = request.form.get('password')
                role = request.form.get('role')
                phone = request.form.get('phone')
                department = request.form.get('department')
                is_active = 'is_active' in request.form
                
                if not all([username, full_name, password, role]):
                    flash('Please fill all required fields', 'danger')
                    return redirect(url_for('add_user'))
                
                conn = get_db_connection()
                cur = conn.cursor()
                
                cur.execute("SELECT admin_id FROM administrators WHERE username = %s", (username,))
                if cur.fetchone():
                    flash('Username already exists', 'danger')
                    cur.close()
                    conn.close()
                    return redirect(url_for('add_user'))
                
                from werkzeug.security import generate_password_hash
                password = request.form.get('password', '').strip()

                if not password:
                    flash('Password is required', 'danger')
                    return redirect(url_for('add_user'))

                password_hash = generate_password_hash(password)
                
                profile_image = None
                if 'profile_image' in request.files:
                    file = request.files['profile_image']
                    if file and file.filename:
                        import os
                        from datetime import datetime
                        import uuid
                        
                        upload_dir = os.path.join(app.root_path, 'static', 'uploads')
                        os.makedirs(upload_dir, exist_ok=True)
                        
                        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        unique_id = str(uuid.uuid4())[:8]
                        filename = f"{timestamp}_{unique_id}.{ext}"
                        
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        profile_image = filename
                
                cur.execute("""
                    INSERT INTO administrators (
                        username, full_name, email, password_hash, role, 
                        phone, department, is_active, profile_image, display_name,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    RETURNING admin_id
                """, (username, full_name, email, password_hash, role, phone, department, 
                    is_active, profile_image, full_name))
                
                new_user_id = cur.fetchone()[0]
                conn.commit()
                
                cur.close()
                conn.close()
                
                flash(f'User "{username}" created successfully!', 'success')
                return redirect(url_for('view_user', user_id=new_user_id))
                
            except Exception as e:
                print(f"Error creating user: {e}")
                flash('Error creating user. Please try again.', 'danger')
                return redirect(url_for('add_user'))
        
        return render_template('add_user.html')
    
    @app.route('/users/reset_password/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def reset_password(user_id: int):
        if request.method == 'GET':
            return render_template('reset_password.html', user_id=user_id)
        
        try:
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            if not new_password or new_password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('reset_password', user_id=user_id))
            
            password_hash = hash_password(new_password)
            
            execute_query(
                "UPDATE administrators SET password_hash = %s, updated_at = NOW() WHERE admin_id = %s",
                (password_hash, user_id)
            )
            
            flash('Password reset successfully!', 'success')
            return redirect(url_for('view_user', user_id=user_id))
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            flash(f'Error resetting password: {str(e)}', 'danger')
            return redirect(url_for('reset_password', user_id=user_id))
    
    @app.route('/users/data')
    @login_required
    @role_required('superadmin', 'admin')
    def users_data() -> Response:
        """JSON endpoint for users table data."""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            search = request.args.get('search', '').strip()
            offset = (page - 1) * per_page
            
            if search:
                count_query = """
                    SELECT COUNT(*) FROM administrators 
                    WHERE is_active = TRUE 
                    AND (username ILIKE %s OR full_name ILIKE %s OR email ILIKE %s)
                """
                search_param = f'%{search}%'
                count_params = (search_param, search_param, search_param)
                
                data_query = """
                    SELECT 
                        admin_id, 
                        username, 
                        full_name, 
                        email, 
                        role, 
                        is_active,
                        created_at,
                        last_login
                    FROM administrators 
                    WHERE is_active = TRUE 
                    AND (username ILIKE %s OR full_name ILIKE %s OR email ILIKE %s)
                    ORDER BY username
                    LIMIT %s OFFSET %s
                """
                data_params = (search_param, search_param, search_param, per_page, offset)
            else:
                count_query = "SELECT COUNT(*) FROM administrators WHERE is_active = TRUE"
                count_params = None
                
                data_query = """
                    SELECT 
                        admin_id, 
                        username, 
                        full_name, 
                        email, 
                        role, 
                        is_active,
                        created_at,
                        last_login
                    FROM administrators 
                    WHERE is_active = TRUE
                    ORDER BY username
                    LIMIT %s OFFSET %s
                """
                data_params = (per_page, offset)
            
            if count_params:
                count_result = execute_query(count_query, count_params)
            else:
                count_result = execute_query(count_query)
            
            total_count = count_result[0][0] if count_result and count_result[0] else 0
            
            result = execute_query(data_query, data_params)
            
            users = []
            if result:
                for row in result:
                    users.append({
                        "id": row[0],
                        "admin_id": row[0],
                        "username": row[1],
                        "full_name": row[2] or row[1],
                        "email": row[3] or 'N/A',
                        "role": row[4] or 'staff',
                        "is_active": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "last_login": row[7].isoformat() if row[7] else None,
                        "status": "active" if row[5] else "inactive"
                    })
            
            return jsonify({
                "success": True,
                "users": users,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": (total_count + per_page - 1) // per_page
                }
            })
            
        except Exception as e:
            logger.error(f"Error loading users data: {e}")
            return jsonify({
                "success": False,
                "error": str(e),
                "users": [],
                "pagination": {
                    "current_page": page if 'page' in locals() else 1,
                    "per_page": per_page if 'per_page' in locals() else 10,
                    "total_count": 0,
                    "total_pages": 0
                }
            })
    
    @app.route('/users/view/<int:user_id>')
    @login_required
    @role_required('superadmin', 'admin')
    def view_user(user_id: int) -> Any:
        """View user details."""
        try:
            user_result = execute_query("""
                SELECT 
                    admin_id,
                    username,
                    full_name,
                    email,
                    role,
                    is_active,
                    created_at,
                    last_login,
                    updated_at
                FROM administrators 
                WHERE admin_id = %s
            """, (user_id,))
            
            if not user_result:
                flash('User not found', 'error')
                return redirect(url_for('user_management'))
            
            row = user_result[0]
            user = {
                'id': row[0],
                'admin_id': row[0],
                'username': row[1],
                'full_name': row[2] or row[1],
                'email': row[3],
                'role': row[4],
                'is_active': row[5],
                'created_at': row[6],
                'last_login': row[7],
                'updated_at': row[8]
            }
            
            logs_result = execute_query("""
                SELECT 
                    timestamp,
                    action,
                    details,
                    ip_address
                FROM audit_logs
                WHERE user_id = %s::varchar
                ORDER BY timestamp DESC
                LIMIT 20
            """, (str(user_id),))
            
            activity_logs = []
            if logs_result:
                for row in logs_result:
                    activity_logs.append({
                        'timestamp': row[0],
                        'action': row[1],
                        'details': row[2],
                        'ip_address': row[3]
                    })
            
            return render_template(
                'view_user.html',
                user=user,
                activity_logs=activity_logs,
                current_user=current_user
            )
            
        except Exception as e:
            logger.error(f"Error viewing user: {e}")
            flash(f'Error viewing user: {str(e)}', 'error')
            return redirect(url_for('user_management'))
    
    @app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    def edit_user(user_id):
        """Edit user page"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT admin_id, username, full_name, email, role, is_active, 
                created_at, last_login, profile_image, display_name
            FROM administrators 
            WHERE admin_id = %s
        """, (user_id,))
        
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            flash('User not found!', 'danger')
            return redirect(url_for('user_management'))
        
        user = {
            'admin_id': row[0],
            'username': row[1],
            'full_name': row[2],
            'email': row[3],
            'role': row[4],
            'is_active': row[5],
            'created_at': row[6],
            'last_login': row[7],
            'profile_image': row[8],
            'display_name': row[9] or row[2]
        }
        
        if request.method == 'POST':
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            role = request.form.get('role')
            is_active = 'is_active' in request.form
            
            cur.execute("""
                UPDATE administrators 
                SET full_name = %s,
                    email = %s,
                    role = %s,
                    is_active = %s,
                    display_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE admin_id = %s
            """, (full_name, email, role, is_active, full_name, user_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('User updated successfully!', 'success')
            return redirect(url_for('view_user', user_id=user_id))
        
        cur.close()
        conn.close()
        
        return render_template('edit_user.html', user=user)
    
    @app.route('/users/delete/<int:user_id>', methods=['GET', 'POST', 'DELETE'])
    @login_required
    @role_required('superadmin')
    def delete_user(user_id: int) -> Any:
        """Delete/deactivate a user."""
        try:
            if current_user.id == str(user_id):
                if request.method == 'DELETE' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'You cannot delete your own account'})
                flash('You cannot delete your own account', 'error')
                return redirect(url_for('user_management'))
            
            execute_query(
                "UPDATE administrators SET is_active = FALSE, updated_at = NOW() WHERE admin_id = %s",
                (user_id,)
            )
            
            execute_query("""
                INSERT INTO audit_logs (user_id, action, details, ip_address, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
            """, (current_user.id, 'USER_DELETE', f'Deactivated user {user_id}', request.remote_addr))
            
            if request.method == 'DELETE' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'User deactivated successfully'})
            
            flash('User deactivated successfully!', 'success')
            
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            if request.method == 'DELETE' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)})
            flash(f'Error deleting user: {str(e)}', 'error')
        
        return redirect(url_for('user_management'))
    
    @app.route('/users/activate/<int:user_id>', methods=['POST'])
    @login_required
    @role_required('superadmin')
    def activate_user(user_id: int) -> Response:
        """Reactivate a deactivated user."""
        try:
            execute_query(
                "UPDATE administrators SET is_active = TRUE, updated_at = NOW() WHERE admin_id = %s",
                (user_id,)
            )
            
            execute_query("""
                INSERT INTO audit_logs (user_id, action, details, ip_address, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
            """, (current_user.id, 'USER_ACTIVATE', f'Activated user {user_id}', request.remote_addr))
            
            return jsonify({'success': True, 'message': 'User activated successfully'})
            
        except Exception as e:
            logger.error(f"Error activating user: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/favicon.ico')
    def favicon() -> Response:
        return Response('', status=204)
    
    @app.route('/reports/student/<string:student_id>')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def student_report(student_id: str) -> Any:
        logs_result = execute_query("""
            SELECT
                al.timestamp,
                al.verification_method,
                al.verification_result,
                al.match_score,
                al.access_point
            FROM access_logs al
            WHERE al.student_id = %s
            ORDER BY al.timestamp DESC
            LIMIT 100
        """, (student_id,))

        student_result = execute_query("""
            SELECT registration_number, first_name, last_name
            FROM students WHERE student_id = %s
        """, (student_id,))

        student = student_result[0] if student_result and student_result[0] else None
        logs = logs_result if logs_result else []

        return render_template(
            "student_report.html",
            student=student,
            logs=logs,
            user=current_user
        )

    @app.route('/reports')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def reports() -> Any:
        return render_template('reports.html', user=current_user)
    
    @app.route('/reports/generate', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def generate_report() -> Response:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})
        
        report_type = data.get('type', '').strip()
        date_from = data.get('date_from', '').strip()
        date_to = data.get('date_to', '').strip()
        access_point = data.get('access_point', '').strip()

        if not report_type or not date_from or not date_to:
            return jsonify({"success": False, "error": "Missing required parameters"})

        query = ""
        params: List[Any] = [date_from, date_to]
        
        if report_type == 'daily':
            query = """
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM access_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
                ORDER BY date
            """
        elif report_type == 'hourly':
            query = """
                SELECT EXTRACT(HOUR FROM timestamp) AS hour, COUNT(*) AS count
                FROM access_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY EXTRACT(HOUR FROM timestamp)
                ORDER BY hour
            """
        elif report_type == 'student':
            query = """
                SELECT s.student_id, s.first_name, s.last_name, COUNT(al.student_id) as count
                FROM students s
                LEFT JOIN access_logs al ON s.student_id = al.student_id
                WHERE al.timestamp BETWEEN %s AND %s
                GROUP BY s.student_id, s.first_name, s.last_name
                ORDER BY count DESC
            """
        else:
            return jsonify({"success": False, "error": "Invalid report type"})

        if access_point:
            query = query.replace("WHERE", "WHERE access_point = %s AND")
            params.insert(0, access_point)

        result = execute_query(query, tuple(params))
        
        return jsonify({
            "success": True,
            "report_type": report_type,
            "data": result if result else [],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @app.route('/reports/export/<string:format_type>')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def export_report(format_type: str) -> Any:
        report_type = request.args.get('type', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        access_point = request.args.get('access_point', '').strip()

        if not report_type or not date_from or not date_to:
            return jsonify({"success": False, "error": "Missing required parameters"})

        query = ""
        params: List[Any] = [date_from, date_to]
        
        if report_type == 'daily':
            query = """
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM access_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
                ORDER BY date
            """
        elif report_type == 'hourly':
            query = """
                SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
                FROM access_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY EXTRACT(HOUR FROM timestamp)
                ORDER BY hour
            """
        elif report_type == 'student':
            query = """
                SELECT s.student_id, s.first_name, s.last_name, COUNT(al.student_id) as count
                FROM students s
                LEFT JOIN access_logs al ON s.student_id = al.student_id
                WHERE al.timestamp BETWEEN %s AND %s
                GROUP BY s.student_id, s.first_name, s.last_name
                ORDER BY count DESC
            """
        else:
            return jsonify({"success": False, "error": "Invalid report type"})

        if access_point:
            query = query.replace("WHERE", "WHERE access_point = %s AND")
            params.insert(0, access_point)

        result = execute_query(query, tuple(params))
        
        if format_type == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            
            if report_type == 'daily':
                writer.writerow(['Date', 'Count'])
                if result:
                    for row in result:
                        writer.writerow(row)
            elif report_type == 'hourly':
                writer.writerow(['Hour', 'Count'])
                if result:
                    for row in result:
                        writer.writerow(row)
            elif report_type == 'student':
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Count'])
                if result:
                    for row in result:
                        writer.writerow(row)

            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    "Content-Disposition": f"attachment; filename={report_type}_report.csv"
                }
            )
        
        return jsonify({"success": False, "error": f"Export format '{format_type}' not supported"})
    
    @app.route('/reports/generate/csv')
    @login_required
    @admin_required
    def generate_report_csv() -> Response:
        where_clause, where_params = build_date_filter(request.args)
        
        query = f"""
            SELECT
                al.timestamp,
                s.registration_number,
                s.first_name,
                s.last_name,
                al.verification_method,
                al.verification_result,
                al.match_score,
                al.access_point
            FROM access_logs al
            LEFT JOIN students s ON al.student_id = s.student_id
            WHERE {where_clause}
            ORDER BY al.timestamp DESC
            LIMIT 1000
        """
        
        result = execute_query(query, tuple(where_params) if where_params else None)

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Timestamp",
            "Registration No",
            "First Name",
            "Last Name",
            "Method",
            "Result",
            "Score",
            "Access Point"
        ])

        if result:
            for row in result:
                writer.writerow(row)

        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=access_report.csv"
            }
        )

    @app.route('/reports/generate/pdf')
    @login_required
    @admin_required
    def generate_report_pdf() -> Response:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        where_clause, where_params = build_date_filter(request.args)
        
        query = f"""
            SELECT
                al.timestamp,
                s.registration_number,
                al.verification_result,
                al.access_point
            FROM access_logs al
            LEFT JOIN students s ON al.student_id = s.student_id
            WHERE {where_clause}
            ORDER BY al.timestamp DESC
            LIMIT 40
        """
        
        result = execute_query(query, tuple(where_params) if where_params else None)

        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, height - 50, "Biometric Access Report")

        pdf.setFont("Helvetica", 10)
        y = height - 90

        if result:
            for row in result:
                if y < 50:
                    pdf.showPage()
                    y = height - 50

                line = f"{row[0]} | {row[1] or 'N/A'} | {row[2]} | {row[3]}"
                pdf.drawString(50, y, line)
                y -= 15

        pdf.save()
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=access_report.pdf"
            }
        )
    
    @app.route('/reports/daily-data')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def reports_daily_data():
        """Get real daily access data for charts"""
        try:
            days = request.args.get('days', 7, type=int)
            
            result = execute_query("""
                WITH dates AS (
                    SELECT generate_series(
                        CURRENT_DATE - (%s || ' days')::interval,
                        CURRENT_DATE,
                        '1 day'::interval
                    )::date as date
                )
                SELECT 
                    d.date,
                    COALESCE(COUNT(al.log_id), 0) as total,
                    COALESCE(SUM(CASE WHEN al.verification_result = 'GRANTED' THEN 1 ELSE 0 END), 0) as granted,
                    COALESCE(SUM(CASE WHEN al.verification_result = 'DENIED' THEN 1 ELSE 0 END), 0) as denied
                FROM dates d
                LEFT JOIN access_logs al ON DATE(al.timestamp) = d.date
                GROUP BY d.date
                ORDER BY d.date
            """, (days,))
            
            labels = []
            total_data = []
            granted_data = []
            denied_data = []
            
            if result:
                for row in result:
                    labels.append(row[0].strftime('%Y-%m-%d'))
                    total_data.append(row[1] or 0)
                    granted_data.append(row[2] or 0)
                    denied_data.append(row[3] or 0)
            
            return jsonify({
                'success': True,
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Total Accesses',
                        'data': total_data,
                        'borderColor': '#0d6efd',
                        'backgroundColor': 'rgba(13,110,253,0.1)',
                        'tension': 0.1
                    },
                    {
                        'label': 'Granted',
                        'data': granted_data,
                        'borderColor': '#198754',
                        'backgroundColor': 'rgba(25,135,84,0.1)',
                        'tension': 0.1
                    },
                    {
                        'label': 'Denied',
                        'data': denied_data,
                        'borderColor': '#dc3545',
                        'backgroundColor': 'rgba(220,53,69,0.1)',
                        'tension': 0.1
                    }
                ]
            })
            
        except Exception as e:
            logger.error(f"Error getting daily data: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/reports/hourly-data')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def reports_hourly_data() -> Response:
        """Get hourly access data for charts."""
        try:
            date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            result = execute_query("""
                SELECT 
                    EXTRACT(HOUR FROM timestamp) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN verification_result = 'GRANTED' THEN 1 ELSE 0 END) as granted,
                    SUM(CASE WHEN verification_result = 'DENIED' THEN 1 ELSE 0 END) as denied
                FROM access_logs
                WHERE DATE(timestamp) = %s
                GROUP BY EXTRACT(HOUR FROM timestamp)
                ORDER BY hour
            """, (date,))
            
            labels = []
            total_data = []
            granted_data = []
            denied_data = []
            
            for hour in range(24):
                labels.append(f'{hour:02d}:00')
                total_data.append(0)
                granted_data.append(0)
                denied_data.append(0)
            
            if result:
                for row in result:
                    hour = int(row[0])
                    labels[hour] = f'{hour:02d}:00'
                    total_data[hour] = row[1] or 0
                    granted_data[hour] = row[2] or 0
                    denied_data[hour] = row[3] or 0
            
            return jsonify({
                'success': True,
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Total Accesses',
                        'data': total_data,
                        'backgroundColor': '#0d6efd'
                    },
                    {
                        'label': 'Granted',
                        'data': granted_data,
                        'backgroundColor': '#198754'
                    },
                    {
                        'label': 'Denied',
                        'data': denied_data,
                        'backgroundColor': '#dc3545'
                    }
                ]
            })
            
        except Exception as e:
            logger.error(f"Error getting hourly data: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/reports/top-access-points')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def reports_top_access_points() -> Response:
        """Get top access points data for charts."""
        try:
            limit = request.args.get('limit', 5, type=int)
            
            result = execute_query("""
                SELECT 
                    access_point,
                    COUNT(*) as count
                FROM access_logs
                WHERE access_point IS NOT NULL
                GROUP BY access_point
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            
            labels = []
            data = []
            
            if result:
                for row in result:
                    labels.append(row[0] or 'Unknown')
                    data.append(row[1])
            
            return jsonify({
                'success': True,
                'labels': labels,
                'data': data
            })
            
        except Exception as e:
            logger.error(f"Error getting top access points: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/reports/student-stats')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def reports_student_stats() -> Response:
        """Get student statistics for charts."""
        try:
            course_result = execute_query("""
                SELECT 
                    COALESCE(course, 'Not Specified') as course,
                    COUNT(*) as count
                FROM students
                WHERE is_active = TRUE
                GROUP BY course
                ORDER BY count DESC
                LIMIT 10
            """)
            
            course_labels = []
            course_data = []
            
            if course_result:
                for row in course_result:
                    course_labels.append(row[0])
                    course_data.append(row[1])
            
            year_result = execute_query("""
                SELECT 
                    COALESCE(year_of_study::text, 'N/A') as year,
                    COUNT(*) as count
                FROM students
                WHERE is_active = TRUE
                GROUP BY year_of_study
                ORDER BY year
            """)
            
            year_labels = []
            year_data = []
            
            if year_result:
                for row in year_result:
                    year_labels.append(f'Year {row[0]}' if row[0] != 'N/A' else 'Not Specified')
                    year_data.append(row[1])
            
            return jsonify({
                'success': True,
                'courses': {
                    'labels': course_labels,
                    'data': course_data
                },
                'years': {
                    'labels': year_labels,
                    'data': year_data
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting student stats: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/logs')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def logs() -> Any:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('json'):
            limit = request.args.get('limit', 10, type=int)
            
            result = execute_query("""
                SELECT
                    al.timestamp,
                    al.verification_method,
                    al.verification_result,
                    al.access_point,
                    s.registration_number,
                    s.first_name,
                    s.last_name
                FROM access_logs al
                LEFT JOIN students s ON al.student_id = s.student_id
                ORDER BY al.timestamp DESC
                LIMIT %s
            """, (limit,))
            
            log_list = []
            if result:
                for row in result:
                    log_list.append({
                        "timestamp": row[0].isoformat() if row[0] else "",
                        "method": row[1],
                        "result": row[2],
                        "access_point": row[3],
                        "student": f"{row[5]} {row[6]}" if row[5] else "Unknown"
                    })
            
            return jsonify({"logs": log_list})
        
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        result = execute_query("""
            SELECT
                al.timestamp,
                al.verification_method,
                al.verification_result,
                al.match_score,
                al.access_point,
                s.registration_number,
                s.first_name,
                s.last_name
            FROM access_logs al
            LEFT JOIN students s ON al.student_id = s.student_id
            ORDER BY al.timestamp DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        total_result = execute_query("SELECT COUNT(*) FROM access_logs")
        total = total_result[0][0] if total_result and total_result[0] else 0

        log_list: List[Dict[str, Any]] = []
        if result:
            for row in result:
                log_list.append({
                    "timestamp": row[0],
                    "method": row[1],
                    "result": row[2],
                    "score": row[3] if row[3] else 0,
                    "access_point": row[4],
                    "student": f"{row[6]} {row[7]}" if row[6] else "Unknown"
                })

        return render_template(
            'logs.html',
            logs=log_list,
            page=page,
            total_pages=(total + per_page - 1) // per_page,
            user=current_user
        )
    
    @app.route('/audit-logs')
    @login_required
    @role_required('superadmin', 'admin', 'staff')
    def audit_logs() -> Any:
        try:
            page = int(request.args.get('page', 1))
            per_page = 20
            offset = (page - 1) * per_page

            result = execute_query("""
                SELECT
                    al.timestamp,
                    al.verification_method,
                    al.verification_result,
                    al.match_score,
                    al.access_point,
                    s.registration_number,
                    s.first_name,
                    s.last_name,
                    al.details
                FROM access_logs al
                LEFT JOIN students s ON al.student_id = s.student_id
                ORDER BY al.timestamp DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))

            total_result = execute_query("SELECT COUNT(*) FROM access_logs")
            total = total_result[0][0] if total_result and total_result[0] else 0

            log_list = []
            if result:
                for row in result:
                    log_list.append({
                        "timestamp": row[0],
                        "method": row[1],
                        "result": row[2],
                        "score": row[3] if row[3] else 0,
                        "access_point": row[4],
                        "registration_number": row[5],
                        "student": f"{row[6]} {row[7]}" if row[6] else "Unknown",
                        "details": row[8] if row[8] else "N/A"
                    })

            return render_template(
                'audit_logs.html',
                logs=log_list,
                page=page,
                total_pages=(total + per_page - 1) // per_page,
                user=current_user
            )
            
        except Exception as e:
            logger.error(f"Error loading audit logs: {e}")
            return render_template(
                'audit_logs.html',
                logs=[],
                page=1,
                total_pages=0,
                user=current_user,
                error=str(e)
            )
        
    @app.route('/clear-old-logs', methods=['POST'])
    @login_required
    @role_required('superadmin', 'admin')
    def clear_old_logs() -> Response:
        try:
            settings_result = execute_query(
                "SELECT setting_value FROM system_settings WHERE setting_name = 'log_retention_days'"
            )
            retention_days = settings_result[0][0] if settings_result and settings_result[0] else 30
            
            execute_query(
                "DELETE FROM access_logs WHERE timestamp < CURRENT_DATE - INTERVAL '%s days'",
                (retention_days,)
            )
            
            return jsonify({'success': True, 'message': f'Cleared logs older than {retention_days} days'})
            
        except Exception as e:
            logger.error(f"Error clearing old logs: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/profile')
    @login_required
    def profile():
        """User profile page"""
        # Fetch complete user data from database
        user_data = execute_query("""
            SELECT admin_id, username, full_name, email, role, profile_image, 
                created_at, last_login, phone, department, display_name
            FROM administrators 
            WHERE admin_id = %s
        """, (current_user.id,))
        
        if user_data and user_data[0]:
            row = user_data[0]
            user = {
                'id': row[0],
                'admin_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'role': row[4],
                'profile_image': row[5],
                'created_at': row[6],
                'last_login': row[7],
                'phone': row[8],
                'department': row[9],
                'display_name': row[10] or row[2]
            }
        else:
            # Fallback to current_user
            user = {
                'id': current_user.id,
                'admin_id': current_user.id,
                'username': current_user.username,
                'full_name': current_user.full_name,
                'email': getattr(current_user, 'email', ''),
                'role': current_user.role,
                'profile_image': getattr(current_user, 'profile_image', ''),
                'created_at': None,
                'last_login': None,
                'phone': getattr(current_user, 'phone', ''),
                'department': getattr(current_user, 'department', ''),
                'display_name': current_user.display_name
            }
        
        # Get biometric enrollment status (if needed)
        biometric_enrolled = False
        enrollment_date = None
        
        return render_template('profile.html', 
                            user=user, 
                            current_user=current_user,
                            biometric_enrolled=biometric_enrolled,
                            enrollment_date=enrollment_date,
                            last_login=user.get('last_login'),
                            last_access=None)

    @app.route('/update-profile', methods=['POST'])
    @login_required
    def update_profile():
        """Update user profile including profile image"""
        try:
            # Get form data
            display_name = request.form.get('display_name', '').strip()
            email = request.form.get('email', '').strip()
            
            # Update basic info in database
            if display_name:
                execute_query("""
                    UPDATE administrators 
                    SET display_name = %s, 
                        email = %s,
                        updated_at = NOW()
                    WHERE admin_id = %s
                """, (display_name, email, current_user.id))
            
            # Handle profile image upload
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    # Validate file type
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    
                    if file_ext not in allowed_extensions:
                        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'danger')
                        return redirect(url_for('profile'))
                    
                    # Validate file size (max 5MB)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > 5 * 1024 * 1024:  # 5MB
                        flash('File too large. Maximum size is 5MB.', 'danger')
                        return redirect(url_for('profile'))
                    
                    # Create upload directory if it doesn't exist
                    static_folder = app.static_folder
                    if not static_folder:
                        static_folder = os.path.join(app.root_path, 'static')
                    
                    upload_dir = os.path.join(static_folder, 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Generate unique filename
                    from datetime import datetime
                    import uuid
                    
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_id = str(uuid.uuid4())[:8]
                    filename = f"profile_{current_user.id}_{timestamp}_{unique_id}.{file_ext}"
                    
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)
                    
                    # Delete old profile image if exists
                    old_image = execute_query(
                        "SELECT profile_image FROM administrators WHERE admin_id = %s",
                        (current_user.id,)
                    )
                    if old_image and old_image[0][0]:
                        old_image_path = os.path.join(upload_dir, old_image[0][0])
                        if os.path.exists(old_image_path) and old_image[0][0] != filename:
                            try:
                                os.remove(old_image_path)
                            except Exception as e:
                                logger.warning(f"Could not delete old profile image: {e}")
                    
                    # Update database with new image filename
                    execute_query("""
                        UPDATE administrators 
                        SET profile_image = %s, updated_at = NOW()
                        WHERE admin_id = %s
                    """, (filename, current_user.id))
                    
                    flash('Profile image updated successfully!', 'success')
                else:
                    flash('Profile updated successfully!', 'success')
            else:
                flash('Profile updated successfully!', 'success')
            
            return redirect(url_for('profile'))
            
        except Exception as e:
            logger.error(f"Error updating profile: {e}")
            flash(f'Error updating profile: {str(e)}', 'danger')
            return redirect(url_for('profile'))    
    
    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        """Change user password"""
        if request.method == 'POST':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not new_password:
                flash('New password is required!', 'danger')
                return redirect(url_for('change_password'))
            
            if new_password != confirm_password:
                flash('New passwords do not match!', 'danger')
                return redirect(url_for('change_password'))
            
            if not current_user.verify_password(current_password):
                flash('Current password is incorrect!', 'danger')
                return redirect(url_for('change_password'))
            
            new_password_hash = hash_password(new_password)
            
            try:
                execute_query(
                    "UPDATE administrators SET password_hash = %s, updated_at = NOW() WHERE admin_id = %s",
                    (new_password_hash, current_user.id)
                )
                
                flash('Your password has been updated successfully!', 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                logger.error(f"Error updating password: {e}")
                flash('An error occurred while updating your password. Please try again.', 'danger')
                return redirect(url_for('change_password'))
        
        return render_template('change_password.html')

    @app.route('/debug-profile-image')
    @login_required
    def debug_profile_image():
        """Debug endpoint to check profile image"""
        import os
        from pathlib import Path
        
        result = {
            'admin_id': current_user.admin_id,
            'full_name': current_user.full_name,
            'profile_image_db': current_user.profile_image,
            'static_folder': app.static_folder,
            'upload_dir': None,
            'upload_dir_exists': False,
            'file_exists': False,
            'file_path': None,
            'url_for_path': None,
            'direct_path': None,
            'files_in_upload_dir': []
        }
        
        if app.static_folder:
            upload_dir = Path(app.static_folder) / 'uploads'
            result['upload_dir'] = str(upload_dir)
            result['upload_dir_exists'] = upload_dir.exists()
            
            if upload_dir.exists():
                result['files_in_upload_dir'] = [f.name for f in upload_dir.glob('*')]
                
                if current_user.profile_image:
                    file_path = upload_dir / current_user.profile_image
                    result['file_exists'] = file_path.exists()
                    result['file_path'] = str(file_path)
            
            if current_user.profile_image:
                result['url_for_path'] = url_for('static', filename=f'uploads/{current_user.profile_image}')
                result['direct_path'] = f'/static/uploads/{current_user.profile_image}'
        
        return result
    
    # ---------------- ERROR HANDLERS ----------------
    @app.errorhandler(403)
    def forbidden(e: Exception) -> Tuple[str, int]:
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e: Exception) -> Tuple[str, int]:
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(e: Exception) -> Tuple[str, int]:
        logger.error(f"Internal server error: {e}")
        return render_template("errors/500.html"), 500

    return app

# -------------------------------------------------------------------
# Runner
# -------------------------------------------------------------------
def run_admin_panel() -> None:
    """Run the admin panel."""
    app = create_app()
    logger.info("[OK] Admin panel running → http://127.0.0.1:5000/login")
    app.run(host='127.0.0.1', port=5000, debug=True)

if __name__ == '__main__':
    run_admin_panel()