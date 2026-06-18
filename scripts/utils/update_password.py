#!/usr/bin/env python3
"""
Update admin password in PostgreSQL database.
Usage: python update_password.py <username> <new_password>
"""

import sys
import os
import bcrypt
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from src.database.connection import execute_query

def update_password(username: str, new_password: str):
    """Update password for a user"""
    try:
        # Hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
        
        # Update in database
        execute_query(
            "UPDATE administrators SET password_hash = %s, updated_at = NOW() WHERE username = %s",
            (hashed, username)
        )
        
        print(f"[OK] Password updated for user: {username}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update password: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python update_password.py <username> <new_password>")
        print("Example: python update_password.py admin MyNewPass123!")
        sys.exit(1)
    
    username = sys.argv[1]
    new_password = sys.argv[2]
    
    success = update_password(username, new_password)
    sys.exit(0 if success else 1)