import numpy as np
import logging
from typing import Optional, Tuple, List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class BiometricMatcher:
    """Matches biometric templates against stored templates."""
    
    def __init__(self, fingerprint_threshold: float = 60, facial_threshold: float = 0.6):
        """Initialize matcher with thresholds."""
        self.fingerprint_threshold = fingerprint_threshold
        self.facial_threshold = facial_threshold
        
    def match_fingerprint(self, live_template: bytes, stored_templates: List[bytes]) -> Tuple[bool, float, int]:
        """
        Match fingerprint against stored templates.
        
        Args:
            live_template: Live fingerprint template
            stored_templates: List of stored templates
            
        Returns:
            (is_match, best_score, template_index)
        """
        try:
            if not stored_templates:
                logger.warning("No stored fingerprint templates to match against")
                return False, 0.0, -1
            
            best_score = 0.0
            best_index = -1
            
            # Convert live template to numpy array
            live_array = np.frombuffer(live_template, dtype=np.uint8)
            
            for i, stored_template in enumerate(stored_templates):
                # Convert stored template
                stored_array = np.frombuffer(stored_template, dtype=np.uint8)
                
                # Ensure arrays are same length
                min_len = min(len(live_array), len(stored_array))
                if min_len == 0:
                    continue
                
                live_slice = live_array[:min_len]
                stored_slice = stored_array[:min_len]
                
                # Calculate correlation score (0-100)
                correlation = np.corrcoef(live_slice, stored_slice)[0, 1]
                score = max(0, (correlation + 1) * 50)  # Convert to 0-100 scale
                
                if score > best_score:
                    best_score = score
                    best_index = i
            
            is_match = best_score >= self.fingerprint_threshold
            
            logger.debug(f"Fingerprint match - Best score: {best_score:.2f}, "
                        f"Threshold: {self.fingerprint_threshold}, Match: {is_match}")
            
            return is_match, best_score, best_index
            
        except Exception as e:
            logger.error(f"Fingerprint matching error: {str(e)}")
            return False, 0.0, -1
    
    def match_facial(self, live_template: np.ndarray, stored_templates: List[np.ndarray]) -> Tuple[bool, float, int]:
        """
        Match facial template against stored templates.
        
        Args:
            live_template: Live facial template
            stored_templates: List of stored templates
            
        Returns:
            (is_match, best_score, template_index)
        """
        try:
            if not stored_templates:
                logger.warning("No stored facial templates to match against")
                return False, 0.0, -1
            
            best_score = 0.0
            best_index = -1
            
            for i, stored_template in enumerate(stored_templates):
                # Ensure templates are same length
                min_len = min(len(live_template), len(stored_template))
                if min_len == 0:
                    continue
                
                live_slice = live_template[:min_len]
                stored_slice = stored_template[:min_len]
                
                # Calculate cosine similarity
                norm_live = np.linalg.norm(live_slice)
                norm_stored = np.linalg.norm(stored_slice)
                
                if norm_live == 0 or norm_stored == 0:
                    similarity = 0.0
                else:
                    similarity = np.dot(live_slice, stored_slice) / (norm_live * norm_stored)
                
                # Convert to 0-1 scale
                score = (similarity + 1) / 2
                
                if score > best_score:
                    best_score = score
                    best_index = i
            
            is_match = best_score >= self.facial_threshold
            
            logger.debug(f"Facial match - Best score: {best_score:.4f}, "
                        f"Threshold: {self.facial_threshold}, Match: {is_match}")
            
            return is_match, best_score, best_index
            
        except Exception as e:
            logger.error(f"Facial matching error: {str(e)}")
            return False, 0.0, -1
    
    def multi_modal_match(self, fingerprint_data: Optional[Tuple[bytes, List[bytes]]] = None,
                         facial_data: Optional[Tuple[np.ndarray, List[np.ndarray]]] = None) -> Dict[str, Any]:
        """
        Perform multi-modal biometric matching.
        
        Args:
            fingerprint_data: (live_template, stored_templates) or None
            facial_data: (live_template, stored_templates) or None
            
        Returns:
            Dict with match results
        """
        results = {
            'overall_match': False,
            'fingerprint_match': False,
            'facial_match': False,
            'composite_score': 0.0,
            'decision': 'denied',
            'details': {}
        }
        
        try:
            # Match fingerprints if available
            if fingerprint_data:
                live_fp, stored_fps = fingerprint_data
                fp_match, fp_score, fp_index = self.match_fingerprint(live_fp, stored_fps)
                results['fingerprint_match'] = fp_match
                results['details']['fingerprint'] = {
                    'match': fp_match,
                    'score': fp_score,
                    'threshold': self.fingerprint_threshold,
                    'matched_index': fp_index
                }
            else:
                fp_match = False
                fp_score = 0.0
            
            # Match facial if available
            if facial_data:
                live_face, stored_faces = facial_data
                face_match, face_score, face_index = self.match_facial(live_face, stored_faces)
                results['facial_match'] = face_match
                results['details']['facial'] = {
                    'match': face_match,
                    'score': face_score,
                    'threshold': self.facial_threshold,
                    'matched_index': face_index
                }
            else:
                face_match = False
                face_score = 0.0
            
            # Calculate composite score
            if fingerprint_data and facial_data:
                # Both modalities available
                fp_normalized = fp_score  # Already 0-100
                face_normalized = face_score * 100  # Convert 0-1 to 0-100
                
                # Weighted average (fingerprint more reliable)
                composite = (fp_normalized * 0.6 + face_normalized * 0.4)
                
                # Decision logic: Both must match OR composite score > 70
                overall_match = (fp_match and face_match) or composite > 70
                
            elif fingerprint_data:
                # Only fingerprint available
                composite = fp_score
                overall_match = fp_match
                
            elif facial_data:
                # Only facial available
                composite = face_score * 100
                overall_match = face_match
                
            else:
                # No biometric data
                composite = 0.0
                overall_match = False
            
            results['overall_match'] = overall_match
            results['composite_score'] = composite
            results['decision'] = 'granted' if overall_match else 'denied'
            
            logger.info(f"Multi-modal match - Decision: {results['decision']}, "
                       f"Composite: {composite:.2f}, FP: {fp_score:.2f}, Face: {face_score:.4f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Multi-modal matching error: {str(e)}")
            return results

def test_biometric_matcher():
    """Test the biometric matcher."""
    print("Testing Biometric Matcher...")
    
    matcher = BiometricMatcher(fingerprint_threshold=60, facial_threshold=0.6)
    
    # Test fingerprint matching
    print("\n1. Fingerprint Matching:")
    live_fp = bytes([i % 256 for i in range(512)])
    stored_fps = [
        bytes([i % 256 for i in range(512)]),  # Same pattern
        bytes([(i + 10) % 256 for i in range(512)])  # Different pattern
    ]
    
    fp_match, fp_score, fp_index = matcher.match_fingerprint(live_fp, stored_fps)
    print(f"   Match: {fp_match}, Score: {fp_score:.2f}, Index: {fp_index}")
    
    # Test facial matching
    print("\n2. Facial Matching:")
    live_face = np.random.randn(128).astype(np.float32)
    stored_faces = [
        live_face + np.random.randn(128) * 0.1,  # Slightly different
        np.random.randn(128).astype(np.float32)  # Completely different
    ]
    
    face_match, face_score, face_index = matcher.match_facial(live_face, stored_faces)
    print(f"   Match: {face_match}, Score: {face_score:.4f}, Index: {face_index}")
    
    # Test multi-modal matching
    print("\n3. Multi-modal Matching:")
    results = matcher.multi_modal_match(
        fingerprint_data=(live_fp, stored_fps),
        facial_data=(live_face, stored_faces)
    )
    
    print(f"   Overall Match: {results['overall_match']}")
    print(f"   Composite Score: {results['composite_score']:.2f}")
    print(f"   Decision: {results['decision'].upper()}")
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_biometric_matcher()