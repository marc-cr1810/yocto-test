#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Show the last Yocto build error")
    parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    build_tmp_work = workspace_root / "bitbake-builds" / "poky-master" / "build" / "tmp" / "work"

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Latest Build Error Diagnosis{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    if not build_tmp_work.exists():
        print(f"  {RED}Error: Build work directory not found at {build_tmp_work}{NC}")
        sys.exit(1)

    print("  Searching for the latest failed task log...")
    
    # Search for log.do_* files recursively
    log_files = []
    try:
        # Check both tmp/work and tmp/work-shared
        search_dirs = [
            build_tmp_work,
            workspace_root / "bitbake-builds" / "poky-master" / "build" / "tmp" / "work-shared"
        ]
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for log_path in search_dir.glob("**/temp/log.do_*"):
                    # We only care about real files, not symlinks (unless they point to real files)
                    if log_path.is_file():
                        log_files.append(log_path)
    except Exception as e:
        print(f"  {RED}Error searching for logs: {e}{NC}")
        sys.exit(1)

    if not log_files:
        print(f"  {BOLD}Status       : No task logs found.{NC}")
        sys.exit(0)

    # Find the latest log by modification time
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)

    print(f"  Latest Log   : {BOLD}{latest_log.name}{NC}")
    print(f"  Path         : {latest_log}")
    print(f"{BOLD}{CYAN}--------------------------------------------------{NC}")

    # Check for actual errors in the log
    has_error = False
    try:
        with open(latest_log, "r") as f:
            lines = f.readlines()
            # Yocto logs usually have "ERROR:" or "FAILED" at the end of the line
            error_lines = [line for line in lines if "ERROR:" in line or "error:" in line.lower() or "FAILED" in line]
            
            if error_lines:
                has_error = True
                print(f"{RED}{BOLD}Detected Error Snippet:{NC}")
                # Show up to 15 lines around the first error or the last few lines
                for line in error_lines[-10:]:
                    print(line.strip())
            else:
                print(f"{BOLD}No obvious error markers in the latest log. End of file:{NC}")
                # Sometimes the error is at the end of the log without a specific marker
                for line in lines[-20:]:
                    print(line.strip())
    except Exception as e:
        print(f"  {RED}Could not read log file: {e}{NC}")

    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
