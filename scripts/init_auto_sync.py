#!/usr/bin/env python3
"""
Initialize automatic sync - Run once to set up
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.firestore_sync import firestore_sync
from src.database.auto_sync import auto_sync

print("=" * 60)
print("INITIALIZING AUTO SYNC SYSTEM")
print("=" * 60)

# Initialize Firestore
print("\n[1] Connecting to Firestore...")
if firestore_sync.init_firestore():
    print("✓ Firestore connected")
else:
    print("❌ Firestore connection failed")
    exit(1)

print("\n✅ Auto-sync system ready!")
print("\nNow when you:")
print("  • Add a student → Auto-syncs to Firestore")
print("  • Edit a student → Auto-syncs to Firestore")
print("  • Delete a student → Auto-syncs to Firestore")
print("  • Log access → Auto-syncs to Firestore")
print("\nNo more manual scripts needed! 🔥")