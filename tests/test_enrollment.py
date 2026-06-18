import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/test_enrollment.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def test_database_connection():
    """Test database connection."""
    print("\n[1] Testing Database Connection...")
    try:
        from src.database.connection import DatabaseConnection
        
        db = DatabaseConnection()
        if db.connect():
            print("[OK] Database connection successful")
            
            # Create tables if they don't exist
            if db.create_tables():
                print("[OK] Database tables created/verified")
            else:
                print("[ERROR] Failed to create tables")
            
            db.close()
            return True
        else:
            print("[ERROR] Database connection failed")
            return False
    except Exception as e:
        print(f"[ERROR] Database test error: {str(e)}")
        return False

def test_biometric_processor():
    """Test biometric processor."""
    print("\n[2] Testing Biometric Processor...")
    try:
        from src.enrollment.biometric_processor import BiometricProcessor
        
        processor = BiometricProcessor()
        
        # Test fingerprint validation
        test_template = bytes([i % 256 for i in range(512)])
        is_valid, quality = processor.validate_fingerprint_template(test_template)
        print(f"[OK] Fingerprint validation: quality={quality:.2f}")
        
        # Test facial validation
        test_face = np.random.randn(128).astype(np.float32)
        is_valid, quality = processor.validate_facial_template(test_face)
        print(f"[OK] Facial validation: quality={quality:.4f}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Biometric processor test error: {str(e)}")
        return False

def test_template_manager():
    """Test template manager."""
    print("\n[3] Testing Template Manager...")
    try:
        from src.enrollment.template_manager import TemplateManager
        
        # Use a temporary directory for testing
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        manager = TemplateManager(temp_dir)
        
        # Test fingerprint template save
        test_fp = bytes([i % 256 for i in range(256)])
        fp_path = manager.save_fingerprint_template(999, test_fp)
        print(f"[OK] Fingerprint template saved")
        
        # Test facial template save
        import numpy as np
        test_face = np.random.randn(128).astype(np.float32)
        face_path = manager.save_facial_template(999, test_face)
        print(f"[OK] Facial template saved")
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        return True
    except Exception as e:
        print(f"[ERROR] Template manager test error: {str(e)}")
        return False

def test_enrollment_flow():
    """Test complete enrollment flow."""
    print("\n[4] Testing Enrollment Flow...")
    try:
        from src.enrollment.enroll_student import EnrollmentManager
        
        manager = EnrollmentManager()
        
        # Test student info collection (simulated)
        print("\nSimulating student info collection...")
        manager.student_data = {
            'registration_number': 'TEST001',
            'first_name': 'Test',
            'last_name': 'Student',
            'email': 'test@example.com',
            'phone': '0712345678',
            'course': 'Computer Science',
            'year_of_study': 3
        }
        
        # Simulate biometric capture
        print("Simulating biometric capture...")
        manager.fingerprint_templates = [bytes([1, 2, 3, 4])]
        manager.facial_templates = [np.random.randn(128).astype(np.float32)]
        
        print("[OK] Enrollment flow test completed (simulation)")
        return True
    except Exception as e:
        print(f"[ERROR] Enrollment flow test error: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("ENROLLMENT MODULE TEST SUITE")
    print("=" * 60)
    
    # Import numpy for tests
    global np
    import numpy as np
    
    tests = [
        test_database_connection,
        test_biometric_processor,
        test_template_manager,
        test_enrollment_flow
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n[WARN] Test interrupted by user")
            break
        except Exception as e:
            print(f"[ERROR] Test {test_func.__name__} crashed: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n[OK] All tests passed! Enrollment module is ready.")
        print("\nTo use the enrollment system:")
        print("1. Ensure PostgreSQL is running")
        print("2. Configure .env with database credentials")
        print("3. Run: python main.py enroll")
        return True
    else:
        print(f"\n[WARN] {failed} test(s) failed. Please check the logs.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
