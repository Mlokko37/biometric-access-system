import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_biometric_matcher():
    """Test biometric matcher."""
    print("\n[1] Testing Biometric Matcher...")
    try:
        from src.verification.biometric_matcher import BiometricMatcher
        
        matcher = BiometricMatcher()
        
        # Test fingerprint matching
        live_fp = bytes([i % 256 for i in range(512)])
        stored_fps = [bytes([i % 256 for i in range(512)])]
        
        match, score, index = matcher.match_fingerprint(live_fp, stored_fps)
        print(f"[OK] Fingerprint match: {match}, Score: {score:.2f}")
        
        # Test facial matching
        import numpy as np
        live_face = np.random.randn(128).astype(np.float32)
        stored_faces = [live_face + np.random.randn(128) * 0.1]
        
        match, score, index = matcher.match_facial(live_face, stored_faces)
        print(f"[OK] Facial match: {match}, Score: {score:.4f}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Biometric matcher test failed: {str(e)}")
        return False

def test_access_controller():
    """Test access controller."""
    print("\n[2] Testing Access Controller...")
    try:
        from src.verification.access_controller import AccessController
        
        controller = AccessController(simulation_mode=True)
        controller.grant_access(duration=1)
        controller.deny_access("Test denial")
        controller.cleanup()
        
        print("[OK] Access controller test passed")
        return True
    except Exception as e:
        print(f"[ERROR] Access controller test failed: {str(e)}")
        return False

def test_logging_manager():
    """Test logging manager."""
    print("\n[3] Testing Logging Manager...")
    try:
        import tempfile
        from src.verification.logging_manager import LoggingManager
        
        temp_db = tempfile.mktemp(suffix='.db')
        manager = LoggingManager(temp_db)
        
        # Log some events
        manager.log_access(
            student_id=1,
            registration_number="TEST001",
            access_point="Main Gate",
            verification_method="fingerprint",
            result="granted",
            match_score=85.5
        )
        
        # Get logs
        logs = manager.get_access_logs()
        print(f"[OK] Logged {len(logs)} access events")
        
        # Get statistics
        stats = manager.get_statistics()
        print(f"[OK] Generated statistics: {stats}")
        
        # Cleanup
        import os
        if os.path.exists(temp_db):
            os.remove(temp_db)
        
        return True
    except Exception as e:
        print(f"[ERROR] Logging manager test failed: {str(e)}")
        return False

def test_verification_flow():
    """Test complete verification flow."""
    print("\n[4] Testing Verification Flow...")
    try:
        from src.verification.verify_access import VerificationManager
        
        manager = VerificationManager(simulation_mode=True)
        
        print("Simulating verification process...")
        
        # Test method selection
        print("\nMethod selection test...")
        # This would normally get user input, but for test we'll simulate
        method = 'fingerprint'
        print(f"Selected method: {method}")
        
        # Test biometric capture
        print("\nBiometric capture test...")
        biometric_data = manager.capture_biometric_data(method)
        print(f"Captured biometric data: {'fingerprint' in biometric_data}")
        
        # Test database matching
        print("\nDatabase matching test...")
        match_result = manager.match_against_database(biometric_data, method)
        print(f"Match result: {match_result.get('overall_match', False)}")
        
        print("[OK] Verification flow test completed")
        return True
    except Exception as e:
        print(f"[ERROR] Verification flow test failed: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("VERIFICATION MODULE TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_biometric_matcher,
        test_access_controller,
        test_logging_manager,
        test_verification_flow
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
        print("\n[OK] All verification tests passed!")
        print("\nTo use the verification system:")
        print("1. Run: python main.py")
        print("2. Select '2. Access Verification'")
        print("3. Choose verification method")
        print("4. Follow the prompts")
        return True
    else:
        print(f"\n[WARN] {failed} test(s) failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
