import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """Test that core modules can be imported."""
    try:
        from src.database.connection import DatabaseConnection
        assert True, "DatabaseConnection imported successfully"
    except ImportError as e:
        assert False, f"Import failed: {str(e)}"

def test_environment():
    """Test that environment file exists."""
    assert os.path.exists('.env') or os.path.exists('.env.example'), \
        "Environment file (.env or .env.example) should exist"

def test_directory_structure():
    """Test that required directories exist."""
    required_dirs = [
        'src',
        'src/database',
        'src/enrollment',
        'src/verification',
        'data',
        'data/logs',
        'tests'
    ]
    
    for dir_path in required_dirs:
        assert os.path.exists(dir_path), f"Directory {dir_path} should exist"

def test_requirements_file():
    """Test that requirements.txt exists."""
    assert os.path.exists('requirements.txt'), "requirements.txt should exist"
    
    # Check that it has some expected content
    with open('requirements.txt', 'r') as f:
        content = f.read()
        assert 'python' in content.lower(), "requirements.txt should contain Python"
        assert 'opencv' in content.lower(), "requirements.txt should contain OpenCV"

if __name__ == "__main__":
    # Run all tests
    test_functions = [
        test_imports,
        test_environment,
        test_directory_structure,
        test_requirements_file
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"[PASS] {test_func.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_func.__name__}: FAILED - {str(e)}")
            failed += 1
    
    print(f"\nTests: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)