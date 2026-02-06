#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Simplify local development using Yocto's devtool")
    parser.add_argument("recipe", help="Recipe name to modify")
    parser.add_argument("--src", help="Source directory (defaults to current dir/sw/recipe)")
    parser.add_argument("--stop", action="store_true", help="Stop modifying (reset) the recipe")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Yocto Devtool Live-Edit Mode{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    print(f"{BOLD}{CYAN}=================================================={NC}")

    workspace_root = Path(__file__).resolve().parent.parent

    if args.stop:
        print(f"  Status       : Resetting {BOLD}{args.recipe}{NC}...")
        try:
            subprocess.run(["devtool", "reset", args.recipe], check=True, capture_output=True)
            print(f"\n{GREEN}Success! {args.recipe} is no longer in development mode.{NC}")
        except subprocess.CalledProcessError as e:
            print(f"  {RED}Error: {e.stderr.decode() if e.stderr else e}{NC}")
            sys.exit(1)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        sys.exit(0)

    # Finding the source
    if args.src:
        src_path = Path(args.src).resolve()
    else:
        src_path = workspace_root / "sw" / args.recipe

    if not src_path.exists():
        print(f"  {RED}Error: Source path {src_path} does not exist.{NC}")
        sys.exit(1)

    print(f"  Target       : {BOLD}{args.recipe}{NC}")
    print(f"  Source Path  : {src_path}")
    print(f"  Status       : Enabling development mode...")
    
    try:
        subprocess.run(["devtool", "modify", args.recipe, str(src_path)], check=True, capture_output=True)
        print(f"\n{GREEN}Success! Live-edit enabled.{NC}")
        print(f"  {BOLD}Edit Files   :{NC} {src_path}")
        print(f"  {BOLD}Rebuild Tool :{NC} Run '{GREEN}bitbake {args.recipe}{NC}'")
    except subprocess.CalledProcessError as e:
        print(f"  {RED}Error: {e.stderr.decode() if e.stderr else e}{NC}")
        print(f"\n  {BOLD}Note:{NC} Ensure BitBake environment is sourced.")
        sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
