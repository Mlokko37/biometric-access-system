"""
Face Recognition Database Models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
import json

from src.database.connection import Base

class FaceEncoding(Base):
    __tablename__ = 'face_encodings'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    encoding = Column(Text, nullable=False)  # JSON serialized list of floats
    image_path = Column(String(255))
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    student = relationship("Student", back_populates="face_encodings")
    
    def set_encoding(self, encoding_list):
        """Store face encoding as JSON string"""
        self.encoding = json.dumps(encoding_list.tolist() if hasattr(encoding_list, 'tolist') else encoding_list)
    
    def get_encoding(self):
        """Retrieve face encoding as list"""
        return json.loads(self.encoding) if self.encoding else None
    
    def __repr__(self):
        return f'<FaceEncoding student_id={self.student_id}>'

class AccessLog(Base):
    __tablename__ = 'access_logs'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    access_point_id = Column(Integer, ForeignKey('access_points.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    status = Column(String(20), default='granted')  # granted, denied, error
    confidence_score = Column(Float)
    verification_method = Column(String(30), default='face_recognition')
    image_path = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration = Column(Float)
    notes = Column(Text)
    
    # Relationships
    student = relationship("Student", back_populates="access_logs")
    access_point = relationship("AccessPoint", back_populates="access_logs")
    user = relationship("User", back_populates="access_logs")
    
    def __repr__(self):
        return f'<AccessLog student_id={self.student_id} status={self.status}>'

# Add to your existing Student model
class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True)
    student_id = Column(String(20), unique=True, nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(120), unique=True)
    phone = Column(String(15))
    course = Column(String(100))
    year_of_study = Column(Integer)
    profile_image = Column(String(255))
    face_encoding_file = Column(String(255))
    is_enrolled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    face_encodings = relationship("FaceEncoding", back_populates="student")
    access_logs = relationship("AccessLog", back_populates="student")