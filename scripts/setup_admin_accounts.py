#!/usr/bin/env python3
"""
Setup initial administrator accounts.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.admin.services.admin_service import AdminService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_initial_accounts():
    print("=== Setting up Initial Administrator Accounts ===\n")
    
    admin_service = AdminService()
    
    # List of accounts to create
    accounts = [
        {
            'username': 'superadmin',
            'password': 'SuperAdminPass123!',
            'full_name': 'System Super Administrator',
            'email': 'superadmin@school.edu',
            'role': 'superadmin'
        },
        {
            'username': 'admin',
            'password': 'AdminPass123!',
            'full_name': 'System Administrator',
            'email': 'admin@school.edu',
            'role': 'admin'
        },
        {
            'username': 'operator',
            'password': 'OperatorPass123!',
            'full_name': 'System Operator',
            'email': 'operator@school.edu',
            'role': 'operator'
        }
    ]
    
    for account in accounts:
        print(f"\nCreating account: {account['username']}...")
        success = admin_service.create_admin(**account)
        
        if success:
            print(f"[OK] Account '{account['username']}' created successfully")
            print(f"  Username: {account['username']}")
            print(f"  Password: {account['password']}")
        else:
            print(f"✗ Account '{account['username']}' already exists or creation failed")
    
    print("\n=== Setup Complete ===")
    print("\nIMPORTANT:")
    print("1. Log in with superadmin account")
    print("2. Change all default passwords immediately!")
    print("3. Create your school-specific administrators")

if __name__ == '__main__':
    setup_initial_accounts()