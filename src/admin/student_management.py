from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime
import logging

from src.database.connection import execute_query
from src.verification.logging_manager import LoggingManager

logger = logging.getLogger(__name__)
students_bp = Blueprint('students', __name__, url_prefix='/students')

@students_bp.route('/')
@login_required
def students_list():
    """Display list of students."""
    return render_template('students.html', user=current_user)

@students_bp.route('/api/list')
@login_required
def get_students():
    """Get list of students from real database (API endpoint)."""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        
        search = request.args.get('search', '')
        course_filter = request.args.get('course', '')
        year_filter = request.args.get('year', '')
        
        # Build base query
        query = """
            SELECT 
                s.student_id,
                s.registration_number,
                s.first_name,
                s.last_name,
                s.email,
                s.phone,
                s.course,
                s.year_of_study,
                s.created_at,
                s.is_active,
                COUNT(DISTINCT bt.template_id) as template_count,
                COUNT(DISTINCT al.log_id) as access_count
            FROM students s
            LEFT JOIN biometric_templates bt ON s.student_id = bt.student_id
            LEFT JOIN access_logs al ON s.student_id = al.student_id
            WHERE 1=1
        """
        
        params = []
        where_clauses = []
        
        if search:
            where_clauses.append("""
                (s.registration_number ILIKE %s OR 
                 s.first_name ILIKE %s OR 
                 s.last_name ILIKE %s OR 
                 s.email ILIKE %s)
            """)
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term, search_term])
        
        if course_filter and course_filter != 'all':
            where_clauses.append("s.course = %s")
            params.append(course_filter)
        
        if year_filter and year_filter != 'all':
            where_clauses.append("s.year_of_study = %s")
            params.append(int(year_filter))
        
        if where_clauses:
            query += " AND " + " AND ".join(where_clauses)
        
        query += " GROUP BY s.student_id ORDER BY s.registration_number"
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"
        count_result = execute_query(count_query, tuple(params) if params else ())
        total = count_result[0][0] if count_result else 0
        
        # Add pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        # Execute query
        results = execute_query(query, tuple(params) if params else ())
        
        students = []
        if results:
            for row in results:
                students.append({
                    'id': row[0],
                    'student_id': row[0],
                    'registration_number': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'email': row[4],
                    'phone': row[5],
                    'course': row[6],
                    'year_of_study': row[7],
                    'created_at': row[8].isoformat() if row[8] else None,
                    'is_active': bool(row[9]),
                    'template_count': row[10] or 0,
                    'access_count': row[11] or 0
                })
        
        return jsonify({
            'success': True,
            'students': students,
            'total': total,
            'page': page,
            'total_pages': (total + limit - 1) // limit
        })
    
    except Exception as e:
        logger.error(f"Error getting students: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@students_bp.route('/api/courses')
@login_required
def get_courses():
    """Get list of unique courses from database."""
    try:
        result = execute_query(
            "SELECT DISTINCT course FROM students WHERE course IS NOT NULL AND course != '' ORDER BY course"
        )
        
        courses = [row[0] for row in result] if result else []
        
        return jsonify({
            'success': True,
            'courses': courses
        })
    
    except Exception as e:
        logger.error(f"Error getting courses: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@students_bp.route('/api/<int:student_id>')
@login_required
def get_student(student_id):
    """Get student details from database."""
    try:
        # Get student info
        query = """
            SELECT 
                s.student_id,
                s.registration_number,
                s.first_name,
                s.last_name,
                s.email,
                s.phone,
                s.course,
                s.year_of_study,
                s.created_at,
                s.is_active,
                s.updated_at,
                COUNT(DISTINCT bt.template_id) as template_count,
                COUNT(DISTINCT al.log_id) as access_count
            FROM students s
            LEFT JOIN biometric_templates bt ON s.student_id = bt.student_id
            LEFT JOIN access_logs al ON s.student_id = al.student_id
            WHERE s.student_id = %s
            GROUP BY s.student_id
        """
        
        result = execute_query(query, (student_id,))
        
        if not result:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        row = result[0]
        student = {
            'id': row[0],
            'student_id': row[0],
            'registration_number': row[1],
            'first_name': row[2],
            'last_name': row[3],
            'email': row[4],
            'phone': row[5],
            'course': row[6],
            'year_of_study': row[7],
            'created_at': row[8].isoformat() if row[8] else None,
            'is_active': bool(row[9]),
            'updated_at': row[10].isoformat() if row[10] else None,
            'template_count': row[11] or 0,
            'access_count': row[12] or 0
        }
        
        # Get biometric templates
        template_query = """
            SELECT template_type, quality_score, created_at 
            FROM biometric_templates 
            WHERE student_id = %s
            ORDER BY created_at DESC
        """
        
        templates = []
        template_results = execute_query(template_query, (student_id,))
        if template_results:
            for template_row in template_results:
                templates.append({
                    'type': template_row[0],
                    'quality': float(template_row[1]) if template_row[1] else 0,
                    'created_at': template_row[2].isoformat() if template_row[2] else None
                })
        
        # Get recent access logs
        access_query = """
            SELECT 
                timestamp,
                verification_method,
                verification_result,
                match_score,
                access_point
            FROM access_logs 
            WHERE student_id = %s
            ORDER BY timestamp DESC
            LIMIT 10
        """
        
        access_logs = []
        access_results = execute_query(access_query, (student_id,))
        if access_results:
            for access_row in access_results:
                access_logs.append({
                    'timestamp': access_row[0].isoformat() if access_row[0] else None,
                    'method': access_row[1],
                    'result': access_row[2],
                    'score': float(access_row[3]) if access_row[3] else None,
                    'access_point': access_row[4]
                })
        
        return jsonify({
            'success': True,
            'student': student,
            'templates': templates,
            'access_logs': access_logs
        })
    
    except Exception as e:
        logger.error(f"Error getting student: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@students_bp.route('/api/update', methods=['POST'])
@login_required
def update_student():

    print(f"csrf token = {request.form.get('csrf_token')}")
    """Update student information in database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        student_id = data.get('student_id')
        if not student_id:
            return jsonify({'success': False, 'error': 'Student ID required'}), 400
        
        # Validate required fields
        required_fields = ['first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Update student
        query = """
            UPDATE students 
            SET first_name = %s,
                last_name = %s,
                email = %s,
                phone = %s,
                course = %s,
                year_of_study = %s,
                updated_at = NOW()
            WHERE student_id = %s
        """
        
        execute_query(query, (
            data['first_name'],
            data['last_name'],
            data.get('email', ''),
            data.get('phone', ''),
            data.get('course', ''),
            int(data['year_of_study']) if data.get('year_of_study') else None,
            student_id
        ))
        
        # Log the action
        logger.info(f"Student {student_id} updated by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Student updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@students_bp.route('/api/create', methods=['POST'])
@login_required
def create_student():
    """Create new student in database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['registration_number', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Check if registration number already exists
        check_query = "SELECT student_id FROM students WHERE registration_number = %s"
        existing = execute_query(check_query, (data['registration_number'],))
        
        if existing:
            return jsonify({'success': False, 'error': 'Registration number already exists'}), 400
        
        # Generate student_id if not provided
        student_id = data.get('student_id')
        if not student_id:
            import time
            student_id = f"STU{int(time.time())}"
        
        # Insert new student
        query = """
            INSERT INTO students 
            (student_id, registration_number, first_name, last_name, email, phone, course, year_of_study, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        execute_query(query, (
            student_id,
            data['registration_number'],
            data['first_name'],
            data['last_name'],
            data.get('email', ''),
            data.get('phone', ''),
            data.get('course', ''),
            int(data['year_of_study']) if data.get('year_of_study') else None,
            True
        ))
        
        logger.info(f"Student {student_id} created by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Student created successfully',
            'student_id': student_id
        })
    
    except Exception as e:
        logger.error(f"Error creating student: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@students_bp.route('/api/<int:student_id>/toggle-active', methods=['POST'])
@login_required
def toggle_active(student_id):
    """Toggle student active status in database."""
    try:
        # Get current status
        current_query = "SELECT is_active FROM students WHERE student_id = %s"
        current_result = execute_query(current_query, (student_id,))
        
        if not current_result:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        current_status = current_result[0][0]
        new_status = not current_status
        
        # Update status
        update_query = "UPDATE students SET is_active = %s, updated_at = NOW() WHERE student_id = %s"
        execute_query(update_query, (new_status, student_id))
        
        status_text = "activated" if new_status else "deactivated"
        logger.info(f"Student {student_id} {status_text} by {current_user.username}")
        
        return jsonify({
            'success': True,
            'message': f'Student {status_text} successfully',
            'is_active': new_status
        })
    
    except Exception as e:
        logger.error(f"Error toggling student status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500