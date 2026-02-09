#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_bitbake_yocto_dir

def get_latest_log(workspace_root):
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    build_tmp_work = bitbake_yocto_dir / "build" / "tmp" / "work"

    if not build_tmp_work.exists():
        UI.print_error(f"Build work directory not found at {build_tmp_work}", fatal=True)

    print("  Searching for the latest failed task log...")
    
    # Search for log.do_* files recursively
    log_files = []
    try:
        # Check both tmp/work and tmp/work-shared
        search_dirs = [
            build_tmp_work,
            bitbake_yocto_dir / "build" / "tmp" / "work-shared"
        ]
        
        for search_dir in search_dirs:
            if search_dir.exists():
                for log_path in search_dir.glob("**/temp/log.do_*"):
                    # We only care about real files, not symlinks (unless they point to real files)
                    if log_path.is_file():
                        log_files.append(log_path)
    except Exception as e:
        UI.print_error(f"Error searching for logs: {e}", fatal=True)

    if not log_files:
        UI.print_item("Status", "No task logs found.")
        sys.exit(0)

    # Find the latest log by modification time
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)

    UI.print_item("Latest Log", latest_log.name)
    UI.print_item("Path", str(latest_log))
    
    return latest_log

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Show the last Yocto build error")
    parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent

    UI.print_header("Latest Build Error Diagnosis")

    latest_log = get_latest_log(workspace_root)
    
    # Check for actual errors in the log
    has_error = False
    try:
        with open(latest_log, "r") as f:
            lines = f.readlines()
            # Yocto logs usually have "ERROR:" or "FAILED" at the end of the line
            error_lines = [line for line in lines if "ERROR:" in line or "error:" in line.lower() or "FAILED" in line]
            
            if error_lines:
                has_error = True
                print(f"{UI.RED}{UI.BOLD}Detected Error Snippet:{UI.NC}")
                # Show up to 15 lines around the first error or the last few lines
                for line in error_lines[-10:]:
                    print(line.strip())
            else:
                print(f"{UI.BOLD}No obvious error markers in the latest log. End of file:{UI.NC}")
                # Sometimes the error is at the end of the log without a specific marker
                for line in lines[-20:]:
                    print(line.strip())
    except Exception as e:
        UI.print_error(f"Could not read log file: {e}")

if __name__ == "__main__":
    main()
