-- Face Encodings Table for PostgreSQL
CREATE TABLE IF NOT EXISTS face_encodings (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    encoding TEXT NOT NULL,
    image_path VARCHAR(255),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add columns to access_logs if they don't exist
DO $$ 
BEGIN
    BEGIN
        ALTER TABLE access_logs ADD COLUMN confidence_score FLOAT;
    EXCEPTION
        WHEN duplicate_column THEN RAISE NOTICE 'column confidence_score already exists in access_logs.';
    END;
    
    BEGIN
        ALTER TABLE access_logs ADD COLUMN verification_method VARCHAR(30) DEFAULT 'face_recognition';
    EXCEPTION
        WHEN duplicate_column THEN RAISE NOTICE 'column verification_method already exists in access_logs.';
    END;
END $$;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_face_encodings_student_id ON face_encodings(student_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_logs_student_id ON access_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_access_point_id ON access_logs(access_point_id);