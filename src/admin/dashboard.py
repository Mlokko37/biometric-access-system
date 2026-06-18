from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import logging

from src.database.connection import execute_query

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def dashboard():
    """Main dashboard page with real data."""
    return render_template('dashboard.html', user=current_user)

@dashboard_bp.route('/realtime-data')
@login_required
def realtime_data():
    """Get real-time data from database for dashboard."""
    try:
        # Get today's access stats
        today = datetime.now().strftime('%Y-%m-%d')
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN verification_result = 'GRANTED' THEN 1 ELSE 0 END) as granted,
                SUM(CASE WHEN verification_result = 'DENIED' THEN 1 ELSE 0 END) as denied
            FROM access_logs 
            WHERE DATE(timestamp) = %s
        """
        
        result = execute_query(query, (today,))
        today_stats = {
            'total': result[0][0] if result else 0,
            'granted': result[0][1] if result and result[0][1] else 0,
            'denied': result[0][2] if result and result[0][2] else 0
        }
        
        # Get hourly data for last 24 hours
        hour_query = """
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                COUNT(*) as count
            FROM access_logs 
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY EXTRACT(HOUR FROM timestamp)
            ORDER BY hour
        """
        
        hourly_data = {}
        hour_results = execute_query(hour_query)
        if hour_results:
            for hour, count in hour_results:
                hourly_data[str(int(hour))] = count
        
        # Get recent access logs
        recent_query = """
            SELECT 
                al.timestamp,
                al.verification_method,
                al.verification_result,
                al.match_score,
                al.access_point,
                s.registration_number,
                s.first_name,
                s.last_name
            FROM access_logs al
            LEFT JOIN students s ON al.student_id = s.student_id
            ORDER BY al.timestamp DESC
            LIMIT 10
        """
        
        recent_logs = []
        recent_results = execute_query(recent_query)
        if recent_results:
            for row in recent_results:
                recent_logs.append({
                    'timestamp': row[0].isoformat() if row[0] else None,
                    'method': row[1],
                    'result': row[2],
                    'score': float(row[3]) if row[3] else None,
                    'access_point': row[4],
                    'registration': row[5],
                    'student_name': f"{row[6]} {row[7]}" if row[6] else "Unknown"
                })
        
        # Get system statistics
        stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM students WHERE is_active = TRUE) as total_students,
                (SELECT COUNT(*) FROM biometric_templates) as total_templates,
                (SELECT COUNT(*) FROM access_logs) as total_accesses,
                (SELECT COUNT(*) FROM devices WHERE status = 'online') as online_devices
        """
        
        stats_result = execute_query(stats_query)
        system_stats = {
            'total_students': stats_result[0][0] if stats_result else 0,
            'total_templates': stats_result[0][1] if stats_result else 0,
            'total_accesses': stats_result[0][2] if stats_result else 0,
            'online_devices': stats_result[0][3] if stats_result else 0
        }
        
        return jsonify({
            'success': True,
            'today_stats': today_stats,
            'hourly_data': hourly_data,
            'recent_logs': recent_logs,
            'system_stats': system_stats,
            'last_updated': datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error getting realtime data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/quick-stats')
@login_required
def quick_stats():
    """Get quick statistics for dashboard cards."""
    try:
        query = """
            SELECT 
                (SELECT COUNT(*) FROM access_logs 
                 WHERE DATE(timestamp) = CURRENT_DATE 
                 AND verification_result = 'GRANTED') as today_accesses,
                (SELECT COUNT(*) FROM access_logs 
                 WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days') as week_accesses,
                (SELECT COUNT(*) FROM students WHERE is_active = TRUE) as total_students,
                (SELECT COUNT(*) FROM devices WHERE status = 'online') as online_devices,
                (SELECT setting_value FROM system_settings 
                 WHERE setting_name = 'system_mode') as system_status
        """
        
        result = execute_query(query)
        
        if result and result[0]:
            return jsonify({
                'success': True,
                'today_accesses': result[0][0] or 0,
                'week_accesses': result[0][1] or 0,
                'total_students': result[0][2] or 0,
                'online_devices': result[0][3] or 0,
                'system_status': result[0][4] or 'online'
            })
        
    except Exception as e:
        logger.error(f"Error getting quick stats: {e}")
        
    return jsonify({
        'success': False,
        'error': 'Could not fetch statistics'
    }), 500
    
@dashboard_bp.route('/access-points')
@login_required
def get_access_points():
    """Get list of access points for filtering."""
    try:
        result = execute_query(
            "SELECT DISTINCT access_point FROM access_logs WHERE access_point IS NOT NULL ORDER BY access_point"
        )
        
        access_points = [row[0] for row in result] if result else []
        
        return jsonify({
            'success': True,
            'access_points': access_points
        })
    
    except Exception as e:
        logger.error(f"Error getting access points: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500