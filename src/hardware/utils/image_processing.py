"""
Image processing utilities for biometric systems
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Image processing utilities for biometric applications"""
    
    @staticmethod
    def preprocess_face_image(image: np.ndarray) -> Optional[np.ndarray]:
        """Preprocess face image for recognition"""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Denoise
            denoised = cv2.medianBlur(enhanced, 3)
            
            return denoised
            
        except Exception as e:
            logger.error(f"Error preprocessing face image: {e}")
            return None
    
    @staticmethod
    def detect_faces(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces in image"""
        try:
            # Load pre-trained face detector
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Detect faces
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            return [(x, y, w, h) for (x, y, w, h) in faces]
            
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []
    
    @staticmethod
    def extract_face_region(image: np.ndarray, face_rect: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Extract face region from image"""
        try:
            x, y, w, h = face_rect
            
            # Add padding
            padding = 20
            x_start = max(0, x - padding)
            y_start = max(0, y - padding)
            x_end = min(image.shape[1], x + w + padding)
            y_end = min(image.shape[0], y + h + padding)
            
            face_region = image[y_start:y_end, x_start:x_end]
            
            # Resize to standard size
            face_region = cv2.resize(face_region, (128, 128))
            
            return face_region
            
        except Exception as e:
            logger.error(f"Error extracting face region: {e}")
            return None
    
    @staticmethod
    def save_image(image: np.ndarray, filepath: str) -> bool:
        """Save image to file"""
        try:
            cv2.imwrite(filepath, image)
            return True
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return False
    
    @staticmethod
    def load_image(filepath: str) -> Optional[np.ndarray]:
        """Load image from file"""
        try:
            image = cv2.imread(filepath)
            if image is not None:
                return image
            return None
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None
    
    @staticmethod
    def compare_images(image1: np.ndarray, image2: np.ndarray) -> float:
        """Compare two images and return similarity score"""
        try:
            # Ensure same size
            if image1.shape != image2.shape:
                image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))
            
            # Convert to grayscale if needed
            if len(image1.shape) == 3:
                image1_gray = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
                image2_gray = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
            else:
                image1_gray = image1
                image2_gray = image2
            
            # Calculate similarity using structural similarity
            from skimage.metrics import structural_similarity as ssim
            score = ssim(image1_gray, image2_gray)
            
            return max(0.0, min(score, 1.0))  # Ensure between 0 and 1
            
        except Exception as e:
            logger.error(f"Error comparing images: {e}")
            return 0.0
    
    @staticmethod
    def encode_image_to_base64(image: np.ndarray) -> Optional[str]:
        """Encode image to base64 string"""
        try:
            import base64
            ret, buffer = cv2.imencode('.jpg', image)
            if ret:
                return base64.b64encode(buffer).decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            return None
    
    @staticmethod
    def decode_base64_to_image(base64_string: str) -> Optional[np.ndarray]:
        """Decode base64 string to image"""
        try:
            import base64
            import numpy as np
            image_data = base64.b64decode(base64_string)
            np_array = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            logger.error(f"Error decoding base64 to image: {e}")
            return None