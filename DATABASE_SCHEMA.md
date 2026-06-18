# Database Schema Documentation

## Tables

### students
- student_id (PK)
- registration_number
- full_name
- course
- year_of_study
- created_at

### biometric_templates
- template_id (PK)
- student_id (FK)
- fingerprint_template (encrypted)
- face_template (encrypted)
- created_at

### access_logs
- log_id (PK)
- student_id (FK)
- access_point
- verification_method
- access_result
- timestamp

### administrators
- admin_id (PK)
- username
- password_hash
- role
- created_at
