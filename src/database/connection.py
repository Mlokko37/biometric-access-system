"""
Database connection module with local PostgreSQL.
Uses connection pooling for optimal performance.
"""

import os
import psycopg2
import logging
import hashlib
from psycopg2 import OperationalError, Error
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List, Tuple, Union
from contextlib import contextmanager
from flask import g, has_app_context

logger = logging.getLogger(__name__)

# =====================================================================
# LOCAL POSTGRESQL DATABASE CONFIGURATION
# =====================================================================

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "biometric_access_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "2546"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

# =====================================================================
# CONNECTION POOL (Single source of truth)
# =====================================================================
_pool = None

def init_pool():
    """Initialize the connection pool (call once at app startup)."""
    global _pool
    try:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            **DB_CONFIG
        )
        logger.info(f"[OK] PostgreSQL connection pool initialized for database: {DB_CONFIG['dbname']}")
        
        # Test connection
        test_conn = _pool.getconn()
        with test_conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()
            logger.info(f"[OK] PostgreSQL version: {version[0][:50]}...")
        _pool.putconn(test_conn)
        
        return True
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize connection pool: {e}")
        _pool = None
        return False

def get_pool():
    """Get the connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        init_pool()
    return _pool

def is_pool_initialized() -> bool:
    """Check if pool is initialized and working."""
    return _pool is not None

# =====================================================================
# CONNECTION MANAGEMENT
# =====================================================================

def get_db_connection():
    """
    Get a connection from the pool.
    Use this in Flask routes WITHOUT request context.
    """
    pool = get_pool()
    if pool is None:
        logger.error("[ERROR] Connection pool not initialized")
        raise Exception("Database connection pool not initialized")
    
    try:
        conn = pool.getconn()
        if conn is None:
            raise Exception("Failed to get connection from pool")
        return conn
    except Exception as e:
        logger.error(f"[ERROR] Failed to get connection from pool: {e}")
        raise

def release_db_connection(conn):
    """
    Release a connection back to the pool.
    Always call this when done with a connection from get_db_connection().
    """
    pool = get_pool()
    if pool is None:
        logger.warning("[WARN] Connection pool not initialized, cannot release connection")
        return
    
    if conn is not None:
        try:
            pool.putconn(conn)
        except Exception as e:
            logger.error(f"[ERROR] Failed to release connection: {e}")

def close_all_connections():
    """Close all connections in the pool (call on app shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("[LOCK] All database connections closed")

# =====================================================================
# FLASK REQUEST-SPECIFIC CONNECTION
# =====================================================================

def get_flask_db():
    """
    Get a database connection for the current Flask request.
    This REUSES the same connection throughout the entire request.
    Call this in Flask routes - it automatically releases at request end.
    """
    if not has_app_context():
        return get_db_connection()
    
    if 'db_conn' not in g:
        g.db_conn = get_db_connection()
    return g.db_conn

def close_flask_db(error=None):
    """Close the Flask request connection (automatically called by teardown)."""
    if has_app_context() and 'db_conn' in g:
        conn = g.db_conn
        if conn is not None:
            release_db_connection(conn)
        del g.db_conn

def init_app(app):
    """Initialize Flask app with database teardown."""
    app.teardown_appcontext(close_flask_db)
    logger.info("[OK] Flask database teardown registered")

# =====================================================================
# CONTEXT MANAGER (for non-Flask code)
# =====================================================================

@contextmanager
def db_connection():
    """
    Context manager for database connections.
    Use this in scripts or non-Flask code.
    
    Usage:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
    """
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    finally:
        if conn is not None:
            release_db_connection(conn)

@contextmanager
def db_cursor():
    """
    Context manager for database cursors.
    Automatically gets connection and releases it.
    
    Usage:
        with db_cursor() as cur:
            cur.execute("SELECT * FROM users")
            results = cur.fetchall()
    """
    with db_connection() as conn:
        if conn is None:
            raise Exception("Failed to get database connection")
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

# =====================================================================
# QUERY EXECUTION HELPERS
# =====================================================================

def execute_query(query: str, params: Union[tuple, list, None] = None):
    """
    Execute a query and return results.
    Use this in Flask routes - it uses the request-scoped connection.
    """
    conn = None
    try:
        if has_app_context():
            conn = get_flask_db()
        else:
            conn = get_db_connection()
        
        if conn is None:
            raise Exception("Failed to get database connection")
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            safe_params = params if params is not None else ()
            cur.execute(query, safe_params)
            
            if query.strip().upper().startswith(('SELECT', 'WITH')):
                results = cur.fetchall()
                return [dict(row) for row in results]
            else:
                conn.commit()
                return []
    except Exception as e:
        logger.error(f"[ERROR] Query execution failed: {e}")
        logger.error(f"   Query: {query[:200]}...")
        if params:
            logger.error(f"   Params: {params}")
        if conn is not None:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if not has_app_context() and conn is not None:
            release_db_connection(conn)

# =====================================================================
# LEGACY COMPATIBILITY - DatabaseConnection class
# =====================================================================

class DatabaseConnection:
    """
    Legacy compatibility class. Use execute_query() or db_cursor() instead.
    """
    
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def connect(self) -> bool:
        """Establish database connection."""
        try:
            self.connection = get_db_connection()
            if self.connection is None:
                return False
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.connection.cursor()
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection is not None:
            release_db_connection(self.connection)
            self.connection = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def test_connection(self) -> bool:
        try:
            if self.connection is None or self.connection.closed:
                return self.connect()
            if self.cursor is None:
                self.cursor = self.connection.cursor()
            self.cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = ()):
        """Execute a query and return results."""
        try:
            if self.connection is None or self.connection.closed:
                if not self.connect():
                    return None
            
            if self.cursor is None:
                if self.connection is not None:
                    self.cursor = self.connection.cursor()
                else:
                    logger.error("Cannot create cursor: connection is None")
                    return None
            
            safe_params = params if params is not None else ()
            self.cursor.execute(query, safe_params)
            
            if query.strip().upper().startswith(('SELECT', 'WITH')):
                return self.cursor.fetchall()
            else:
                if self.connection is not None:
                    self.connection.commit()
                    return []
                else:
                    logger.error("Cannot commit: connection is None")
                    return None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            if self.connection:
                try:
                    self.connection.rollback()
                except:
                    pass
            return None
    
    def create_tables(self) -> bool:
        """Create all required tables if they don't exist."""
        try:
            queries = [
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id VARCHAR(50) PRIMARY KEY,
                    registration_number VARCHAR(50) UNIQUE NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    course VARCHAR(100),
                    year_of_study INTEGER,
                    profile_image TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS biometric_templates (
                    template_id SERIAL PRIMARY KEY,
                    student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
                    template_type VARCHAR(20) CHECK (template_type IN ('fingerprint', 'facial')),
                    template_data BYTEA NOT NULL,
                    template_hash VARCHAR(64) NOT NULL,
                    quality_score FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id, template_type)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS access_logs (
                    log_id SERIAL PRIMARY KEY,
                    student_id VARCHAR(50) REFERENCES students(student_id),
                    access_point VARCHAR(50),
                    verification_method VARCHAR(20),
                    verification_result VARCHAR(20),
                    match_score FLOAT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS administrators (
                    admin_id SERIAL PRIMARY KEY,
                    firebase_uid VARCHAR(128) UNIQUE,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    role VARCHAR(20) DEFAULT 'staff',
                    is_active BOOLEAN DEFAULT TRUE,
                    email_verified BOOLEAN DEFAULT FALSE,
                    firebase_last_sync TIMESTAMP,
                    profile_image TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    updated_at TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id VARCHAR(100) PRIMARY KEY,
                    device_name VARCHAR(100) NOT NULL,
                    device_type VARCHAR(50) NOT NULL,
                    location VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'offline',
                    last_seen TIMESTAMP,
                    ip_address VARCHAR(45),
                    port INTEGER,
                    username VARCHAR(100),
                    password VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    id SERIAL PRIMARY KEY,
                    setting_name VARCHAR(100) UNIQUE NOT NULL,
                    setting_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50),
                    action VARCHAR(100),
                    details TEXT,
                    ip_address VARCHAR(45),
                    status VARCHAR(20),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            ]

            for query in queries:
                self.execute_query(query)

            return True

        except Exception as e:
            logger.error(f"Table creation failed: {e}")
            return False
    
    def save_biometric_template(self, student_id: str, template_type: str, template_data: bytes, quality_score: float = 0.0) -> bool:
        try:
            template_hash = hashlib.sha256(template_data).hexdigest()
            
            existing = self.execute_query(
                "SELECT template_id FROM biometric_templates WHERE student_id=%s AND template_type=%s",
                (student_id, template_type)
            )
            
            if existing:
                self.execute_query(
                    """
                    UPDATE biometric_templates
                    SET template_data=%s, template_hash=%s, quality_score=%s, created_at=CURRENT_TIMESTAMP
                    WHERE student_id=%s AND template_type=%s
                    """,
                    (psycopg2.Binary(template_data), template_hash, quality_score, student_id, template_type)
                )
            else:
                self.execute_query(
                    """
                    INSERT INTO biometric_templates
                    (student_id, template_type, template_data, template_hash, quality_score)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (student_id, template_type, psycopg2.Binary(template_data), template_hash, quality_score)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to save biometric template: {e}")
            return False
    
    def get_student_templates(self, student_id: str) -> Dict[str, List[bytes]]:
        try:
            rows = self.execute_query(
                """
                SELECT template_type, template_data
                FROM biometric_templates
                WHERE student_id=%s
                ORDER BY created_at DESC
                """,
                (student_id,)
            )
            
            templates = {"fingerprint": [], "facial": []}
            if rows:
                for row in rows:
                    if row and len(row) >= 2:
                        t_type, t_data = row[0], row[1]
                        if t_type in templates:
                            templates[t_type].append(t_data)
            
            return templates
        except Exception as e:
            logger.error(f"Failed to get student templates: {e}")
            return {"fingerprint": [], "facial": []}
    
    def get_all_templates(self) -> List[Dict[str, Any]]:
        try:
            rows = self.execute_query(
                """
                SELECT
                    bt.student_id,
                    bt.template_type,
                    bt.template_data,
                    s.registration_number,
                    s.first_name,
                    s.last_name
                FROM biometric_templates bt
                JOIN students s ON bt.student_id = s.student_id
                WHERE s.is_active = TRUE
                """
            ) or []
            
            result = []
            for r in rows:
                if r and len(r) >= 6:
                    result.append({
                        "student_id": r[0],
                        "template_type": r[1],
                        "template_data": r[2],
                        "registration_number": r[3],
                        "first_name": r[4],
                        "last_name": r[5],
                    })
            return result
        except Exception as e:
            logger.error(f"Failed to get templates: {e}")
            return []

# Initialize the pool when module is imported
init_pool()