"""
API Client - Communicates with the main server
"""
import requests
import json
import logging
import base64
import cv2
from typing import Optional, Dict, Any, List
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class APIClient:
    """Client for communicating with the main server"""
    
    def __init__(self, server_url: str, api_key: str, timeout: int = 10):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def verify_face(self, image, student_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Send face image to server for verification
        """
        try:
            # Convert image to base64
            _, buffer = cv2.imencode('.jpg', image)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            data = {
                'api_key': self.api_key,
                'image': image_base64,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if student_id:
                data['student_id'] = student_id
            
            response = self.session.post(
                f"{self.server_url}/verify",
                json=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Server returned {response.status_code}: {response.text}")
                return {'success': False, 'error': f"Server error: {response.status_code}"}
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return {'success': False, 'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            logger.error("Connection error")
            return {'success': False, 'error': 'Connection error'}
        except Exception as e:
            logger.error(f"Error in verify_face: {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_encodings(self) -> List[Dict[str, Any]]:
        """
        Sync face encodings from server
        """
        try:
            response = self.session.get(
                f"{self.server_url}/sync",
                params={'api_key': self.api_key},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('students', [])
                else:
                    logger.error(f"Sync failed: {data.get('error', 'Unknown error')}")
                    return []
            else:
                logger.error(f"Sync failed with status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error syncing encodings: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check if server is reachable"""
        try:
            response = self.session.get(
                f"{self.server_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def log_access(self, student_id: int, confidence: float, status: str = 'granted'):
        """
        Log access event to server
        """
        try:
            data = {
                'api_key': self.api_key,
                'student_id': student_id,
                'confidence': confidence,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.session.post(
                f"{self.server_url}/log",
                json=data,
                timeout=self.timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error logging access: {e}")
            return False