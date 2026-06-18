"""
Firebase Authentication integration for Flask
Hybrid approach: Firebase Auth + Local PostgreSQL
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from flask import current_app

logger = logging.getLogger(__name__)

# Global Firebase app instance
_firebase_app = None

def init_firebase(app=None):
    """Initialize Firebase Admin SDK"""
    global _firebase_app
    
    if _firebase_app is not None:
        return True
    
    try:
        # Get credentials path from environment
        cred_path = os.getenv("FIREBASE_ADMIN_KEY", "firebase-admin-key.json")
        
        # Expand user path if needed (for ~/.secrets/)
        if cred_path.startswith("~"):
            cred_path = os.path.expanduser(cred_path)
        
        if not os.path.exists(cred_path):
            logger.error(f"Firebase admin key not found at: {cred_path}")
            logger.info("Please download from Firebase Console -> Project Settings -> Service Accounts")
            return False
        
        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("[OK] Firebase Admin SDK initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        return False

def get_firebase_app():
    """Get Firebase app instance"""
    if _firebase_app is None:
        init_firebase()
    return _firebase_app

def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """Verify Firebase ID token and return user info"""
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        return None

def create_firebase_user(email: str, password: str, display_name: str = "", phone: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Create a new user in Firebase Authentication
    Returns: (user_uid, error_message)
    """
    try:
        user_args = {
            'email': email,
            'password': password,
            'email_verified': False,
        }
        
        if display_name:
            user_args['display_name'] = display_name
        
        if phone:
            user_args['phone_number'] = phone
        
        user = firebase_auth.create_user(**user_args)
        logger.info(f"✓ Created Firebase user: {user.uid} ({email})")
        return user.uid, None
        
    except firebase_auth.EmailAlreadyExistsError:
        return None, "Email already exists in Firebase"
    except Exception as e:
        logger.error(f"Failed to create Firebase user: {e}")
        return None, str(e)

def update_firebase_user(uid: str, **kwargs) -> Tuple[bool, Optional[str]]:
    """Update Firebase user properties"""
    try:
        firebase_auth.update_user(uid, **kwargs)
        return True, None
    except Exception as e:
        logger.error(f"Failed to update Firebase user: {e}")
        return False, str(e)

def delete_firebase_user(uid: str) -> Tuple[bool, Optional[str]]:
    """Delete user from Firebase Authentication"""
    try:
        firebase_auth.delete_user(uid)
        logger.info(f"✓ Deleted Firebase user: {uid}")
        return True, None
    except Exception as e:
        logger.error(f"Failed to delete Firebase user: {e}")
        return False, str(e)

def get_firebase_user(uid: str) -> Optional[Dict[str, Any]]:
    """Get user from Firebase by UID"""
    try:
        user = firebase_auth.get_user(uid)
        return {
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name,
            'email_verified': user.email_verified,
            'disabled': user.disabled,
            'created_at': user.user_metadata.creation_timestamp,
            'last_sign_in': user.user_metadata.last_sign_in_timestamp,
        }
    except Exception as e:
        logger.error(f"Failed to get Firebase user: {e}")
        return None

def get_firebase_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user from Firebase by email"""
    try:
        user = firebase_auth.get_user_by_email(email)
        return {
            'uid': user.uid,
            'email': user.email,
            'display_name': user.display_name,
            'email_verified': user.email_verified,
            'disabled': user.disabled,
        }
    except Exception as e:
        logger.error(f"Failed to get Firebase user by email: {e}")
        return None

def send_password_reset_email(email: str) -> Tuple[bool, Optional[str]]:
    """Send password reset email via Firebase"""
    try:
        # Note: This requires Firebase Client SDK or REST API
        # For server-side, we'll return a sign-in link
        reset_link = firebase_auth.generate_password_reset_link(email)
        logger.info(f"Generated password reset link for: {email}")
        # You would send this link via email using your email service
        return True, reset_link
    except Exception as e:
        logger.error(f"Failed to generate password reset link: {e}")
        return False, str(e)

def sync_user_from_firebase(uid: str, conn=None) -> Optional[Dict[str, Any]]:
    """
    Sync a Firebase user to local PostgreSQL
    Returns user dict if successful
    """
    try:
        firebase_user = get_firebase_user(uid)
        if not firebase_user:
            return None
        
        from src.database.connection import execute_query
        
        # Check if user exists in PostgreSQL
        result = execute_query(
            "SELECT admin_id FROM administrators WHERE firebase_uid = %s",
            (uid,)
        )
        
        if result:
            # Update existing user
            execute_query("""
                UPDATE administrators 
                SET email = %s, 
                    username = %s,
                    full_name = %s,
                    email_verified = %s,
                    firebase_last_sync = NOW()
                WHERE firebase_uid = %s
            """, (
                firebase_user['email'],
                firebase_user['email'].split('@')[0],  # Use email prefix as username
                firebase_user['display_name'] or firebase_user['email'].split('@')[0],
                firebase_user['email_verified'],
                uid
            ))
            logger.info(f"✓ Updated local user from Firebase: {uid}")
        else:
            # Create new user
            execute_query("""
                INSERT INTO administrators 
                (firebase_uid, username, full_name, email, email_verified, role, is_active, created_at, firebase_last_sync)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                uid,
                firebase_user['email'].split('@')[0],
                firebase_user['display_name'] or firebase_user['email'].split('@')[0],
                firebase_user['email'],
                firebase_user['email_verified'],
                'staff',  # Default role
                not firebase_user.get('disabled', False)
            ))
            logger.info(f"✓ Created local user from Firebase: {uid}")
        
        return firebase_user
        
    except Exception as e:
        logger.error(f"Failed to sync user from Firebase: {e}")
        return None

def sync_all_firebase_users() -> Dict[str, Any]:
    """Sync all Firebase users to local PostgreSQL"""
    try:
        users = firebase_auth.list_users().iterate_all()
        
        synced = 0
        failed = 0
        errors = []
        
        for user in users:
            try:
                result = sync_user_from_firebase(user.uid)
                if result:
                    synced += 1
                else:
                    failed += 1
                    errors.append(f"Failed to sync: {user.uid}")
            except Exception as e:
                failed += 1
                errors.append(f"Error syncing {user.uid}: {e}")
        
        return {
            'success': True,
            'synced': synced,
            'failed': failed,
            'errors': errors[:10]  # Return first 10 errors
        }
        
    except Exception as e:
        logger.error(f"Failed to list Firebase users: {e}")
        return {
            'success': False,
            'error': str(e),
            'synced': 0,
            'failed': 0
        }