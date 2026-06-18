"""
Run database migration for face recognition tables
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.connection import execute_query, get_db_connection, release_db_connection

def run_migration():
    """Run the migration"""
    print("=" * 60)
    print("Face Recognition Database Migration")
    print("=" * 60)
    
    try:
        # Read SQL file
        sql_file = os.path.join(os.path.dirname(__file__), 'add_face_tables_postgres.sql')
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Split into statements
        statements = sql_content.split(';')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\nExecuting migration...")
        
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cursor.execute(statement)
                    print(f"✓ Executed: {statement[:50]}...")
                except Exception as e:
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"ℹ Already exists: {statement[:30]}...")
                    else:
                        print(f"✗ Error: {e}")
                        print(f"  Statement: {statement[:100]}")
        
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    run_migration()