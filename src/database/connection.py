import os
import psycopg2
from psycopg2 import OperationalError, Error
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages PostgreSQL database connection."""

    def __init__(self):
        """Initialize database connection with environment variables."""
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.database = os.getenv("DB_NAME", "biometric_access_db")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "")
        self.connection = None
        self.cursor = None

    def connect(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.connection.cursor()
            logger.info(f"Connected to database: {self.database}")
            return True
        except OperationalError as e:
            logger.error(f"Connection failed: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            if not self.connection or self.connection.closed:
                return self.connect()

            self.cursor.execute("SELECT version();")
            version = self.cursor.fetchone()
            logger.debug(f"Database version: {version[0]}")
            return True
        except (OperationalError, Error) as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def execute_query(self, query: str, params: Tuple = None) -> Optional[List[Tuple]]:
        """Execute a SQL query and return results."""
        try:
            if not self.test_connection():
                return None

            self.cursor.execute(query, params or ())

            if query.strip().upper().startswith("SELECT"):
                return self.cursor.fetchall()
            else:
                self.connection.commit()
                return None
        except Error as e:
            logger.error(f"Query execution failed: {str(e)}")
            logger.error(f"Query: {query}")
            if params:
                logger.error(f"Parameters: {params}")
            self.connection.rollback()
            return None

    def create_tables(self) -> bool:
        """Create initial database tables based on proposal design."""
        try:
            logger.info("Creating database tables...")

            # Students table
            students_table = """
            CREATE TABLE IF NOT EXISTS students (
                student_id SERIAL PRIMARY KEY,
                registration_number VARCHAR(50) UNIQUE NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                phone VARCHAR(20),
                course VARCHAR(100),
                year_of_study INTEGER,
                enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            # Biometric templates table
            biometrics_table = """
            CREATE TABLE IF NOT EXISTS biometric_templates (
                template_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id) ON DELETE CASCADE,
                template_type VARCHAR(20) NOT NULL CHECK (template_type IN ('fingerprint', 'facial')),
                template_data BYTEA NOT NULL,
                template_hash VARCHAR(64) NOT NULL,
                quality_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, template_type)
            );
            """

            # Access logs table
            access_logs_table = """
            CREATE TABLE IF NOT EXISTS access_logs (
                log_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id),
                access_point VARCHAR(50) NOT NULL,
                verification_method VARCHAR(20) NOT NULL,
                verification_result VARCHAR(20) NOT NULL,
                match_score FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                additional_info TEXT
            );
            """

            # Administrators table
            administrators_table = """
            CREATE TABLE IF NOT EXISTS administrators (
                admin_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                role VARCHAR(20) DEFAULT 'operator',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
            """

            # System configuration table
            system_config_table = """
            CREATE TABLE IF NOT EXISTS system_config (
                config_id SERIAL PRIMARY KEY,
                config_key VARCHAR(50) UNIQUE NOT NULL,
                config_value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            # Execute table creation
            queries = [
                students_table,
                biometrics_table,
                access_logs_table,
                administrators_table,
                system_config_table,
            ]

            for query in queries:
                self.execute_query(query)

            # Insert default admin if not exists
            self.execute_query("""
                INSERT INTO administrators (username, password_hash, full_name, role)
                VALUES ('admin', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'System Administrator', 'superadmin')
                ON CONFLICT (username) DO NOTHING;
            """)

            # Insert default configurations
            default_configs = [
                (
                    "fingerprint_threshold",
                    "60",
                    "Minimum match score for fingerprint verification",
                ),
                (
                    "facial_threshold",
                    "0.6",
                    "Minimum match score for facial recognition",
                ),
                (
                    "max_login_attempts",
                    "3",
                    "Maximum failed login attempts before lockout",
                ),
                ("session_timeout", "30", "Admin session timeout in minutes"),
                ("system_mode", "operational", "System operational mode"),
            ]

            for key, value, description in default_configs:
                self.execute_query(
                    """
                    INSERT INTO system_config (config_key, config_value, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (config_key) DO UPDATE 
                    SET config_value = EXCLUDED.config_value,
                        updated_at = CURRENT_TIMESTAMP;
                """,
                    (key, value, description),
                )

            logger.info("Database tables created successfully")
            return True

        except Error as e:
            logger.error(f"Table creation failed: {str(e)}")
            return False

    def backup_database(self, backup_path: str) -> bool:
        """Create a database backup."""
        try:
            import subprocess
            import time

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_path}/backup_{timestamp}.sql"

            # Use pg_dump for backup
            cmd = [
                "pg_dump",
                "-h",
                self.host,
                "-p",
                self.port,
                "-U",
                self.user,
                "-d",
                self.database,
                "-f",
                backup_file,
            ]

            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env["PGPASSWORD"] = self.password

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Database backup created: {backup_file}")
                return True
            else:
                logger.error(f"Backup failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Backup error: {str(e)}")
            return False

    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Utility function for easy query execution
def execute_sql(query: str, params: Tuple = None) -> Optional[List[Tuple]]:
    """Execute SQL query using a temporary connection."""
    with DatabaseConnection() as db:
        return db.execute_query(query, params)


if __name__ == "__main__":
    # Test the database connection
    import sys

    sys.path.append("..")

    db = DatabaseConnection()
    if db.connect():
        print("✅ Database connection successful")
        if db.create_tables():
            print("✅ Database tables created/verified")
        db.close()
    else:
        print("❌ Database connection failed")
