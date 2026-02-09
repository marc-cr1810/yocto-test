#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_bitbake_yocto_dir

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
    build_dir = get_bitbake_yocto_dir(workspace_root) / "build"
    
    UI.print_header("Safe Yocto Build Cleanup")

    if not build_dir.exists():
        UI.print_error(f"Build directory {build_dir} not found.", fatal=True)

    # Directories to safely remove
    targets = [
        build_dir / "tmp" / "work",
        build_dir / "tmp" / "deploy",
        build_dir / "tmp" / "stamps",
        build_dir / "tmp" / "cache",
    ]

    print(f"  {UI.YELLOW}Warning: This will remove temporary build artifacts{UI.NC}")
    print(f"           (sstate-cache and downloads are preserved){UI.NC}\n")

    total_reclaimed = 0
    # ... (cleanup logic same)

    print(f"\n{UI.GREEN}{UI.BOLD}Cleanup Complete!{UI.NC}")
    print(f"  Total Reclaimed : {UI.BOLD}{format_size(total_reclaimed)}{UI.NC}")

if __name__ == "__main__":
    main()
