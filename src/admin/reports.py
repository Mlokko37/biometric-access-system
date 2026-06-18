from flask import Blueprint, render_template, jsonify, request, send_file, Response
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import csv
import io
import json
import logging
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from src.database.connection import execute_query

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def reports_home():
    """Reports home page."""
    return render_template('reports.html', user=current_user)

@reports_bp.route('/generate', methods=['POST'])
@login_required
def generate_report():
    """Generate a report based on criteria from real database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        report_type = data.get('type', 'daily')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        access_point = data.get('access_point', '')
        student_id = data.get('student_id', '')
        access_type = data.get('access_type', '')
        
        # Build base query
        if report_type == 'daily':
            query = """
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as total,
                    SUM(CASE WHEN verification_result = 'GRANTED' THEN 1 ELSE 0 END) as granted,
                    SUM(CASE WHEN verification_result = 'DENIED' THEN 1 ELSE 0 END) as denied
                FROM access_logs
                WHERE 1=1
            """
            group_by = " GROUP BY DATE(timestamp) ORDER BY date DESC"
            
        elif report_type == 'hourly':
            query = """
                SELECT 
                    EXTRACT(HOUR FROM timestamp) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN verification_result = 'GRANTED' THEN 1 ELSE 0 END) as granted,
                    SUM(CASE WHEN verification_result = 'DENIED' THEN 1 ELSE 0 END) as denied
                FROM access_logs
                WHERE 1=1
            """
            group_by = " GROUP BY EXTRACT(HOUR FROM timestamp) ORDER BY hour"
        
        elif report_type == 'student':
            query = """
                SELECT 
                    s.student_id,
                    s.registration_number,
                    s.first_name || ' ' || s.last_name as student_name,
                    s.course,
                    COUNT(al.log_id) as total_accesses,
                    SUM(CASE WHEN al.verification_result = 'GRANTED' THEN 1 ELSE 0 END) as successful_accesses,
                    COALESCE(AVG(al.match_score), 0) as avg_match_score,
                    MAX(al.timestamp) as last_access
                FROM students s
                LEFT JOIN access_logs al ON s.student_id = al.student_id
                WHERE s.is_active = TRUE
            """
            group_by = " GROUP BY s.student_id, s.registration_number, s.first_name, s.last_name, s.course ORDER BY student_name"
        
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Add filters
        params = []
        where_clauses = []
        
        if date_from:
            where_clauses.append("timestamp >= %s")
            params.append(date_from)
        
        if date_to:
            where_clauses.append("timestamp <= %s")
            params.append(date_to + " 23:59:59")
        
        if access_point and report_type != 'student':
            where_clauses.append("access_point = %s")
            params.append(access_point)
        
        if student_id and report_type != 'student':
            where_clauses.append("student_id = %s")
            params.append(student_id)
        
        if access_type and report_type != 'student':
            where_clauses.append("verification_result = %s")
            params.append(access_type)
        
        if where_clauses:
            query += " AND " + " AND ".join(where_clauses)
        
        query += group_by
        
        # Execute query - Fixed: Always pass a tuple, never None
        if params:
            results = execute_query(query, tuple(params))
        else:
            results = execute_query(query)  # Assuming execute_query can handle no params
        
        if not results:
            return jsonify({
                'success': True,
                'message': 'No data found for the selected criteria',
                'data': []
            })
        
        # Format results
        formatted_results = []
        if report_type == 'daily':
            for row in results:
                formatted_results.append({
                    'date': row[0].strftime('%Y-%m-%d') if row[0] else '',
                    'total': row[1],
                    'granted': row[2],
                    'denied': row[3],
                    'success_rate': round((row[2] / row[1] * 100) if row[1] > 0 else 0, 2)
                })
        elif report_type == 'hourly':
            for row in results:
                formatted_results.append({
                    'hour': f"{int(row[0]):02d}:00",
                    'total': row[1],
                    'granted': row[2],
                    'denied': row[3]
                })
        elif report_type == 'student':
            for row in results:
                formatted_results.append({
                    'student_id': row[0],
                    'registration_number': row[1],
                    'student_name': row[2],
                    'course': row[3],
                    'total_accesses': row[4],
                    'successful_accesses': row[5],
                    'avg_match_score': round(float(row[6]), 2) if row[6] else 0,
                    'last_access': row[7].strftime('%Y-%m-%d %H:%M') if row[7] else 'Never'
                })
        
        return jsonify({
            'success': True,
            'report_type': report_type,
            'data': formatted_results,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/export/<format>', methods=['POST'])
@login_required
def export_report(format):
    """Export report in specified format."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        report_data = data.get('data', [])
        report_type = data.get('report_type', 'custom')
        filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if format == 'csv':
            # Create CSV
            output = io.StringIO()
            
            if report_data:
                # Get fieldnames from first item
                fieldnames = report_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(report_data)
            
            output.seek(0)
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}.csv'}
            )
        
        elif format == 'json':
            # Create JSON file
            return Response(
                json.dumps(report_data, indent=2, default=str),
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename={filename}.json'}
            )
        
        elif format == 'excel':
            # Create Excel file
            if not report_data:
                return jsonify({'error': 'No data to export'}), 400
            
            df = pd.DataFrame(report_data)
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Report', index=False)
            
            output.seek(0)
            
            return Response(
                output.getvalue(),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={'Content-Disposition': f'attachment; filename={filename}.xlsx'}
            )
        
        elif format == 'pdf':
            # Create PDF
            if not report_data:
                return jsonify({'error': 'No data to export'}), 400
            
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph(f"{report_type.title()} Report", styles['Title'])
            elements.append(title)
            
            # Add timestamp
            timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
            elements.append(timestamp)
            
            # Create table
            if report_data:
                # Headers
                headers = list(report_data[0].keys())
                table_data = [headers]
                
                # Data rows
                for row in report_data:
                    table_data.append([str(val) for val in row.values()])
                
                # Create table
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                elements.append(table)
            
            # Build PDF
            doc.build(elements)
            output.seek(0)
            
            return Response(
                output.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename={filename}.pdf'}
            )
        
        else:
            return jsonify({'error': f'Unsupported format: {format}'}), 400
    
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500