#!/usr/bin/env python
"""
Script to replace emoji characters in all Python files with text alternatives.
Run this script from the project root directory.
"""

import os
import re
import sys
from pathlib import Path

# Mapping of emoji to replacement text
EMOJI_MAP = {
    '[OK]': '[OK]',
    '[ERROR]': '[ERROR]',
    '[OK]': '[OK]',
    '[OK]': '[OK]',
    '[WARN]': '[WARN]',
    '[MODE]': '[MODE]',
    '[MENU]': '[MENU]',
    '[INFO]': '[INFO]',
    '[CAMERA]': '[CAMERA]',
    '[LOCK]': '[LOCK]',
    '[DEVICE]': '[DEVICE]',
    '[CAMERA]': '[CAMERA]',
    '[SECURE]': '[SECURE]',
    '[POWER]': '[POWER]',
    '[PC]': '[PC]',
    '[SCREEN]': '[SCREEN]',
    '[TIMER]': '[TIMER]',
    '[WAIT]': '[WAIT]',
    '[KEY]': '[KEY]',
    '[GEAR]': '[GEAR]',
    '[TOOL]': '[TOOL]',
    '[TOOLS]': '[TOOLS]',
    '[BELL]': '[BELL]',
    '[CHART]': '[CHART]',
    '[UP]': '[UP]',
    '[DOWN]': '[DOWN]',
    '[RED]': '[RED]',
    '[GREEN]': '[GREEN]',
    '[BLUE]': '[BLUE]',
    '[YELLOW]': '[YELLOW]',
    '[WHITE]': '[WHITE]',
    '[BLACK]': '[BLACK]',
}

def fix_emojis_in_file(filepath):
    """Replace emojis in a single file."""
    try:
        # Read file with UTF-8 encoding
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Replace each emoji
        for emoji, replacement in EMOJI_MAP.items():
            content = content.replace(emoji, replacement)
        
        # Also replace any other non-ASCII characters that might be emojis
        # This regex finds any character outside the ASCII range
        def replace_non_ascii(match):
            char = match.group(0)
            # If it's in our map, use that replacement
            if char in EMOJI_MAP:
                return EMOJI_MAP[char]
            # Otherwise, replace with a placeholder
            return f'[UNICODE]'
        
        if content != original:
            # Write back with UTF-8 encoding
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return False

def main():
    """Main function."""
    project_root = Path.cwd()
    print(f"Scanning Python files in: {project_root}")
    
    python_files = list(project_root.rglob('*.py'))
    print(f"Found {len(python_files)} Python files")
    
    modified_files = []
    
    for filepath in python_files:
        # Skip files in virtual environment
        if '.venv' in str(filepath) or 'env' in str(filepath) or 'venv' in str(filepath):
            continue
        
        if fix_emojis_in_file(filepath):
            modified_files.append(filepath)
            print(f"Fixed: {filepath.relative_to(project_root)}")
    
    print(f"\nCompleted! Modified {len(modified_files)} files.")
    
    if modified_files:
        print("\nModified files:")
        for f in modified_files:
            print(f"  - {f.relative_to(project_root)}")

if __name__ == "__main__":
    main()