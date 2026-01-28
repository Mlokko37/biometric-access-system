import os
import sys
import logging
from datetime import datetime

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'data/logs/system_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    logger.info("=" * 60)
    logger.info("BIOMETRIC STUDENT ACCESS CONTROL SYSTEM")
    logger.info("Kibabii University - Group Three")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            logger.warning(".env file not found. Using .env.example as template.")
            if os.path.exists('.env.example'):
                logger.info("Please copy .env.example to .env and configure your settings.")
            else:
                logger.error(".env.example not found. Cannot proceed.")
                return
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        logger.info("Environment variables loaded successfully")
        
        # Display system information
        logger.info(f"Database: {os.getenv('DB_NAME', 'Not configured')}")
        logger.info(f"Debug Mode: {os.getenv('APP_DEBUG', 'False')}")
        
        # Initialize system modules
        initialize_system()
        
        # Start the appropriate mode based on command line arguments
        if len(sys.argv) > 1:
            handle_command(sys.argv[1:])
        else:
            start_interactive_mode()
            
    except KeyboardInterrupt:
        logger.info("\nSystem shutdown requested by user")
    except Exception as e:
        logger.error(f"System error: {str(e)}", exc_info=True)
    finally:
        logger.info("System shutdown completed")
        logger.info("=" * 60)

def initialize_system():
    """Initialize all system components."""
    logger.info("Initializing system components...")
    
    # Check for required directories
    required_dirs = ['data/sample_templates', 'data/logs', 'data/backups']
    for dir_path in required_dirs:
        os.makedirs(dir_path, exist_ok=True)
        logger.debug(f"Directory verified: {dir_path}")
    
    # Initialize database connection
    try:
        from src.database.connection import DatabaseConnection
        db = DatabaseConnection()
        if db.test_connection():
            logger.info("Database connection established successfully")
        else:
            logger.warning("Database connection failed")
    except ImportError:
        logger.warning("Database module not yet implemented")
    
    logger.info("System initialization completed")

def handle_command(args):
    """Handle command line arguments."""
    command = args[0] if args else 'help'
    
    if command == 'enroll':
        logger.info("Starting enrollment mode...")
        # Import and run enrollment module
        try:
            from src.enrollment.enroll_student import start_enrollment
            start_enrollment()
        except ImportError:
            logger.error("Enrollment module not implemented yet")
    
    elif command == 'verify':
        logger.info("Starting verification mode...")
        # Import and run verification module
        try:
            from src.verification.verify_student import start_verification
            start_verification()
        except ImportError:
            logger.error("Verification module not implemented yet")
    
    elif command == 'admin':
        logger.info("Starting admin interface...")
        # Start Flask admin interface
        try:
            from src.admin.app import run_admin_panel
            run_admin_panel()
        except ImportError:
            logger.error("Admin interface not implemented yet")
    
    elif command == 'test':
        logger.info("Running system tests...")
        # Run tests
        os.system("pytest tests/ -v")
    
    elif command == 'help':
        show_help()
    
    else:
        logger.error(f"Unknown command: {command}")
        show_help()

def start_interactive_mode():
    """Start the system in interactive mode."""
    print("\n" + "="*60)
    print("BIOMETRIC STUDENT ACCESS CONTROL SYSTEM")
    print("="*60)
    
    while True:
        print("\nMain Menu:")
        print("1. Student Enrollment")
        print("2. Access Verification")
        print("3. Admin Dashboard")
        print("4. System Configuration")
        print("5. Run Tests")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == '1':
            handle_command(['enroll'])
        elif choice == '2':
            handle_command(['verify'])
        elif choice == '3':
            handle_command(['admin'])
        elif choice == '4':
            configure_system()
        elif choice == '5':
            handle_command(['test'])
        elif choice == '6':
            logger.info("Exiting system...")
            break
        else:
            print("Invalid option. Please try again.")

def configure_system():
    """System configuration menu."""
    print("\nSystem Configuration:")
    print("1. Check Database Connection")
    print("2. Test Hardware")
    print("3. View System Logs")
    print("4. Backup Database")
    print("5. Return to Main Menu")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        test_database()
    elif choice == '2':
        test_hardware()
    elif choice == '3':
        view_logs()
    elif choice == '4':
        backup_database()
    elif choice == '5':
        return
    else:
        print("Invalid option")

def test_database():
    """Test database connection."""
    logger.info("Testing database connection...")
    try:
        from src.database.connection import DatabaseConnection
        db = DatabaseConnection()
        if db.test_connection():
            print("✅ Database connection successful")
        else:
            print("❌ Database connection failed")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_hardware():
    """Test hardware components."""
    print("\nHardware Testing:")
    print("1. Test Fingerprint Scanner")
    print("2. Test Camera")
    print("3. Test Access Lock")
    print("4. Test All Hardware")
    
    choice = input("\nSelect option (1-4): ").strip()
    logger.info(f"Testing hardware option: {choice}")
    print("Hardware testing module not implemented yet")

def view_logs():
    """View system logs."""
    logger.info("Viewing system logs...")
    try:
        log_files = [f for f in os.listdir('data/logs') if f.endswith('.log')]
        if log_files:
            print(f"\nAvailable log files ({len(log_files)}):")
            for i, log_file in enumerate(sorted(log_files)[-5:], 1):  # Show last 5
                print(f"{i}. {log_file}")
            
            choice = input("\nEnter number to view (or 0 to go back): ").strip()
            if choice.isdigit() and int(choice) > 0:
                selected = sorted(log_files)[-int(choice)]
                with open(f'data/logs/{selected}', 'r') as f:
                    print(f"\n--- {selected} ---")
                    print(f.read()[-2000:])  # Last 2000 characters
        else:
            print("No log files found")
    except Exception as e:
        print(f"Error reading logs: {str(e)}")

def backup_database():
    """Backup database."""
    logger.info("Starting database backup...")
    backup_file = f"data/backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    print(f"Backup would be saved to: {backup_file}")
    print("Database backup module not implemented yet")

def show_help():
    """Display help information."""
    print("\nUsage: python main.py [command]")
    print("\nCommands:")
    print("  enroll    - Start student enrollment process")
    print("  verify    - Start access verification process")
    print("  admin     - Launch admin web interface")
    print("  test      - Run system tests")
    print("  help      - Show this help message")
    print("\nExamples:")
    print("  python main.py enroll")
    print("  python main.py verify")
    print("  python main.py            # Interactive mode")

if __name__ == "__main__":
    main()
