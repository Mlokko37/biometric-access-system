import os
import sys
import logging
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)

class VerificationManager:
    """Manages the complete verification process."""
    
    def __init__(self, simulation_mode: bool = True):
        """Initialize verification manager."""
        self.simulation_mode = simulation_mode
        
        # Initialize components
        self._init_components()
        
    def _init_components(self):
        """Initialize verification components."""
        try:
            from src.verification.biometric_matcher import BiometricMatcher
            from src.verification.access_controller import AccessController
            from src.verification.logging_manager import LoggingManager
            from src.database.connection import DatabaseConnection
            
            self.matcher = BiometricMatcher()
            self.controller = AccessController(simulation_mode=self.simulation_mode)
            self.logger = LoggingManager()
            self.db = DatabaseConnection()
            
            logger.info("Verification components initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize components: {str(e)}")
            raise
    
    def start_verification(self, access_point: str = "Main Gate"):
        """Start the verification process."""
        try:
            print("\n" + "=" * 60)
            print(f"ACCESS VERIFICATION - {access_point}")
            print("=" * 60)
            
            # Step 1: Select verification method
            method = self.select_verification_method()
            if not method:
                logger.warning("Verification method selection cancelled")
                return
            
            # Step 2: Capture biometric data
            biometric_data = self.capture_biometric_data(method)
            if not biometric_data:
                self.controller.deny_access("Biometric capture failed")
                return
            
            # Step 3: Match against database
            match_result = self.match_against_database(biometric_data, method)
            
            # Step 4: Make access decision
            self.make_access_decision(match_result, access_point, method)
            
        except KeyboardInterrupt:
            logger.info("Verification cancelled by user")
            print("\n[WARN] Verification cancelled")
        except Exception as e:
            logger.error(f"Verification error: {str(e)}", exc_info=True)
            self.controller.deny_access(f"System error: {str(e)}")
    
    def select_verification_method(self) -> Optional[str]:
        """Select verification method."""
        print("\nSelect Verification Method:")
        print("1. Fingerprint Only")
        print("2. Facial Recognition Only")
        print("3. Multi-modal (Fingerprint + Facial)")
        print("4. Cancel")
        
        while True:
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                return 'fingerprint'
            elif choice == '2':
                return 'facial'
            elif choice == '3':
                return 'multi-modal'
            elif choice == '4':
                return None
            else:
                print("[ERROR] Invalid option. Please try again.")
    
    def capture_biometric_data(self, method: str) -> Optional[Dict[str, Any]]:
        """Capture biometric data based on method."""
        try:
            print(f"\nCapturing {method} biometric data...")
            self.controller.indicate_waiting()
            
            data = {}
            
            if method in ['fingerprint', 'multi-modal']:
                fp_data = self.capture_fingerprint()
                if fp_data:
                    data['fingerprint'] = fp_data
                elif method == 'fingerprint':
                    # Fingerprint required but capture failed
                    return None
            
            if method in ['facial', 'multi-modal']:
                face_data = self.capture_facial()
                if face_data:
                    data['facial'] = face_data
                elif method == 'facial':
                    # Facial required but capture failed
                    return None
            
            self.controller.indicate_processing()
            return data
            
        except Exception as e:
            logger.error(f"Biometric capture error: {str(e)}")
            return None
    
    def capture_fingerprint(self) -> Optional[bytes]:
        """Capture fingerprint data."""
        try:
            print("\nFingerprint Capture:")
            print("Place your finger on the scanner...")
            
            if self.simulation_mode:
                # Simulation mode
                input("Press Enter to simulate fingerprint capture...")
                import random
                template = bytes([random.randint(0, 255) for _ in range(512)])
                print("[OK] Fingerprint captured (simulation)")
                return template
            else:
                # Real hardware capture
                try:
                    from src.enrollment.fingerprint_capture import FingerprintCapture
                    capture = FingerprintCapture()
                    template = capture.capture_sample()
                    capture.cleanup()
                    
                    if template:
                        print("[OK] Fingerprint captured")
                        return template
                    else:
                        print("[ERROR] Fingerprint capture failed")
                        return None
                except ImportError:
                    print("[WARN] Fingerprint hardware not available, using simulation")
                    return self.capture_fingerprint()  # Recursive with simulation
            
        except Exception as e:
            logger.error(f"Fingerprint capture error: {str(e)}")
            return None
    
    def capture_facial(self) -> Optional[Any]:  # Should be np.ndarray
        """Capture facial data."""
        try:
            print("\nFacial Capture:")
            print("Look at the camera...")
            
            if self.simulation_mode:
                # Simulation mode
                input("Press Enter to simulate facial capture...")
                import numpy as np
                template = np.random.randn(128).astype(np.float32)
                print("[OK] Facial template captured (simulation)")
                return template
            else:
                # Real hardware capture
                try:
                    from src.enrollment.facial_capture import FacialCapture
                    capture = FacialCapture()
                    template = capture.capture_sample("verification")
                    capture.cleanup()
                    
                    if template is not None:
                        print("[OK] Facial template captured")
                        return template
                    else:
                        print("[ERROR] Facial capture failed")
                        return None
                except ImportError:
                    print("[WARN] Facial capture hardware not available, using simulation")
                    return self.capture_facial()  # Recursive with simulation
            
        except Exception as e:
            logger.error(f"Facial capture error: {str(e)}")
            return None
    
    def match_against_database(self, biometric_data: Dict[str, Any], method: str) -> Dict[str, Any]:
        """Match biometric data against database."""
        try:
            print("\nMatching against database...")
            
            # Connect to database
            if not self.db.connect():
                logger.error("Database connection failed")
                return {'error': 'Database connection failed'}
            
            # Get all stored templates for comparison
            # In production, you'd use more sophisticated search
            all_templates = self.get_all_templates()
            
            # Prepare data for matching
            fingerprint_data = None
            facial_data = None
            
            if 'fingerprint' in biometric_data:
                live_fp = biometric_data['fingerprint']
                stored_fps = [t['template_data'] for t in all_templates 
                            if t['template_type'] == 'fingerprint']
                fingerprint_data = (live_fp, stored_fps)
            
            if 'facial' in biometric_data:
                live_face = biometric_data['facial']
                stored_faces = [t['template_data'] for t in all_templates 
                              if t['template_type'] == 'facial']
                facial_data = (live_face, stored_faces)
            
            # Perform matching
            match_result = self.matcher.multi_modal_match(
                fingerprint_data=fingerprint_data,
                facial_data=facial_data
            )
            
            # Try to identify student
            student_info = self.identify_student(match_result, all_templates)
            match_result['student_info'] = student_info
            
            self.db.close()
            return match_result
            
        except Exception as e:
            logger.error(f"Database matching error: {str(e)}")
            return {'error': str(e), 'overall_match': False}
    
    def get_all_templates(self) -> list:
        """Get all biometric templates from database."""
        try:
            query = '''
                SELECT bt.*, s.registration_number, s.first_name, s.last_name
                FROM biometric_templates bt
                JOIN students s ON bt.student_id = s.student_id
                WHERE s.is_active = 1
            '''
            
            results = self.db.execute_query(query)
            if not results:
                return []
            
            templates = []
            for row in results:
                template = {
                    'student_id': row[0],
                    'template_type': row[2],
                    'template_data': row[3],  # This is bytes
                    'registration_number': row[7],
                    'first_name': row[8],
                    'last_name': row[9]
                }
                templates.append(template)
            
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get templates: {str(e)}")
            return []
    
    def identify_student(self, match_result: Dict[str, Any], all_templates: list) -> Optional[Dict[str, Any]]:
        """Identify student from match results."""
        try:
            # This is simplified - in production, you'd have better student identification
            if not match_result.get('overall_match', False):
                return None
            
            # Get matched template index from details
            details = match_result.get('details', {})
            
            if 'fingerprint' in details:
                fp_match = details['fingerprint']
                if fp_match.get('match', False):
                    matched_index = fp_match.get('matched_index', -1)
                    if matched_index >= 0:
                        # Find fingerprint template at this index
                        fp_templates = [t for t in all_templates 
                                      if t['template_type'] == 'fingerprint']
                        if matched_index < len(fp_templates):
                            return fp_templates[matched_index]
            
            if 'facial' in details:
                face_match = details['facial']
                if face_match.get('match', False):
                    matched_index = face_match.get('matched_index', -1)
                    if matched_index >= 0:
                        # Find facial template at this index
                        face_templates = [t for t in all_templates 
                                        if t['template_type'] == 'facial']
                        if matched_index < len(face_templates):
                            return face_templates[matched_index]
            
            return None
            
        except Exception as e:
            logger.error(f"Student identification error: {str(e)}")
            return None
    
    def make_access_decision(self, match_result: Dict[str, Any], 
                           access_point: str, method: str):
        """Make and execute access decision."""
        try:
            overall_match = match_result.get('overall_match', False)
            composite_score = match_result.get('composite_score', 0.0)
            student_info = match_result.get('student_info')
            
            # Log the access attempt
            registration = student_info.get('registration_number') if student_info else None
            student_id = student_info.get('student_id') if student_info else None
            
            self.logger.log_access(
                student_id=student_id,
                registration_number=registration,
                access_point=access_point,
                verification_method=method,
                result='granted' if overall_match else 'denied',
                match_score=composite_score,
                additional_info=str(match_result.get('details', {}))
            )
            
            # Execute decision
            if overall_match:
                # Access granted
                duration = 3  # seconds
                self.controller.grant_access(duration)
                
                # Display student info
                if student_info:
                    print(f"\n[OK] ACCESS GRANTED for:")
                    print(f"   Student: {student_info.get('first_name', '')} "
                         f"{student_info.get('last_name', '')}")
                    print(f"   Registration: {student_info.get('registration_number', '')}")
                    print(f"   Match Score: {composite_score:.2f}")
                else:
                    print(f"\n[OK] ACCESS GRANTED")
                    print(f"   Match Score: {composite_score:.2f}")
                
                # Log successful access
                self.logger.log_audit(
                    user_type='student',
                    user_id=student_id,
                    action='access_granted',
                    details=f"Access granted at {access_point}"
                )
            else:
                # Access denied
                reason = "Authentication failed"
                if composite_score > 0:
                    reason = f"Match score {composite_score:.2f} below threshold"
                
                self.controller.deny_access(reason)
                
                print(f"\n[ERROR] ACCESS DENIED")
                print(f"   Reason: {reason}")
                
                # Log failed attempt
                self.logger.log_audit(
                    user_type='unknown',
                    user_id=None,
                    action='access_denied',
                    details=f"Access denied at {access_point}: {reason}"
                )
            
            # Display match details
            self.display_match_details(match_result)
            
        except Exception as e:
            logger.error(f"Access decision error: {str(e)}")
            self.controller.deny_access(f"System error: {str(e)}")
    
    def display_match_details(self, match_result: Dict[str, Any]):
        """Display detailed match results."""
        print("\n" + "-" * 40)
        print("MATCH DETAILS:")
        print("-" * 40)
        
        details = match_result.get('details', {})
        
        if 'fingerprint' in details:
            fp = details['fingerprint']
            print(f"Fingerprint: {'[OK] MATCH' if fp.get('match') else '✗ NO MATCH'}")
            print(f"  Score: {fp.get('score', 0):.2f} (Threshold: {fp.get('threshold', 60)})")
        
        if 'facial' in details:
            face = details['facial']
            print(f"Facial: {'[OK] MATCH' if face.get('match') else '✗ NO MATCH'}")
            print(f"  Score: {face.get('score', 0):.4f} (Threshold: {face.get('threshold', 0.6)})")
        
        print(f"Composite Score: {match_result.get('composite_score', 0):.2f}")
        print("-" * 40)

def start_verification():
    """Start verification process (called from main.py)."""
    manager = VerificationManager(simulation_mode=True)
    return manager.start_verification()

def test_verification():
    """Test the verification system."""
    print("Testing Verification System...")
    
    manager = VerificationManager(simulation_mode=True)
    
    # Test with simulated data
    print("\nSimulating verification process...")
    
    # Simulate fingerprint capture
    import random
    simulated_fp = bytes([random.randint(0, 255) for _ in range(512)])
    
    # Simulate facial capture
    import numpy as np
    simulated_face = np.random.randn(128).astype(np.float32)
    
    # Create mock biometric data
    biometric_data = {
        'fingerprint': simulated_fp,
        'facial': simulated_face
    }
    
    # Test matching
    print("\nTesting biometric matching...")
    match_result = manager.match_against_database(biometric_data, 'multi-modal')
    
    print(f"Match Result: {match_result.get('overall_match', False)}")
    print(f"Composite Score: {match_result.get('composite_score', 0):.2f}")
    
    # Test access decision
    print("\nTesting access decision...")
    manager.make_access_decision(match_result, "Test Gate", "multi-modal")
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Run test or start verification
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_verification()
    else:
        start_verification()