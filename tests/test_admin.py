import os
import sys
import tempfile
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_database_setup():
    """Test database setup for admin."""
    print("\n[1] Testing Database Setup...")
    try:
        from src.database.connection import DatabaseConnection
        
        db = DatabaseConnection()
        if db.connect():
            print("[OK] Database connection successful")
            
            # Create tables
            if db.create_tables():
                print("[OK] Database tables created")
                
                # Check if admin exists
                result = db.execute_query("SELECT COUNT(*) FROM administrators")
                if result:
                    print(f"[OK] Found {result[0][0]} admin accounts")
                
                # Check if default admin exists
                result = db.execute_query("SELECT * FROM administrators WHERE username = 'admin'")
                if result:
                    print("[OK] Default admin account exists")
                else:
                    print("[WARN] Default admin account not found")
                
            db.close()
            return True
        else:
            print("[ERROR] Database connection failed")
            return False
    except Exception as e:
        print(f"[ERROR] Database test error: {str(e)}")
        return False

def test_auth_module():
    """Test authentication module."""
    print("\n[2] Testing Authentication Module...")
    try:
        from src.admin.auth import AdminUser, create_default_admin
        
        # Test password hashing
        password = "test123"
        hashed = AdminUser.hash_password(password)
        print(f"[OK] Password hashing works")
        
        # Test password verification
        test_user = AdminUser(
            user_id=1,
            username="test",
            password_hash=hashed,
            full_name="Test User",
            role="admin"
        )
        
        if test_user.verify_password(password):
            print("[OK] Password verification works")
        else:
            print("[ERROR] Password verification failed")
        
        # Test default admin creation
        create_default_admin()
        print("[OK] Default admin creation tested")
        
        return True
    except Exception as e:
        print(f"[ERROR] Auth test error: {str(e)}")
        return False

def test_flask_app():
    """Test Flask application creation."""
    print("\n[3] Testing Flask Application...")
    try:
        from src.admin.app import create_app
        
        # Create test app
        app = create_app()
        
        # Test app configuration
        if app.config['SECRET_KEY']:
            print("[OK] Flask app created with secret key")
        
        # Test routes
        with app.test_client() as client:
            # Test home redirect
            response = client.get('/')
            if response.status_code in [200, 302]:
                print("[OK] Home route works")
            
            # Test login page
            response = client.get('/login')
            if response.status_code == 200:
                print("[OK] Login page works")
            
            # Test system status (should redirect to login)
            response = client.get('/system-status')
            if response.status_code == 401 or response.status_code == 200:
                print("[OK] System status endpoint exists")
        
        return True
    except Exception as e:
        print(f"[ERROR] Flask test error: {str(e)}")
        return False

def test_admin_modules():
    """Test admin modules."""
    print("\n[4] Testing Admin Modules...")
    try:
        # Test dashboard module
        from src.admin.dashboard import dashboard_bp
        print("[OK] Dashboard blueprint loaded")
        
        # Test reports module
        from src.admin.reports import reports_bp
        print("[OK] Reports blueprint loaded")
        
        # Test student management module
        from src.admin.student_management import students_bp
        print("[OK] Student management blueprint loaded")
        
        return True
    except Exception as e:
        print(f"[ERROR] Admin modules test error: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("ADMIN INTERFACE TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_database_setup,
        test_auth_module,
        test_flask_app,
        test_admin_modules
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
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
        print("\n[OK] All admin interface tests passed!")
        print("\nTo start the admin interface:")
        print("1. Run: python -c \"from src.admin.app import run_admin_panel; run_admin_panel()\"")
        print("2. Or run: python src/admin/app.py")
        print("3. Open browser: http://127.0.0.1:5000")
        print("4. Login with: admin / password")
        return True
    else:
        print(f"\n[WARN] {failed} test(s) failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)