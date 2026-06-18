#!/usr/bin/env python3
"""
Project Cleanup and Reorganization Script
Run this to automatically clean up your project structure
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

class ProjectCleanup:
    def __init__(self, project_root):
        self.project_root = Path(project_root).resolve()
        self.files_moved = []
        self.files_removed = []
        self.errors = []
        
    def print_header(self, text):
        print("\n" + "=" * 70)
        print(f" {text}")
        print("=" * 70)
    
    def ensure_dir(self, path):
        """Create directory if it doesn't exist"""
        path = self.project_root / path
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def move_file(self, file_path, dest_dir):
        """Move file to destination directory"""
        try:
            src = self.project_root / file_path
            if not src.exists():
                return False
            
            dest_dir_path = self.ensure_dir(dest_dir)
            dest = dest_dir_path / src.name
            
            # Handle duplicate filenames
            if dest.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = dest_dir_path / f"{src.stem}_{timestamp}{src.suffix}"
            
            shutil.move(str(src), str(dest))
            self.files_moved.append(f"{file_path} -> {dest_dir}/{dest.name}")
            print(f"  ✓ Moved: {file_path} -> {dest_dir}/")
            return True
        except Exception as e:
            self.errors.append(f"Failed to move {file_path}: {e}")
            print(f"  ✗ Error moving {file_path}: {e}")
            return False
    
    def remove_file(self, file_path):
        """Remove file if it exists"""
        try:
            src = self.project_root / file_path
            if src.exists():
                src.unlink()
                self.files_removed.append(str(file_path))
                print(f"  ✓ Removed: {file_path}")
                return True
        except Exception as e:
            self.errors.append(f"Failed to remove {file_path}: {e}")
            print(f"  ✗ Error removing {file_path}: {e}")
            return False
    
    def backup_gitignore(self):
        """Create backup of .gitignore"""
        gitignore_path = self.project_root / ".gitignore"
        if gitignore_path.exists():
            backup_path = self.project_root / ".gitignore.backup"
            shutil.copy(gitignore_path, backup_path)
            print(f"  ✓ Backed up .gitignore to .gitignore.backup")
    
    def update_gitignore(self):
        """Update .gitignore with security rules"""
        gitignore_path = self.project_root / ".gitignore"
        
        new_entries = """
# ===== SECURITY - CRITICAL =====
# Firebase credentials
*.json
firebase-*.json
*-firebase-adminsdk-*.json
service-account-key.json

# Environment files
.env
.env.local
.env.*.local
.env.backup

# Database files
*.db
*.sqlite
*.sqlite3
*.mdb

# ===== TEMPORARY FILES =====
*.tmp
*.temp
*.log
*.bak
*.backup
z.txt
location.reload()
icon.html

# ===== TEST FILES =====
test_*.py
*_test.py
!tests/**/test_*.py

# ===== IDE & OS =====
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
Thumbs.db
desktop.ini

# ===== PYTHON =====
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
htmlcov/

# ===== PROJECT SPECIFIC =====
backups/*.sql
!backups/.gitkeep
data/backups/*.sql
!data/backups/.gitkeep

# ===== HARDWARE CONFIGS WITH CREDS =====
hardware/configs/*.yaml
!hardware/configs/*.example.yaml
"""
        
        # Read existing .gitignore
        existing_content = ""
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                existing_content = f.read()
        
        # Check if our entries already exist
        if "# ===== SECURITY - CRITICAL =====" not in existing_content:
            with open(gitignore_path, 'a') as f:
                f.write(new_entries)
            print("  ✓ Updated .gitignore with security rules")
        else:
            print("  ✓ .gitignore already has security rules")
    
    def create_env_example(self):
        """Create .env.example from .env with placeholders"""
        env_path = self.project_root / ".env"
        env_example_path = self.project_root / ".env.example"
        
        if not env_path.exists():
            print("  ⚠ .env file not found, skipping .env.example creation")
            return
        
        # Read .env file
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Replace sensitive values with placeholders
        example_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                example_lines.append(line)
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                
                # Replace passwords and keys
                if any(x in key.upper() for x in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']):
                    if key.startswith('#'):
                        example_lines.append(line)
                    else:
                        example_lines.append(f"{key}=YOUR_{key}_HERE")
                else:
                    example_lines.append(line)
            else:
                example_lines.append(line)
        
        # Write .env.example
        with open(env_example_path, 'w') as f:
            f.write('\n'.join(example_lines))
        
        print("  ✓ Created .env.example with placeholders")
    
    def move_test_files(self):
        """Move test files to tests/integration"""
        tests_moved = False
        test_files = [
            "test_supabase_connection.py",
            "test_supabase_pooler.py",
            "test_supabase_final.py",
            "test_supabase_fixed.py",
            "test_hybrid_auth.py",
        ]
        
        for test_file in test_files:
            if self.move_file(test_file, "tests/integration"):
                tests_moved = True
        
        return tests_moved
    
    def move_scripts(self):
        """Move utility scripts to scripts/utils"""
        scripts_moved = False
        script_files = [
            "fix_emojis.py",
            "tree.ps1",
        ]
        
        for script in script_files:
            if self.move_file(script, "scripts/utils"):
                scripts_moved = True
        
        return scripts_moved
    
    def remove_temp_files(self):
        """Remove temporary and strange files"""
        temp_files = [
            "location.reload())",  # Strange filename
            "z.txt",
            "icon.html",
            "biometric_access.db",  # SQLite file (using PostgreSQL)
        ]
        
        for temp_file in temp_files:
            self.remove_file(temp_file)
    
    def secure_firebase_keys(self):
        """Move Firebase keys to secure location"""
        firebase_keys = [
            "biometric-access-system-firebase-adminsdk-fbsvc-e139ea1770.json",
            "firebase-admin-key.json",
        ]
        
        # Create secure directory (outside project)
        secure_dir = Path.home() / ".secrets" / "biometric-system"
        secure_dir.mkdir(parents=True, exist_ok=True)
        
        for key_file in firebase_keys:
            src = self.project_root / key_file
            if src.exists():
                try:
                    dest = secure_dir / key_file
                    shutil.move(str(src), str(dest))
                    self.files_moved.append(f"{key_file} -> ~/.secrets/biometric-system/")
                    print(f"  ✓ Secured: {key_file} -> ~/.secrets/biometric-system/")
                    
                    # Update .env to point to new location
                    env_path = self.project_root / ".env"
                    if env_path.exists():
                        with open(env_path, 'r') as f:
                            env_content = f.read()
                        
                        # Add or update FIREBASE_ADMIN_KEY
                        if "FIREBASE_ADMIN_KEY" in env_content:
                            # Update existing line
                            lines = env_content.split('\n')
                            for i, line in enumerate(lines):
                                if line.startswith("FIREBASE_ADMIN_KEY="):
                                    lines[i] = f"FIREBASE_ADMIN_KEY={secure_dir / key_file}"
                            env_content = '\n'.join(lines)
                        else:
                            # Add new line
                            env_content += f"\nFIREBASE_ADMIN_KEY={secure_dir / key_file}\n"
                        
                        with open(env_path, 'w') as f:
                            f.write(env_content)
                        print(f"  ✓ Updated .env with new Firebase key path")
                        
                except Exception as e:
                    self.errors.append(f"Failed to secure {key_file}: {e}")
                    print(f"  ✗ Error securing {key_file}: {e}")
    
    def check_for_committed_secrets(self):
        """Check if secrets might be in git history"""
        git_dir = self.project_root / ".git"
        if git_dir.exists():
            print("\n  ⚠ WARNING: Check if secrets were committed to git!")
            print("    Run these commands to check:")
            print("    git log --all --full-history -- '*.json'")
            print("    git log --all --full-history -- '.env'")
            print("\n    If found, use BFG Repo-Cleaner or git filter-branch")
    
    def create_directory_structure(self):
        """Ensure all required directories exist"""
        directories = [
            "tests/integration",
            "tests/unit",
            "tests/system",
            "scripts/utils",
            "data/logs",
            "data/backups",
            "data/sample_templates",
            "data/captures",
            "data/exports",
        ]
        
        for directory in directories:
            self.ensure_dir(directory)
        
        print("  ✓ Verified directory structure")
    
    def generate_report(self):
        """Generate cleanup report"""
        self.print_header("CLEANUP REPORT")
        
        print(f"\n📁 Files Moved: {len(self.files_moved)}")
        for item in self.files_moved[:10]:  # Show first 10
            print(f"  • {item}")
        if len(self.files_moved) > 10:
            print(f"  ... and {len(self.files_moved) - 10} more")
        
        print(f"\n🗑️  Files Removed: {len(self.files_removed)}")
        for item in self.files_removed:
            print(f"  • {item}")
        
        if self.errors:
            print(f"\n⚠️  Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"  • {error}")
        
        print("\n" + "=" * 70)
        print(" NEXT STEPS")
        print("=" * 70)
        print("""
1. Review changes:
   git status

2. If secrets were committed to git history:
   - Rotate any exposed API keys/passwords
   - Use BFG Repo-Cleaner: https://rtyley.github.io/bfg-repo-cleaner/
   - Or run: git filter-branch --force --index-filter \\
     "git rm --cached --ignore-unmatch *.json .env" \\
     --prune-empty --tag-name-filter cat -- --all

3. Update your environment:
   - Copy .env.example to .env (if needed)
   - Add real values back (but don't commit!)

4. Test your application:
   python main.py
""")
    
    def run(self):
        """Run all cleanup tasks"""
        self.print_header("PROJECT CLEANUP STARTED")
        
        print("\n[1/8] Backing up .gitignore...")
        self.backup_gitignore()
        
        print("\n[2/8] Creating directory structure...")
        self.create_directory_structure()
        
        print("\n[3/8] Moving test files...")
        self.move_test_files()
        
        print("\n[4/8] Moving utility scripts...")
        self.move_scripts()
        
        print("\n[5/8] Removing temporary files...")
        self.remove_temp_files()
        
        print("\n[6/8] Securing Firebase keys...")
        self.secure_firebase_keys()
        
        print("\n[7/8] Updating .gitignore...")
        self.update_gitignore()
        
        print("\n[8/8] Creating .env.example...")
        self.create_env_example()
        
        print("\n[9/9] Checking for committed secrets...")
        self.check_for_committed_secrets()
        
        # Generate report
        self.generate_report()
        
        return len(self.errors) == 0

def main():
    # Get project root (current directory or specified)
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()
    
    print(f"Project root: {project_root}")
    response = input("\nThis will reorganize your project files. Continue? (y/N): ")
    
    if response.lower() != 'y':
        print("Cleanup cancelled.")
        return
    
    cleanup = ProjectCleanup(project_root)
    success = cleanup.run()
    
    if success:
        print("\n✅ Cleanup completed successfully!")
    else:
        print("\n⚠️  Cleanup completed with warnings. Check the report above.")
        sys.exit(1)

if __name__ == "__main__":
    main()