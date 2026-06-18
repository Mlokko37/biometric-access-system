import os
import sys
import subprocess
import platform
from typing import Optional
from pathlib import Path

def print_header():
    """Print setup header."""
    print("=" * 60)
    print("BIOMETRIC STUDENT ACCESS CONTROL SYSTEM - SETUP")
    print("Kibabii University - Group Three")
    print("=" * 60)

def check_python_version():
    """Check Python version."""
    print("\n[1/6] Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"[OK] Python {version.major}.{version.minor}.{version.micro} detected")
        return True
    else:
        print(f"[ERROR] Python 3.8+ required, found {version.major}.{version.minor}")
        return False

def check_virtual_env():
    """Check for existing virtual environment (venv or .venv)."""
    print("\n[2/6] Checking virtual environment...")
    
    # Check for common venv folder names
    venv_folders = ['.venv', 'venv', 'env']
    
    existing_venv = None
    for folder in venv_folders:
        if os.path.exists(folder):
            existing_venv = folder
            break
    
    if existing_venv:
        print(f"[OK] Virtual environment found: '{existing_venv}/'")
        print("   Using existing virtual environment")
        return existing_venv
    else:
        print("ℹ️  No virtual environment found")
        
        # Ask user if they want to create one
        response = input("Create virtual environment? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            venv_name = input("Folder name (default: '.venv'): ").strip()
            if not venv_name:
                venv_name = '.venv'
            
            try:
                subprocess.run([sys.executable, '-m', 'venv', venv_name], check=True)
                print(f"[OK] Virtual environment created at '{venv_name}/'")
                return venv_name
            except subprocess.CalledProcessError:
                print("[ERROR] Failed to create virtual environment")
                return None
        else:
            print("[WARN]  Continuing without virtual environment")
            return None

def install_dependencies(venv_folder: Optional[Path] = None):
    """Install Python dependencies."""
    print("\n[3/6] Installing dependencies...")
    
    # Determine which pip to use
    if venv_folder:
        if platform.system() == 'Windows':
            pip_cmd = os.path.join(venv_folder, 'Scripts', 'pip')
        else:
            pip_cmd = os.path.join(venv_folder, 'bin', 'pip')
        
        if not os.path.exists(pip_cmd):
            print(f"[WARN]  Pip not found at {pip_cmd}")
            print("   Trying alternative approach...")
            pip_cmd = None
    else:
        pip_cmd = None
    
    # If no venv pip found or no venv, check if we're already in a venv
    in_venv = sys.prefix != sys.base_prefix
    
    if pip_cmd and os.path.exists(pip_cmd):
        print(f"Using virtual environment pip: {pip_cmd}")
        cmd = [pip_cmd]
    elif in_venv:
        print("Using current virtual environment pip")
        cmd = [sys.executable, '-m', 'pip']
    else:
        print("[WARN]  Installing globally (not recommended)")
        cmd = [sys.executable, '-m', 'pip']
    
    try:
        # Install requirements
        if os.path.exists('requirements.txt'):
            print("Installing dependencies from requirements.txt...")
            
            # Upgrade pip first
            print("Upgrading pip...")
            subprocess.run([*cmd, 'install', '--upgrade', 'pip'], 
                         capture_output=True, text=True, check=False)
            
            # Install packages
            print("Installing packages...")
            result = subprocess.run(
                [*cmd, 'install', '-r', 'requirements.txt'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("[OK] Dependencies installed successfully")
                return True
            else:
                print("[ERROR] Some dependencies failed to install")
                print("Error output:", result.stderr[:500])  # First 500 chars
                return False
        else:
            print("[ERROR] requirements.txt not found")
            return False
    except Exception as e:
        print(f"[ERROR] Installation failed: {e}")
        return False

def setup_environment():
    """Setup environment configuration."""
    print("\n[4/6] Setting up environment...")
    
    if not os.path.exists('.env') and os.path.exists('.env.example'):
        try:
            import shutil
            shutil.copy('.env.example', '.env')
            print("[OK] .env file created from .env.example")
            print("[WARN]  Please edit .env file with your configuration")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create .env: {e}")
            return False
    elif os.path.exists('.env'):
        print("[OK] .env file already exists")
        return True
    else:
        print("[ERROR] .env.example not found")
        return False

def verify_structure():
    """Verify project structure."""
    print("\n[5/6] Verifying project structure...")
    
    required = [
        'src',
        'src/database',
        'src/enrollment',
        'src/verification',
        'data',
        'data/logs'
    ]
    
    for directory in required:
        if not os.path.exists(directory):
            print(f"[WARN]  Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)
        else:
            print(f"[OK] Directory exists: {directory}")
    
    # Create .gitkeep files in empty data directories
    data_dirs = ['data/logs', 'data/backups', 'data/sample_templates']
    for dir_path in data_dirs:
        gitkeep = os.path.join(dir_path, '.gitkeep')
        if not os.path.exists(gitkeep):
            with open(gitkeep, 'w') as f:
                f.write('# Keep this directory in git\n')
    
    return True

def run_tests():
    """Run basic tests."""
    print("\n[6/6] Running basic tests...")
    
    try:
        # Run the test script
        result = subprocess.run(
            [sys.executable, 'tests/test_basic.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Basic tests passed")
            # Show test output if not too long
            if result.stdout and len(result.stdout) < 500:
                print(result.stdout.strip())
            return True
        else:
            print("[ERROR] Basic tests failed")
            if result.stdout:
                print("Output:", result.stdout[:300])
            if result.stderr:
                print("Errors:", result.stderr[:300])
            return False
    except Exception as e:
        print(f"[ERROR] Failed to run tests: {e}")
        return False

def activate_venv_instructions(venv_folder: Optional[Path]):
    """Show instructions to activate virtual environment."""
    print("\n" + "=" * 60)
    print("VIRTUAL ENVIRONMENT ACTIVATION INSTRUCTIONS")
    print("=" * 60)
    
    if venv_folder and str(venv_folder) == ".venv":
        if platform.system() == 'Windows':
            print("To activate on Windows:")
            print(f"  {venv_folder}\\Scripts\\activate")
        else:
            print("To activate on Linux/Mac:")
            print(f"  source {venv_folder}/bin/activate")
    else:
        print(f"Your virtual environment is in '{venv_folder}/'")
    
    print("\nOr if you're using an IDE (VS Code, PyCharm):")
    print("1. Select the Python interpreter from the venv folder")
    print("2. Usually: .venv/bin/python (Linux/Mac)")
    print("3. Or: .venv\\Scripts\\python.exe (Windows)")
    print("=" * 60)

def main():
    """Main setup function."""
    print_header()
    
    # Step 1: Check Python version
    if not check_python_version():
        print("\n[ERROR] Python version check failed")
        return
    
    # Step 2: Check for existing venv
    venv_folder = check_virtual_env()
    
    # Step 3: Install dependencies using existing venv
    if not install_dependencies(Path(venv_folder) if venv_folder else None):
        print("\n[WARN]  Dependency installation had issues")
        # Continue anyway
    
    # Step 4: Setup environment
    if not setup_environment():
        print("\n[WARN]  Environment setup had issues")
    
    # Step 5: Verify structure
    verify_structure()
    
    # Step 6: Run tests
    run_tests()
    
    # Show completion message
    print("\n" + "=" * 60)
    print("SETUP COMPLETED!")
    print("=" * 60)
    
    # Show venv activation instructions if we have one
    if venv_folder:
        activate_venv_instructions(Path(venv_folder) if venv_folder else None)
    # Next steps    
    print("\nNEXT STEPS:")
    print("1. Edit the .env file with your configuration:")
    print("   - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD")
    print("   - APP_SECRET_KEY (generate a random one)")
    print("   - Hardware ports if applicable")
    
    print("\n2. Set up PostgreSQL database:")
    print("   CREATE DATABASE biometric_access_db;")
    
    print("\n3. Run the system:")
    if venv_folder:
        print(f"   source {venv_folder}/bin/activate  # Activate venv first")
    print("   python main.py")
    
    print("\n4. Default admin login:")
    print("   Username: admin")
    print("   Password: password")
    
    print("\n5. Check the README.md for more details")
    print("=" * 60)

if __name__ == "__main__":
    main()