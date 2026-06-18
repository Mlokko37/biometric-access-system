"""
Access Point API Routes
Handles communication between access points and the main server
"""
import os
import json
import base64
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import cv2
import numpy as np

from src.services.face_recognition_service import get_face_recognition_service
from src.database.connection import execute_query, get_db_connection, release_db_connection, db_cursor
from src.database.connection import DB_CONFIG

logger = logging.getLogger(__name__)

access_point_api = Blueprint('access_point_api', __name__, url_prefix='/api/access-point')

def verify_api_key(api_key):
    """Verify access point API key"""
    if not api_key:
        return False, None
    
    try:
        result = execute_query(
            "SELECT id, name, status FROM access_points WHERE api_key = %s AND status = 'active'",
            (api_key,)
        )
        
        if result and len(result) > 0:
            point = result[0]
            return True, (point['id'], point['name'], point['status'])
        
        return False, None
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return False, None

@access_point_api.route('/verify', methods=['POST'])
def verify_face():
    """
    Endpoint for access point to verify a face
    Expects: {'api_key': 'xxx', 'image': 'base64_image_data'}
    Returns: {'success': True/False, 'student_id': id, 'name': name, 'confidence': 0.xx}
    """
    try:
        data = request.get_json()
        
        # Verify API key
        api_key = data.get('api_key')
        is_valid, point = verify_api_key(api_key)
        if not is_valid:
            return jsonify({'success': False, 'error': 'Invalid API key or access point inactive'}), 401
        
        # Get image data
        image_data = data.get('image')
        if not image_data:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        # Decode base64 image
        try:
            if image_data.startswith('data:image'):
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            
            # Convert to numpy array
            import io
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))
            image = np.array(image)
            
            # Convert to RGB if needed
            if len(image.shape) == 3 and image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            elif len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                
        except Exception as e:
            logger.error(f"Error decoding image: {e}")
            return jsonify({'success': False, 'error': 'Invalid image data'}), 400
        
        # Recognize face
        service = get_face_recognition_service()
        results = service.recognize_face(image)
        
        if not results:
            # Log denied access
            log_access_attempt(
                point_id=point[0],
                student_id=None,
                status='denied',
                confidence=0,
                verification_method='face_recognition'
            )
            return jsonify({'success': False, 'error': 'No matching face found'}), 404
        
        # Get best match
        best_match = results[0]
        student_id = best_match['student_id']
        confidence = best_match['confidence']
        
        # Log granted access
        log_access_attempt(
            point_id=point[0],
            student_id=student_id,
            status='granted',
            confidence=confidence,
            verification_method='face_recognition'
        )
        
        # Update access point statistics
        update_access_point_stats(point[0])
        
        return jsonify({
            'success': True,
            'student_id': student_id,
            'name': best_match['name'],
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in verify_face: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@access_point_api.route('/sync', methods=['GET'])
def sync_encodings():
    """
    Endpoint for access point to sync face encodings
    Expects: {'api_key': 'xxx'}
    Returns: {'success': True, 'encodings': [...]}
    """
    try:
        api_key = request.args.get('api_key')
        is_valid, point = verify_api_key(api_key)
        if not is_valid:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        
        service = get_face_recognition_service()
        students = service.get_all_students()
        
        return jsonify({
            'success': True,
            'count': len(students),
            'students': students,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in sync_encodings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@access_point_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for access points"""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.utcnow().isoformat()
    })

@access_point_api.route('/log', methods=['POST'])
def log_access():
    """Log access event from access point"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        is_valid, point = verify_api_key(api_key)
        if not is_valid:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        
        student_id = data.get('student_id')
        confidence = data.get('confidence', 0)
        status = data.get('status', 'granted')
        
        log_access_attempt(
            point_id=point[0],
            student_id=student_id,
            status=status,
            confidence=confidence,
            verification_method='face_recognition'
        )
        
        if status == 'granted':
            update_access_point_stats(point[0])
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error in log_access: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def log_access_attempt(point_id, student_id, status, confidence, verification_method):
    """Log access attempt to database"""
    try:
        execute_query(
            """INSERT INTO access_logs 
               (access_point_id, student_id, status, confidence_score, verification_method, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (point_id, student_id, status, confidence, verification_method, datetime.utcnow())
        )
        logger.info(f"Logged access: student_id={student_id}, status={status}")
        
    except Exception as e:
        logger.error(f"Error logging access attempt: {e}")

def update_access_point_stats(point_id):
    """Update access point statistics"""
    try:
        execute_query(
            """UPDATE access_points 
               SET total_accesses = total_accesses + 1,
                   last_activity = %s
               WHERE id = %s""",
            (datetime.utcnow(), point_id)
        )
        logger.info(f"Updated stats for access point {point_id}")
        
    except Exception as e:
        logger.error(f"Error updating access point stats: {e}")