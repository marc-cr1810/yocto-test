#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check sanity of Yocto layers")
    parser.add_argument("--layer", help="Path to layer to check (default: auto-detect custom layer)")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    if args.layer:
         layer_dir = Path(args.layer).resolve()
    else:
         sys.path.insert(0, str(Path(__file__).resolve().parent))
         from yocto_utils import find_custom_layer
         layer_dir = find_custom_layer(workspace_root)
    
    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    def pass_label(text): return f"{GREEN}[ PASS ]{NC} {text}"
    def fail_label(text): return f"{RED}[ FAIL ]{NC} {text}"

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Layer Sanity & Recipe Check{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    
    print(f"  Layer        : {BOLD}{layer_dir.name}{NC}")
    
    errors = 0
    # ... (rest of the checks, update labels below)

    if errors == 0:
        print(f"\n{GREEN}{BOLD}Overall Status: HEALTHY{NC}")
    else:
        print(f"\n{RED}{BOLD}Overall Status: {errors} ISSUE(S) FOUND{NC}")
        sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
