#!/usr/bin/env python3
"""
Initialize local PostgreSQL database with Firebase Auth support.
Run this after setting up your database.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import DatabaseConnection, init_pool
from src.database.firebase_auth import init_firebase

def main():
    print("=" * 60)
    print("Local PostgreSQL + Firebase Auth Setup")
    print("=" * 60)
    
    # Debug: Show Firebase key path
    firebase_key = os.getenv("FIREBASE_ADMIN_KEY", "")
    print(f"\n[DEBUG] Firebase key path: {firebase_key}")
    
    # Step 1: Initialize PostgreSQL
    print("\n[1/3] Initializing PostgreSQL...")
    if init_pool():
        print("✓ PostgreSQL connection pool initialized")
    else:
        print("✗ PostgreSQL initialization failed!")
        print("  Make sure PostgreSQL is running and credentials are correct")
        return False
    
    # Step 2: Create tables
    print("\n[2/3] Creating database tables...")
    db = DatabaseConnection()
    if db.connect():
        if db.create_tables():
            print("✓ All tables created successfully!")
            
            # Add Firebase columns if they don't exist
            try:
                from src.database.connection import execute_query
                execute_query("""
                    ALTER TABLE administrators 
                    ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128) UNIQUE
                """)
                execute_query("""
                    ALTER TABLE administrators 
                    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE
                """)
                execute_query("""
                    ALTER TABLE administrators 
                    ADD COLUMN IF NOT EXISTS firebase_last_sync TIMESTAMP
                """)
                print("✓ Firebase columns verified")
            except Exception as e:
                print(f"⚠ Note: {e}")
        else:
            print("✗ Failed to create tables")
            return False
        db.close()
    else:
        print("✗ Failed to connect to database")
        return False
    
    # Step 3: Initialize Firebase
    print("\n[3/3] Initializing Firebase...")
    if init_firebase():
        print("✓ Firebase Admin SDK initialized")
        
        # Optional: Sync Firebase users
        print("\n  Syncing Firebase users to PostgreSQL...")
        from src.database.firebase_auth import sync_all_firebase_users
        result = sync_all_firebase_users()
        if result['success']:
            print(f"  ✓ Synced {result['synced']} users")
            if result['failed'] > 0:
                print(f"  ⚠ Failed to sync {result['failed']} users")
        else:
            print(f"  ✗ Sync failed: {result.get('error', 'Unknown')}")
    else:
        print("⚠ Firebase initialization failed - auth will fall back to local passwords")
        print("  Make sure FIREBASE_ADMIN_KEY is set correctly in .env")
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run: python scripts/setup_admin_accounts.py")
    print("2. Start the app: python src/admin/app.py")
    print("3. Login with superadmin credentials")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)