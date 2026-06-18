#!/usr/bin/env python3
"""
Schema checker for Supabase PostgreSQL database.
"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import execute_query, get_db_connection, release_db_connection

def check_schema():
    """Check database schema and show table structures."""
    
    print("=" * 80)
    print("SUPABASE DATABASE SCHEMA CHECKER")
    print("=" * 80)
    
    # Get all tables
    tables_result = execute_query("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    if not tables_result:
        print("No tables found in the database!")
        return
    
    print(f"\nFound {len(tables_result)} tables:\n")
    
    for table_row in tables_result:
        table_name = table_row[0]
        print(f"\n{'=' * 80}")
        print(f"TABLE: {table_name.upper()}")
        print('=' * 80)
        
        # Get column information
        columns_result = execute_query("""
            SELECT 
                column_name, 
                data_type, 
                is_nullable,
                column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        if columns_result:
            print(f"\n{'Column Name':<30} {'Data Type':<20} {'Nullable':<10} {'Default'}")
            print("-" * 80)
            for col in columns_result:
                col_name = col[0]
                data_type = col[1]
                is_nullable = col[2]
                default = col[3] if col[3] else ''
                print(f"{col_name:<30} {data_type:<20} {is_nullable:<10} {default[:30]}")
        
        # Get row count
        count_result = execute_query(f"SELECT COUNT(*) FROM {table_name}")
        if count_result:
            print(f"\nTotal rows: {count_result[0][0]}")
    
    # Database info
    print("\n" + "=" * 80)
    print("DATABASE INFORMATION")
    print("=" * 80)
    
    db_info = execute_query("""
        SELECT 
            current_database() as database_name,
            inet_server_addr() as server_address,
            version() as postgres_version
    """)
    
    if db_info:
        print(f"Database Name: {db_info[0][0]}")
        print(f"Server Address: {db_info[0][1] or 'N/A'}")
        print(f"PostgreSQL Version: {db_info[0][2][:80]}...")
    
    # Database size
    size_result = execute_query("""
        SELECT pg_database_size(current_database()) as size_bytes
    """)
    
    if size_result:
        size_bytes = size_result[0][0]
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024
        print(f"Database Size: {size_mb:.2f} MB ({size_gb:.2f} GB)")

if __name__ == "__main__":
    check_schema()