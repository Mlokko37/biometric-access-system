from flask_socketio import SocketIO, emit
from flask import request
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
socketio = SocketIO()

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('request_stats')
def handle_stats_request():
    """Send real-time stats to client"""
    from app import execute_query
    
    result = execute_query("""
        SELECT 
            (SELECT COUNT(*) FROM students WHERE is_active = TRUE) as students,
            (SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp) = CURRENT_DATE) as today,
            (SELECT COUNT(*) FROM devices WHERE status = 'online') as online_devices,
            (SELECT COUNT(*) FROM access_logs 
             WHERE timestamp >= NOW() - INTERVAL '1 hour') as last_hour
    """)
    
    if result and result[0]:
        emit('stats_update', {
            'students': result[0][0],
            'today_accesses': result[0][1],
            'online_devices': result[0][2],
            'last_hour': result[0][3],
            'timestamp': datetime.now().isoformat()
        })

def init_socketio(app):
    """Initialize SocketIO with app"""
    socketio.init_app(app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect():
        emit('connected', {'message': 'Connected to real-time updates'})
    
    return socketio