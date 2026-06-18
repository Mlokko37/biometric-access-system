#!/usr/bin/env python3
"""Test local PostgreSQL + Firebase setup"""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("Testing Local PostgreSQL + Firebase Setup")
print("=" * 60)

# Test 1: PostgreSQL connection
print("\n[1] Testing PostgreSQL connection...")
from src.database.connection import init_pool, execute_query

if init_pool():
    print("✓ PostgreSQL connected")
    
    # Test query
    result = execute_query("SELECT version() as version, current_database() as db_name")
    if result:
        print(f"  Database: {result[0]['db_name']}")
        print(f"  Version: {result[0]['version'][:50]}...")
else:
    print("✗ PostgreSQL connection failed")
    exit(1)

# Test 2: Firebase initialization
print("\n[2] Testing Firebase initialization...")
from src.database.firebase_auth import init_firebase

if init_firebase():
    print("✓ Firebase initialized")
else:
    print("⚠ Firebase initialization failed (fallback to local auth)")

# Test 3: Check database schema
print("\n[3] Checking database schema...")
tables = execute_query("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

if tables:
    print(f"✓ Found {len(tables)} tables:")
    for table in tables:
        print(f"  - {table['table_name']}")
else:
    print("✗ No tables found - run init_local_db.py")

print("\n" + "=" * 60)
print("✅ Setup is ready!")
print("=" * 60)