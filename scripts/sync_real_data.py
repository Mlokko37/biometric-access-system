#!/usr/bin/env python3
"""
Sync existing real data from PostgreSQL to Firestore
Direct sync without relying on firestore_sync functions
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import execute_query
from src.database.firestore_sync import firestore_sync

def sync_all_students_direct():
    """Sync all students directly to Firestore"""
    print("\n[1] Syncing students...")
    
    # Initialize Firestore directly
    if not firestore_sync.init_firestore():
        print("  ❌ Firestore not connected")
        return 0
    
    if not firestore_sync.db:
        print("  ❌ Firestore database not available")
        return 0
    
    try:
        students = execute_query("""
            SELECT student_id, registration_number, first_name, last_name, 
                   email, phone, course, year_of_study, is_active
            FROM students
        """)
        
        if not students:
            print("  No students found in database")
            return 0
        
        print(f"  Found {len(students)} students in database")
        
        count = 0
        for student in students:
            try:
                # Convert all values to strings safely
                student_id = student.get('student_id')
                if student_id is None:
                    continue
                
                # Convert to string
                student_id_str = str(student_id)
                
                # Get values as strings
                first_name = student.get('first_name')
                if first_name is None:
                    first_name = ''
                first_name = str(first_name)
                
                last_name = student.get('last_name')
                if last_name is None:
                    last_name = ''
                last_name = str(last_name)
                
                registration_number = student.get('registration_number')
                if registration_number is None:
                    registration_number = ''
                registration_number = str(registration_number)
                
                email = student.get('email')
                if email is None:
                    email = ''
                email = str(email)
                
                phone = student.get('phone')
                if phone is None:
                    phone = ''
                phone = str(phone)
                
                course = student.get('course')
                if course is None:
                    course = ''
                course = str(course)
                
                year_of_study = student.get('year_of_study')
                if year_of_study is None:
                    year_of_study = 0
                year_of_study = int(year_of_study)
                
                is_active = student.get('is_active')
                if is_active is None:
                    is_active = True
                is_active = bool(is_active)
                
                # Build the data for Firestore
                data = {
                    'student_id': student_id_str,
                    'registration_number': registration_number,
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': f"{first_name} {last_name}".strip(),
                    'email': email,
                    'phone': phone,
                    'course': course,
                    'year_of_study': year_of_study,
                    'is_active': is_active,
                    'synced_at': datetime.now().isoformat()
                }
                
                # Direct Firestore save
                firestore_sync.db.collection('students').document(student_id_str).set(data)
                count += 1
                print(f"  ✓ #{student_id} - {first_name} {last_name} ({registration_number})")
                
            except Exception as e:
                print(f"  ✗ Error syncing student: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"  Total synced: {count} students")
        return count
        
    except Exception as e:
        print(f"  ✗ Error querying students: {e}")
        return 0

def sync_all_admins():
    """Sync all admins from PostgreSQL to Firestore"""
    print("\n[2] Syncing administrators...")
    
    try:
        admins = execute_query("""
            SELECT admin_id, username, full_name, email, role, is_active
            FROM administrators
        """)
        
        if not admins:
            print("  No admins found in database")
            return 0
        
        print(f"  Found {len(admins)} administrators in database")
        
        count = 0
        for admin in admins:
            try:
                admin_id = admin.get('admin_id')
                if admin_id is None:
                    continue
                
                admin_id_str = str(admin_id)
                
                username = admin.get('username')
                if username is None:
                    username = ''
                username = str(username)
                
                full_name = admin.get('full_name')
                if full_name is None:
                    full_name = ''
                full_name = str(full_name)
                
                email = admin.get('email')
                if email is None:
                    email = ''
                email = str(email)
                
                role = admin.get('role')
                if role is None:
                    role = 'staff'
                role = str(role)
                
                is_active = admin.get('is_active')
                if is_active is None:
                    is_active = True
                is_active = bool(is_active)
                
                data = {
                    'admin_id': admin_id_str,
                    'username': username,
                    'full_name': full_name,
                    'email': email,
                    'role': role,
                    'is_active': is_active,
                    'synced_at': datetime.now().isoformat()
                }
                
                firestore_sync.db.collection('administrators').document(admin_id_str).set(data)
                count += 1
                print(f"  ✓ {username} ({role})")
                
            except Exception as e:
                print(f"  ✗ Error syncing admin: {e}")
        
        print(f"  Total synced: {count} administrators")
        return count
        
    except Exception as e:
        print(f"  ✗ Error querying admins: {e}")
        return 0

def sync_recent_access_logs():
    """Sync recent access logs to Firestore"""
    print("\n[3] Syncing recent access logs...")
    
    try:
        logs = execute_query("""
            SELECT student_id, access_point, verification_method, 
                   verification_result, match_score, timestamp
            FROM access_logs
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        if not logs:
            print("  No access logs found in database")
            return 0
        
        print(f"  Found {len(logs)} access logs in database")
        
        count = 0
        for log in logs:
            try:
                student_id = log.get('student_id')
                if student_id is None:
                    continue
                
                # Get student name
                student_info = execute_query(
                    "SELECT first_name, last_name, registration_number FROM students WHERE student_id = %s",
                    (student_id,)
                )
                
                student_name = "Unknown"
                registration_number = ""
                if student_info and len(student_info) > 0:
                    student = student_info[0]
                    first_name = student.get('first_name', '') or ''
                    last_name = student.get('last_name', '') or ''
                    student_name = f"{first_name} {last_name}".strip() or "Unknown"
                    registration_number = student.get('registration_number', '') or ''
                
                data = {
                    'student_id': str(student_id),
                    'student_name': str(student_name),
                    'registration_number': str(registration_number),
                    'access_point': str(log.get('access_point', '')),
                    'verification_method': str(log.get('verification_method', '')),
                    'verification_result': str(log.get('verification_result', '')),
                    'match_score': float(log.get('match_score', 0)),
                    'timestamp': log.get('timestamp', datetime.now()).isoformat() if log.get('timestamp') else datetime.now().isoformat()
                }
                
                firestore_sync.db.collection('access_logs').add(data)
                count += 1
                
            except Exception as e:
                print(f"  ✗ Error syncing log: {e}")
        
        print(f"  Total synced: {count} access logs")
        return count
        
    except Exception as e:
        print(f"  ✗ Error querying access logs: {e}")
        return 0

def main():
    print("=" * 60)
    print("SYNC REAL DATA TO FIRESTORE")
    print("=" * 60)
    
    # Initialize Firestore
    print("\nInitializing Firestore...")
    if not firestore_sync.init_firestore():
        print("❌ Failed to connect to Firestore")
        return
    
    if not firestore_sync.db:
        print("❌ Firestore database not available")
        return
    
    print("✓ Firestore connected\n")
    
    # Sync data
    students = sync_all_students_direct()
    admins = sync_all_admins()
    logs = sync_recent_access_logs()
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   Students: {students}")
    print(f"   Administrators: {admins}")
    print(f"   Access Logs: {logs}")
    
    if students > 0:
        print("\n✅ Your real data is now in Firestore!")
        print("\nView it at: https://console.firebase.google.com/")
        print("Go to Firestore Database → View your collections")

if __name__ == "__main__":
    main()