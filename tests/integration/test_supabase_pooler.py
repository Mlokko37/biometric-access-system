#!/usr/bin/env python3
"""Test Supabase connection using Transaction Pooler"""

import os
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

print("=" * 70)
print("Supabase Transaction Pooler Connection Test")
print("=" * 70)

# Method 1: Using individual parameters
print("\n[Method 1] Connecting with individual parameters...")

host = os.getenv("SUPABASE_DB_HOST", "")
port = os.getenv("SUPABASE_DB_PORT", "6543")
user = os.getenv("SUPABASE_DB_USER", "")
password = os.getenv("SUPABASE_DB_PASSWORD", "")
database = os.getenv("SUPABASE_DB_NAME", "postgres")

print(f"  Host: {host}")
print(f"  Port: {port}")
print(f"  User: {user}")
print(f"  Database: {database}")

try:
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        connect_timeout=10,
        sslmode='require'  # Supabase requires SSL
    )
    
    print("✓ Connected successfully!")
    
    # Test query
    cur = conn.cursor()
    cur.execute("SELECT version(), current_database(), current_user, NOW()")
    result = cur.fetchone()
    
    print("\n✅ Database Information:")
    print(f"  PostgreSQL Version: {result[0][:60]}...")
    print(f"  Database Name: {result[1]}")
    print(f"  Current User: {result[2]}")
    print(f"  Server Time: {result[3]}")
    
    # Check if tables exist
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    tables = cur.fetchall()
    if tables:
        print(f"\n📊 Existing tables ({len(tables)}):")
        for table in tables[:10]:  # Show first 10
            print(f"  - {table[0]}")
        if len(tables) > 10:
            print(f"  ... and {len(tables) - 10} more")
    else:
        print("\n⚠ No tables found. Run init_db.py to create them.")
    
    cur.close()
    conn.close()
    
    print("\n🎉 Supabase is ready to use!")
    
except OperationalError as e:
    print(f"\n✗ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure your IP is allowed in Supabase network settings")
    print("2. Go to: https://app.supabase.com/project/gqlupibjdygthahkww1/settings/database")
    print("3. Under 'Network Restrictions', add your IP address")
    print("4. Your current IP might have changed - check it at https://whatismyip.com")
    
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)

# Method 2: Using connection string
print("\n[Method 2] Trying connection string method...")

try:
    # URL encode special characters
    # @ becomes %40, $ becomes %24
    conn_string = f"postgresql://postgres.gqlupibjdy%40thnkhwkr1:%24Collotynho254@aes-1-eu-central-1.pooler.supabase.com:6543/postgres?sslmode=require"
    
    conn = psycopg2.connect(conn_string)
    print("✓ Connected using connection string!")
    conn.close()
    
except Exception as e:
    print(f"✗ Connection string failed: {e}")

print("\n" + "=" * 70)