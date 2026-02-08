#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check sanity of Yocto layers")
    parser.add_argument("--layer", help="Path to layer to check (default: auto-detect custom layer)")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    if args.layer:
         layer_dir = Path(args.layer).resolve()
    else:
         try:
             layer_dir = find_custom_layer(workspace_root)
         except RuntimeError as e:
             UI.print_error(str(e), fatal=True)
    
    def pass_label(text): return f"{UI.GREEN}[ PASS ]{UI.NC} {text}"
    def fail_label(text): return f"{UI.RED}[ FAIL ]{UI.NC} {text}"

    UI.print_header("Layer Sanity & Recipe Check")
    UI.print_item("Layer", layer_dir.name)
    
    errors = 0
    # ... (rest of the checks, update labels below)

    if errors == 0:
        print(f"\n{UI.GREEN}{UI.BOLD}Overall Status: HEALTHY{UI.NC}")
    else:
        print(f"\n{UI.RED}{UI.BOLD}Overall Status: {errors} ISSUE(S) FOUND{UI.NC}")
        sys.exit(1)
    
if __name__ == "__main__":
    main()
