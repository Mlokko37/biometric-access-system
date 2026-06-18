import os
import sys
import logging
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import base64
import hashlib
import psycopg2
import psycopg2.extras
import serial
import time
import struct

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import execute_query, get_db_connection
from enrollment.biometric_processor import BiometricProcessor
from enrollment.template_manager import TemplateManager
from src.hardware.device_service import device_service

logger = logging.getLogger(__name__)

class EnrollmentManager:
    """Manages the complete student enrollment process with real hardware."""
    
    def __init__(self):
        """Initialize enrollment manager with real hardware only."""
        self.student_data = {}
        self.fingerprint_templates = []
        self.facial_templates = []
        self.biometric_processor = BiometricProcessor()
        self.template_manager = TemplateManager()
        
    def start_enrollment(self, access_point: str = "Enrollment Station") -> bool:
        """Start the enrollment process with real hardware."""
        logger.info(f"Starting enrollment process at {access_point}")
        
        print("\n" + "=" * 60)
        print("STUDENT ENROLLMENT MODULE - REAL HARDWARE MODE")
        print("=" * 60)
        
        try:
            # Step 1: Collect student information
            if not self.collect_student_info():
                logger.error("Student information collection failed")
                return False
            
            # Step 2: Capture fingerprint biometrics (REAL SCANNER)
            fingerprint_success = self.capture_fingerprint()
            if not fingerprint_success:
                print("\n[ERROR] Fingerprint capture failed.")
                retry = input("Would you like to retry fingerprint capture? (y/n): ").strip().lower()
                if retry in ['y', 'yes']:
                    return self.start_enrollment(access_point)
                print("[WARN] Continuing without fingerprint data...")
            
            # Step 3: Capture facial biometrics (REAL CAMERA)
            facial_success = self.capture_facial()
            if not facial_success:
                print("\n[ERROR] Facial capture failed.")
                retry = input("Would you like to retry facial capture? (y/n): ").strip().lower()
                if retry in ['y', 'yes']:
                    return self.start_enrollment(access_point)
                print("[WARN] Continuing without facial data...")
            
            # Step 4: Validate at least one biometric captured
            if not self.fingerprint_templates and not self.facial_templates:
                logger.error("No biometric data captured")
                print("\n[ERROR] Enrollment failed: No biometric data captured")
                print("Please ensure your fingerprint scanner and camera are properly connected.")
                return False
            
            # Step 5: Save to database
            if self.save_to_database():
                student_name = f"{self.student_data.get('first_name', '')} {self.student_data.get('last_name', '')}"
                logger.info(f"Student enrolled successfully: {self.student_data.get('registration_number')}")
                print(f"\n[SUCCESS] Student {student_name} enrolled successfully!")
                
                # Print summary
                self.print_enrollment_summary()
                return True
            else:
                logger.error("Failed to save enrollment data")
                return False
                
        except KeyboardInterrupt:
            logger.info("Enrollment cancelled by user")
            print("\n[WARN] Enrollment cancelled")
            return False
        except Exception as e:
            logger.error(f"Enrollment error: {str(e)}", exc_info=True)
            print(f"\n[ERROR] Enrollment error: {str(e)}")
            return False
    
    def collect_student_info(self) -> bool:
        """Collect student demographic information."""
        print("\n[1/4] STUDENT INFORMATION")
        print("-" * 40)
        
        try:
            self.student_data = {}
            
            # Get required information
            while True:
                reg_no = input("Registration Number: ").strip().upper()
                if not reg_no:
                    print("[ERROR] Registration number is required")
                    continue
                
                # Check if already exists
                if self.check_student_exists(reg_no):
                    print(f"[WARN] Student with registration {reg_no} already exists")
                    overwrite = input("Overwrite existing record? (y/n): ").strip().lower()
                    if overwrite not in ['y', 'yes']:
                        continue
                break
            
            self.student_data['registration_number'] = reg_no
            self.student_data['first_name'] = input("First Name: ").strip().title()
            self.student_data['last_name'] = input("Last Name: ").strip().title()
            self.student_data['email'] = input("Email (optional): ").strip().lower()
            self.student_data['phone'] = input("Phone Number (optional): ").strip()
            self.student_data['course'] = input("Course/Program: ").strip().upper()
            
            # Validate year of study
            while True:
                year_input = input("Year of Study (1-6): ").strip()
                if year_input.isdigit() and 1 <= int(year_input) <= 6:
                    self.student_data['year_of_study'] = int(year_input)
                    break
                else:
                    print("[ERROR] Please enter a valid year (1-6)")
            
            # Confirm information
            print("\n" + "-" * 40)
            print("PLEASE CONFIRM INFORMATION:")
            print(f"Registration: {self.student_data['registration_number']}")
            print(f"Name: {self.student_data['first_name']} {self.student_data['last_name']}")
            print(f"Email: {self.student_data.get('email', 'N/A')}")
            print(f"Phone: {self.student_data.get('phone', 'N/A')}")
            print(f"Course: {self.student_data['course']}, Year: {self.student_data['year_of_study']}")
            
            confirm = input("\nIs this information correct? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("[WARN] Please restart enrollment with correct information")
                return False
            
            logger.info(f"Student info collected: {self.student_data['registration_number']}")
            return True
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error collecting student info: {str(e)}")
            return False
    
    def check_student_exists(self, registration_number: str) -> bool:
        """Check if student already exists in database."""
        try:
            result = execute_query(
                "SELECT student_id FROM students WHERE registration_number = %s",
                (registration_number,)
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking student: {e}")
            return False
    
    def capture_fingerprint(self) -> bool:
        """Capture fingerprint biometric data from real scanner."""
        print("\n[2/4] FINGERPRINT CAPTURE - REAL SCANNER")
        print("-" * 40)
        
        try:
            # Get fingerprint scanner configuration
            scanner_port = os.getenv('FINGERPRINT_PORT', '/dev/ttyUSB0')
            scanner_baudrate = int(os.getenv('FINGERPRINT_BAUDRATE', '57600'))
            
            print(f"Initializing fingerprint scanner on {scanner_port}...")
            
            # Initialize real fingerprint scanner
            from hardware.fingerprint_scanner import FingerprintScannerReal
            
            scanner = FingerprintScannerReal(
                port=scanner_port,
                baudrate=scanner_baudrate
            )
            
            if not scanner.connect():
                print("[ERROR] Failed to connect to fingerprint scanner")
                print("Please check:")
                print("  1. Scanner is connected to USB port")
                print("  2. Correct port is configured in .env file")
                print("  3. Scanner drivers are installed")
                print("  4. You have permission to access the serial port")
                return False
            
            print("[OK] Fingerprint scanner connected")
            
            # Capture multiple samples
            samples = []
            required_samples = 3
            
            print(f"\nPlease place your finger on the scanner")
            print(f"We will capture {required_samples} samples for better accuracy")
            
            for i in range(1, required_samples + 1):
                print(f"\nSample {i}/{required_samples}:")
                input("Press ENTER when finger is placed on scanner...")
                
                # Capture fingerprint
                result = scanner.capture_fingerprint(timeout=10)
                
                if result and result.get('success'):
                    template_data = result.get('template')
                    quality = result.get('quality', 0)
                    
                    if template_data and quality >= 50:
                        # Validate quality
                        is_valid, quality_score, metrics = self.biometric_processor.validate_fingerprint_template(
                            template_data
                        )
                        
                        if is_valid:
                            samples.append({
                                'template': template_data,
                                'quality': quality_score,
                                'metrics': metrics
                            })
                            print(f"[OK] Sample {i} captured successfully (Quality: {quality_score:.1f}%)")
                        else:
                            print(f"[ERROR] Sample quality too low ({quality_score:.1f}%). Please try again.")
                            i -= 1  # Retry this sample
                    else:
                        print(f"[ERROR] Failed to capture quality sample. Quality: {quality}%")
                        i -= 1
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No response'
                    print(f"[ERROR] Capture failed: {error_msg}")
                    retry = input("Retry this sample? (y/n): ").strip().lower()
                    if retry not in ['y', 'yes']:
                        return False
            
            scanner.disconnect()
            
            if len(samples) >= 1:
                self.fingerprint_templates = samples
                avg_quality = sum(s['quality'] for s in samples) / len(samples)
                print(f"\n[SUCCESS] {len(samples)} fingerprint samples captured")
                print(f"   Average quality: {avg_quality:.1f}%")
                return True
            else:
                print("[ERROR] No valid fingerprint samples captured")
                return False
                
        except ImportError as e:
            logger.error(f"Fingerprint scanner import error: {e}")
            print("[ERROR] Fingerprint scanner driver not available")
            print("Please install required dependencies: pip install pyserial")
            return False
        except Exception as e:
            logger.error(f"Fingerprint capture error: {str(e)}")
            print(f"[ERROR] Fingerprint capture error: {str(e)}")
            return False
    
    def capture_facial(self) -> bool:
        """Capture facial biometric data from real camera."""
        print("\n[3/4] FACIAL RECOGNITION CAPTURE - REAL CAMERA")
        print("-" * 40)
        
        try:
            # Get camera configuration
            camera_index = int(os.getenv('CAMERA_INDEX', 0))
            
            print(f"Initializing camera (index {camera_index})...")
            
            # Initialize real camera
            cap = cv2.VideoCapture(camera_index)
            
            if not cap.isOpened():
                print("[ERROR] Cannot open camera")
                print("Please check:")
                print("  1. Camera is connected")
                print("  2. Camera drivers are installed")
                print("  3. Camera is not in use by another application")
                return False
            
            print("[OK] Camera initialized")
            
            # Set camera properties for better quality
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Warm up camera
            for _ in range(5):
                cap.read()
            
            samples = []
            angles = ['Front', 'Left Profile', 'Right Profile', 'Smiling']
            
            # Create window for capture
            window_name = 'Facial Capture - Real Camera'
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 800, 600)
            
            # Load face cascade
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            for angle in angles:
                print(f"\n{angle} view:")
                print("Position yourself and press SPACE to capture")
                print("Press ESC to skip this angle")
                
                capture_success = False
                while not capture_success:
                    ret, frame = cap.read()
                    if not ret:
                        print("[ERROR] Failed to grab frame")
                        break
                    
                    # Detect faces
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(
                        gray, 
                        scaleFactor=1.1, 
                        minNeighbors=5, 
                        minSize=(100, 100)
                    )
                    
                    # Prepare display frame
                    display = frame.copy()
                    
                    if len(faces) > 0:
                        # Use the largest face
                        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                        x, y, w, h = faces[0]
                        
                        # Draw face rectangle
                        cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(display, "Face Detected", (x, y-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        
                        # Calculate face quality metrics
                        face_roi = gray[y:y+h, x:x+w]
                        if face_roi.size > 0:
                            sharpness = cv2.Laplacian(face_roi, cv2.CV_64F).var()
                            quality = min(100, sharpness / 10)
                            
                            # Display quality
                            quality_color = (0, 255, 0) if quality > 50 else (0, 165, 255) if quality > 30 else (0, 0, 255)
                            cv2.putText(display, f"Quality: {quality:.1f}%", (x, y+h+25),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, quality_color, 2)
                    
                    # Display instructions
                    cv2.putText(display, f"Angle: {angle}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(display, "SPACE: Capture  ESC: Skip", (10, 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # Show face count
                    face_count = len(faces)
                    cv2.putText(display, f"Faces Detected: {face_count}", (10, 90),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    
                    cv2.imshow(window_name, display)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == 32:  # SPACE
                        if len(faces) > 0:
                            # Validate face quality
                            is_valid, quality, metrics = self.biometric_processor.validate_facial_template(frame)
                            
                            if is_valid and quality >= 50:
                                # Encode image as JPEG
                                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                                img_bytes = buffer.tobytes()
                                
                                samples.append({
                                    'image': img_bytes,
                                    'quality': quality,
                                    'angle': angle,
                                    'metrics': metrics
                                })
                                
                                print(f"[OK] {angle} captured (Quality: {quality:.1f}%)")
                                capture_success = True
                            else:
                                print(f"[ERROR] Poor quality ({quality:.1f}%). Please try again.")
                                print("   Tips for better quality:")
                                print("   - Ensure good lighting")
                                print("   - Face the camera directly")
                                print("   - Remove glasses or hat if possible")
                                print("   - Stay still during capture")
                        else:
                            print("[ERROR] No face detected. Please ensure your face is visible in frame.")
                            
                    elif key == 27:  # ESC
                        print(f"⏭️ Skipping {angle} view")
                        capture_success = True
            
            # Clean up
            cap.release()
            cv2.destroyAllWindows()
            
            if len(samples) >= 1:
                self.facial_templates = samples
                avg_quality = sum(s['quality'] for s in samples) / len(samples)
                print(f"\n[SUCCESS] {len(samples)} facial images captured")
                print(f"   Average quality: {avg_quality:.1f}%")
                return True
            else:
                print("[ERROR] No facial images were captured successfully")
                return False
                
        except Exception as e:
            logger.error(f"Facial capture error: {str(e)}")
            print(f"[ERROR] Facial capture error: {str(e)}")
            if 'cap' in locals():
                cap.release()
            cv2.destroyAllWindows()
            return False
    
    def save_to_database(self) -> bool:
        """Save enrollment data to PostgreSQL database."""
        try:
            print("\n[4/4] SAVING TO DATABASE")
            print("-" * 40)
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if student already exists
            cur.execute(
                "SELECT student_id FROM students WHERE registration_number = %s",
                (self.student_data['registration_number'],)
            )
            existing = cur.fetchone()
            
            if existing:
                print(f"[WARN] Student {self.student_data['registration_number']} already exists")
                overwrite = input("Update existing record? (y/n): ").strip().lower()
                if overwrite in ['y', 'yes']:
                    # Update existing record
                    student_id = existing[0]
                    cur.execute("""
                        UPDATE students SET
                            first_name = %s,
                            last_name = %s,
                            email = %s,
                            phone = %s,
                            course = %s,
                            year_of_study = %s,
                            updated_at = NOW()
                        WHERE student_id = %s
                    """, (
                        self.student_data['first_name'],
                        self.student_data['last_name'],
                        self.student_data.get('email'),
                        self.student_data.get('phone'),
                        self.student_data['course'],
                        self.student_data['year_of_study'],
                        student_id
                    ))
                    print(f"[OK] Student record updated")
                else:
                    conn.close()
                    return False
            else:
                # Insert new student
                cur.execute("""
                    INSERT INTO students (
                        registration_number, first_name, last_name, 
                        email, phone, course, year_of_study, is_active, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
                    RETURNING student_id
                """, (
                    self.student_data['registration_number'],
                    self.student_data['first_name'],
                    self.student_data['last_name'],
                    self.student_data.get('email'),
                    self.student_data.get('phone'),
                    self.student_data['course'],
                    self.student_data['year_of_study']
                ))
                
                student_id = cur.fetchone()[0]
                print(f"[OK] New student record created")
            
            # Save fingerprint templates
            if self.fingerprint_templates:
                for i, fp_data in enumerate(self.fingerprint_templates):
                    template_bytes = fp_data['template']
                    template_hash = hashlib.sha256(template_bytes).hexdigest()
                    
                    cur.execute("""
                        INSERT INTO biometric_templates (
                            student_id, template_type, template_data, template_hash,
                            quality_score, created_at
                        ) VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (
                        student_id, 'fingerprint', psycopg2.Binary(template_bytes),
                        template_hash, fp_data['quality']
                    ))
                    
                    # Also save to file system
                    self.template_manager.save_fingerprint_template(
                        student_id, template_bytes,
                        {'quality': fp_data['quality'], 'index': i}
                    )
                
                print(f"[OK] {len(self.fingerprint_templates)} fingerprint templates saved")
            
            # Save facial templates
            if self.facial_templates:
                for i, face_data in enumerate(self.facial_templates):
                    template_hash = hashlib.sha256(face_data['image']).hexdigest()
                    
                    cur.execute("""
                        INSERT INTO biometric_templates (
                            student_id, template_type, template_data, template_hash,
                            quality_score, created_at
                        ) VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (
                        student_id, 'facial', psycopg2.Binary(face_data['image']),
                        template_hash, face_data['quality']
                    ))
                    
                    # Also save to file system
                    self.template_manager.save_facial_template(
                        student_id, face_data['image'],
                        {'quality': face_data['quality'], 'angle': face_data.get('angle', 'front')}
                    )
                
                print(f"[OK] {len(self.facial_templates)} facial templates saved")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Student data saved to database. Student ID: {student_id}")
            return True
            
        except Exception as e:
            logger.error(f"Database save error: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            print(f"[ERROR] Database error: {str(e)}")
            return False
    
    def print_enrollment_summary(self):
        """Print enrollment summary."""
        print("\n" + "=" * 60)
        print("ENROLLMENT SUMMARY")
        print("=" * 60)
        
        print(f"\nStudent Information:")
        print(f"  Name: {self.student_data['first_name']} {self.student_data['last_name']}")
        print(f"  Registration: {self.student_data['registration_number']}")
        print(f"  Course: {self.student_data['course']} (Year {self.student_data['year_of_study']})")
        
        if self.fingerprint_templates:
            avg_fp_quality = sum(f['quality'] for f in self.fingerprint_templates) / len(self.fingerprint_templates)
            print(f"\nFingerprint Templates: {len(self.fingerprint_templates)}")
            print(f"  Average Quality: {avg_fp_quality:.1f}%")
        
        if self.facial_templates:
            avg_face_quality = sum(f['quality'] for f in self.facial_templates) / len(self.facial_templates)
            print(f"\nFacial Templates: {len(self.facial_templates)}")
            print(f"  Average Quality: {avg_face_quality:.1f}%")
        
        print("\n" + "=" * 60)


def start_enrollment():
    """Start the enrollment process with real hardware."""
    manager = EnrollmentManager()
    return manager.start_enrollment()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Enrollment Module - REAL HARDWARE MODE")
    print("======================================")
    print("This system uses:")
    print("  - Real fingerprint scanner (USB/Serial)")
    print("  - Real camera for facial recognition")
    print()
    
    if start_enrollment():
        print("\n[SUCCESS] Enrollment completed successfully")
    else:
        print("\n[ERROR] Enrollment failed")