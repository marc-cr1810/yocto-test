#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

def get_dir_size(path):
    total = 0
    try:
        for p in path.rglob('*'):
            if p.is_file():
                total += p.stat().st_size
    except Exception:
        pass
    return total

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Safely clean up Yocto build artifacts")
    parser.add_argument("--force", action="store_true", help="Do not ask for confirmation (if implemented)")
    parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    build_dir = workspace_root / "bitbake-builds" / "poky-master" / "build"
    
    if not build_dir.exists():
        print(f"Error: Build directory {build_dir} not found.")
        sys.exit(1)

    # Directories to safely remove
    targets = [
        build_dir / "tmp" / "work",
        build_dir / "tmp" / "deploy",
        build_dir / "tmp" / "stamps",
        build_dir / "tmp" / "cache",
    ]

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Safe Yocto Build Cleanup{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    
    print(f"  {YELLOW}Warning: This will remove temporary build artifacts{NC}")
    print(f"           (sstate-cache and downloads are preserved){NC}\n")

    total_reclaimed = 0
    # ... (cleanup logic same)

    print(f"\n{GREEN}{BOLD}Cleanup Complete!{NC}")
    print(f"  Total Reclaimed : {BOLD}{format_size(total_reclaimed)}{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
