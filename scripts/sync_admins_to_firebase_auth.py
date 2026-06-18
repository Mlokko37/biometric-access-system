#!/usr/bin/env python3
"""
Sync existing administrators from PostgreSQL to Firebase Authentication
"""

import sys
import os
import bcrypt
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import execute_query
from src.database.firebase_auth import init_firebase, create_firebase_user, update_firebase_user
from src.database.firestore_sync import firestore_sync

def sync_admin_to_firebase_auth(admin):
    """Sync a single admin to Firebase Auth"""
    
    admin_id = admin.get('admin_id')
    username = admin.get('username', '')
    email = admin.get('email', '')
    full_name = admin.get('full_name', '')
    role = admin.get('role', 'staff')
    
    # Skip if no email
    if not email:
        print(f"  ⚠ Admin {username} has no email - cannot create Firebase user")
        return False
    
    # Create temporary password (user will need to reset)
    temp_password = f"Temp@{admin_id}!"
    
    print(f"  Creating Firebase user for: {username} ({email})")
    
    # Create user in Firebase Auth
    firebase_uid, error = create_firebase_user(email, temp_password, full_name or username)
    
    if firebase_uid:
        # Update PostgreSQL with Firebase UID
        execute_query("""
            UPDATE administrators 
            SET firebase_uid = %s, 
                firebase_last_sync = NOW(),
                updated_at = NOW()
            WHERE admin_id = %s
        """, (firebase_uid, admin_id))
        
        print(f"  ✓ Synced {username} to Firebase Auth (UID: {firebase_uid[:8]}...)")
        print(f"    Temporary password: {temp_password}")
        print(f"    ⚠ User must reset password on first login")
        
        # Also sync to Firestore
        admin_data = {
            'admin_id': admin_id,
            'username': username,
            'full_name': full_name,
            'email': email,
            'role': role,
            'firebase_uid': firebase_uid,
            'is_active': True
        }
        firestore_sync.sync_admin_to_firestore(admin_data)
        
        return True
    else:
        print(f"  ✗ Failed to create Firebase user for {username}: {error}")
        return False

def main():
    print("=" * 60)
    print("SYNC ADMINISTRATORS TO FIREBASE AUTH")
    print("=" * 60)
    
    # Initialize Firebase
    print("\n[1] Initializing Firebase...")
    if not init_firebase():
        print("❌ Firebase initialization failed!")
        return
    
    # Initialize Firestore
    print("\n[2] Initializing Firestore...")
    firestore_sync.init_firestore()
    
    # Get admins without Firebase UID
    print("\n[3] Fetching administrators without Firebase Auth...")
    admins = execute_query("""
        SELECT admin_id, username, email, full_name, role, firebase_uid
        FROM administrators
        WHERE is_active = TRUE
        ORDER BY admin_id
    """)
    
    if not admins:
        print("  No administrators found")
        return
    
    print(f"  Found {len(admins)} administrators")
    
    # Separate those with and without Firebase UID
    need_sync = []
    already_synced = []
    
    for admin in admins:
        if admin.get('firebase_uid'):
            already_synced.append(admin)
        else:
            need_sync.append(admin)
    
    if already_synced:
        print(f"\n  Already synced to Firebase Auth: {len(already_synced)}")
        for admin in already_synced:
            print(f"    ✓ {admin.get('username')} (UID: {admin.get('firebase_uid')[:8]}...)")
    
    if not need_sync:
        print("\n✅ All administrators are already synced to Firebase Auth!")
        return
    
    print(f"\n  Need to sync: {len(need_sync)}")
    
    # Sync admins to Firebase Auth
    print("\n[4] Syncing to Firebase Auth...")
    synced = 0
    failed = 0
    
    for admin in need_sync:
        if sync_admin_to_firebase_auth(admin):
            synced += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   Successfully synced: {synced}")
    print(f"   Failed: {failed}")
    
    if synced > 0:
        print("\n⚠ IMPORTANT: Temporary passwords were created!")
        print("   Users must reset their password on first login.")
        print("\n   To allow password reset, users can:")
        print("   1. Use 'Forgot Password' on login page")
        print("   2. Or run password reset script")
    
    print("\n✅ Administrators are now in Firebase Auth!")
    print("\nView them at: https://console.firebase.google.com/")
    print("Go to Authentication → Users")

if __name__ == "__main__":
    main()