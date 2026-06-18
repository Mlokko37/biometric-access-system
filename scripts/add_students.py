#!/usr/bin/env python3
"""
Add sample students to PostgreSQL and sync to Firestore
Fixed: Uses separate query to get the last inserted ID
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import execute_query
from src.database.firestore_sync import firestore_sync

# Sample students data with multiple courses
students = [
    # Computer Science
    {'registration_number': 'CS/0001/21', 'first_name': 'John', 'last_name': 'Doe', 'email': 'john.doe@kibabii.ac.ke', 'phone': '0712345678', 'course': 'COMPUTER SCIENCE', 'year_of_study': 4},
    {'registration_number': 'CS/0023/22', 'first_name': 'Jane', 'last_name': 'Smith', 'email': 'jane.smith@kibabii.ac.ke', 'phone': '0723456789', 'course': 'COMPUTER SCIENCE', 'year_of_study': 3},
    {'registration_number': 'CS/0056/23', 'first_name': 'Robert', 'last_name': 'Johnson', 'email': 'robert.johnson@kibabii.ac.ke', 'phone': '0734567890', 'course': 'COMPUTER SCIENCE', 'year_of_study': 2},
    
    # Information Technology
    {'registration_number': 'BIT/0001/21', 'first_name': 'Mary', 'last_name': 'Williams', 'email': 'mary.williams@kibabii.ac.ke', 'phone': '0745678901', 'course': 'BSc. Information Technology', 'year_of_study': 4},
    {'registration_number': 'BIT/0045/22', 'first_name': 'David', 'last_name': 'Brown', 'email': 'david.brown@kibabii.ac.ke', 'phone': '0756789012', 'course': 'BSc. Information Technology', 'year_of_study': 3},
    {'registration_number': 'BIT/0089/23', 'first_name': 'Sarah', 'last_name': 'Davis', 'email': 'sarah.davis@kibabii.ac.ke', 'phone': '0767890123', 'course': 'BSc. Information Technology', 'year_of_study': 2},
    
    # Electrical Engineering
    {'registration_number': 'EE/0003/21', 'first_name': 'Michael', 'last_name': 'Miller', 'email': 'michael.miller@kibabii.ac.ke', 'phone': '0778901234', 'course': 'ELECTRICAL ENGINEERING', 'year_of_study': 4},
    {'registration_number': 'EE/0012/22', 'first_name': 'Patricia', 'last_name': 'Wilson', 'email': 'patricia.wilson@kibabii.ac.ke', 'phone': '0789012345', 'course': 'ELECTRICAL ENGINEERING', 'year_of_study': 3},
    
    # Mechanical Engineering
    {'registration_number': 'ME/0005/21', 'first_name': 'James', 'last_name': 'Moore', 'email': 'james.moore@kibabii.ac.ke', 'phone': '0790123456', 'course': 'MECHANICAL ENGINEERING', 'year_of_study': 4},
    {'registration_number': 'ME/0018/22', 'first_name': 'Linda', 'last_name': 'Taylor', 'email': 'linda.taylor@kibabii.ac.ke', 'phone': '0701234567', 'course': 'MECHANICAL ENGINEERING', 'year_of_study': 3},
    
    # Business Administration
    {'registration_number': 'BA/0007/21', 'first_name': 'William', 'last_name': 'Anderson', 'email': 'william.anderson@kibabii.ac.ke', 'phone': '0712345680', 'course': 'BUSINESS ADMINISTRATION', 'year_of_study': 4},
    {'registration_number': 'BA/0021/22', 'first_name': 'Elizabeth', 'last_name': 'Thomas', 'email': 'elizabeth.thomas@kibabii.ac.ke', 'phone': '0723456791', 'course': 'BUSINESS ADMINISTRATION', 'year_of_study': 3},
    {'registration_number': 'BA/0034/23', 'first_name': 'Charles', 'last_name': 'Jackson', 'email': 'charles.jackson@kibabii.ac.ke', 'phone': '0734567802', 'course': 'BUSINESS ADMINISTRATION', 'year_of_study': 2},
    
    # Nursing
    {'registration_number': 'NUR/0002/21', 'first_name': 'Susan', 'last_name': 'White', 'email': 'susan.white@kibabii.ac.ke', 'phone': '0745678913', 'course': 'NURSING', 'year_of_study': 4},
    {'registration_number': 'NUR/0015/22', 'first_name': 'Paul', 'last_name': 'Harris', 'email': 'paul.harris@kibabii.ac.ke', 'phone': '0756789024', 'course': 'NURSING', 'year_of_study': 3},
    
    # Education
    {'registration_number': 'EDU/0004/21', 'first_name': 'Margaret', 'last_name': 'Martin', 'email': 'margaret.martin@kibabii.ac.ke', 'phone': '0767890135', 'course': 'EDUCATION', 'year_of_study': 4},
    {'registration_number': 'EDU/0019/22', 'first_name': 'Thomas', 'last_name': 'Thompson', 'email': 'thomas.thompson@kibabii.ac.ke', 'phone': '0778901246', 'course': 'EDUCATION', 'year_of_study': 3},
    
    # Law
    {'registration_number': 'LAW/0006/21', 'first_name': 'Jennifer', 'last_name': 'Garcia', 'email': 'jennifer.garcia@kibabii.ac.ke', 'phone': '0789012357', 'course': 'LAW', 'year_of_study': 4},
    {'registration_number': 'LAW/0014/22', 'first_name': 'Daniel', 'last_name': 'Martinez', 'email': 'daniel.martinez@kibabii.ac.ke', 'phone': '0790123468', 'course': 'LAW', 'year_of_study': 3},
    
    # Medicine
    {'registration_number': 'MED/0008/21', 'first_name': 'Jessica', 'last_name': 'Robinson', 'email': 'jessica.robinson@kibabii.ac.ke', 'phone': '0701234579', 'course': 'MEDICINE', 'year_of_study': 4},
    {'registration_number': 'MED/0025/22', 'first_name': 'Kevin', 'last_name': 'Clark', 'email': 'kevin.clark@kibabii.ac.ke', 'phone': '0712345680', 'course': 'MEDICINE', 'year_of_study': 3},
]

def add_students():
    """Add students to database and sync to Firestore"""
    print("=" * 70)
    print("ADDING STUDENTS TO DATABASE")
    print("=" * 70)
    
    # Initialize Firestore
    print("\n[1] Initializing Firestore...")
    firestore_sync.init_firestore()
    
    print("\n[2] Adding students...")
    print("-" * 70)
    
    added = 0
    skipped = 0
    
    for student in students:
        try:
            # Check if student already exists
            existing = execute_query(
                "SELECT student_id FROM students WHERE registration_number = %s",
                (student['registration_number'],)
            )
            
            if existing and len(existing) > 0:
                print(f"  ⚠ {student['registration_number']} already exists - skipping")
                skipped += 1
                continue
            
            # Insert into PostgreSQL
            execute_query("""
                INSERT INTO students 
                (registration_number, first_name, last_name, 
                 email, phone, course, year_of_study, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                student['registration_number'],
                student['first_name'],
                student['last_name'],
                student['email'],
                student['phone'],
                student['course'],
                student['year_of_study'],
                True
            ))
            
            # Get the last inserted ID using currval
            result = execute_query("SELECT last_value FROM students_student_id_seq")
            
            new_student_id = None
            if result and len(result) > 0:
                row = result[0]
                if isinstance(row, dict):
                    new_student_id = row.get('last_value')
                elif isinstance(row, (list, tuple)):
                    new_student_id = row[0]
            
            if new_student_id:
                # Sync to Firestore
                student_data = {
                    'student_id': str(new_student_id),
                    'registration_number': student['registration_number'],
                    'first_name': student['first_name'],
                    'last_name': student['last_name'],
                    'full_name': f"{student['first_name']} {student['last_name']}",
                    'email': student['email'],
                    'phone': student['phone'],
                    'course': student['course'],
                    'year_of_study': student['year_of_study'],
                    'is_active': True
                }
                firestore_sync.sync_student_to_firestore(student_data)
                
                added += 1
                print(f"  ✓ #{new_student_id:3d} | {student['registration_number']:<15} | {student['first_name']} {student['last_name']:<15} | {student['course'][:25]}")
            else:
                print(f"  ✗ Could not get ID for {student['registration_number']}")
            
        except Exception as e:
            print(f"  ✗ Error adding {student['registration_number']}: {e}")
    
    print("-" * 70)
    print(f"\n📊 Summary:")
    print(f"   ✅ Added: {added} students")
    print(f"   ⚠ Skipped: {skipped} students")
    
    if added > 0:
        print("\n✅ Students added to both PostgreSQL and Firestore!")
        print("\nVerify in PostgreSQL:")
        print("   SELECT student_id, registration_number, first_name, last_name, course FROM students;")
        print("\nView in Firebase Console:")
        print("   https://console.firebase.google.com/")
        print("   → Firestore Database → students collection")
        
        # Show course distribution
        print("\n📚 Course Distribution:")
        courses = {}
        for student in students:
            if student['registration_number'] not in [s['registration_number'] for s in students[:added]]:
                continue
            course = student['course']
            courses[course] = courses.get(course, 0) + 1
        for course, count in courses.items():
            print(f"   {course}: {count} students")

if __name__ == "__main__":
    add_students()