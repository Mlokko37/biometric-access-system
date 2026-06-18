#!/usr/bin/env python3
"""
Generate bcrypt hash for a password.
Usage: python generate_hash.py <password>
"""

import sys
import bcrypt

def generate_hash(password: str) -> str:
    """Generate bcrypt hash for a password"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_hash.py <password>")
        print("Example: python generate_hash.py MySecretPass123")
        sys.exit(1)
    
    password = sys.argv[1]
    hashed = generate_hash(password)
    
    print("\n" + "=" * 60)
    print("BCRYPT HASH GENERATED")
    print("=" * 60)
    print(f"Password: {password}")
    print(f"Hash: {hashed}")
    print("\nYou can use this hash in your database.")