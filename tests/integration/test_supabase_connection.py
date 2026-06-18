#!/usr/bin/env python3
"""Test Supabase connection with better error messages"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("=" * 60)
print("Supabase Connection Test")
print("=" * 60)

# Check environment variables
print("\n[1] Checking environment variables...")
supabase_host = os.getenv("SUPABASE_DB_HOST", "")
supabase_password = os.getenv("SUPABASE_DB_PASSWORD", "")
supabase_url = os.getenv("SUPABASE_DATABASE_URL", "")

if supabase_url:
    print("✓ SUPABASE_DATABASE_URL is set")
    # Mask the password for security
    masked_url = supabase_url.replace(supabase_url.split(':')[2].split('@')[0], '****')
    print(f"  URL: {masked_url[:50]}...")
elif supabase_host and supabase_password:
    print("✓ SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD are set")
    print(f"  Host: {supabase_host}")
    print(f"  Password: {'*' * len(supabase_password)}")
else:
    print("✗ Missing Supabase credentials!")
    print("\nPlease set one of the following in your .env file:")
    print("  Option 1: SUPABASE_DATABASE_URL=postgresql://postgres:password@host.supabase.co:5432/postgres")
    print("  Option 2: SUPABASE_DB_HOST=your-project.supabase.co")
    print("            SUPABASE_DB_PASSWORD=your_password")
    exit(1)

# Try to connect
print("\n[2] Attempting to connect to Supabase...")

try:
    from src.database.connection import is_supabase_connected, get_supabase_version, init_pool
    
    # Reinitialize pool with current credentials
    from src.database.connection import _pool, init_pool
    global _pool
    _pool = None  # Reset pool
    init_pool()  # Reinitialize
    
    if is_supabase_connected():
        print("✓ Successfully connected to Supabase!")
        
        version = get_supabase_version()
        if version:
            print(f"  PostgreSQL Version: {version[:80]}...")
        
        # Test a simple query
        from src.database.connection import execute_query
        result = execute_query("SELECT NOW() as current_time, current_database() as db_name")
        if result:
            print(f"  Database: {result[0]['db_name']}")
            print(f"  Server Time: {result[0]['current_time']}")
        
        print("\n✅ Supabase connection is working correctly!")
        
    else:
        print("✗ Failed to connect to Supabase!")
        
except Exception as e:
    print(f"✗ Connection error: {e}")
    print("\nPossible issues:")
    print("  1. Host name is incorrect (should end with .supabase.co)")
    print("  2. Password is wrong")
    print("  3. Your IP is not allowed in Supabase network settings")
    print("  4. Database name is not 'postgres' (unless you changed it)")
    print("\nGo to: https://app.supabase.com/project/_/settings/database")
    print("to verify your connection parameters.")