#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI

def main():
    parser = argparse.ArgumentParser(description="Simplify local development using Yocto's devtool")
    parser.add_argument("recipe", help="Recipe name to modify")
    parser.add_argument("--src", help="Source directory (defaults to current dir/sw/recipe)")
    parser.add_argument("--stop", action="store_true", help="Stop modifying (reset) the recipe")
    args = parser.parse_args()

    UI.print_header("Yocto Devtool Live-Edit Mode")

    workspace_root = Path(__file__).resolve().parent.parent

    if args.stop:
        UI.print_item("Status", f"Resetting {UI.BOLD}{args.recipe}{UI.NC}...")
        try:
            subprocess.run(["devtool", "reset", args.recipe], check=True, capture_output=True)
            UI.print_success(f"{args.recipe} is no longer in development mode.")
        except subprocess.CalledProcessError as e:
            UI.print_error(f"{e.stderr.decode() if e.stderr else e}")
            sys.exit(1)
        sys.exit(0)

    # Finding the source
    if args.src:
        src_path = Path(args.src).resolve()
    else:
        src_path = workspace_root / "sw" / args.recipe

    if not src_path.exists():
        UI.print_error(f"Source path {src_path} does not exist.", fatal=True)

    UI.print_item("Target", args.recipe)
    UI.print_item("Source Path", str(src_path))
    UI.print_item("Status", "Enabling development mode...")
    
    try:
        subprocess.run(["devtool", "modify", args.recipe, str(src_path)], check=True, capture_output=True)
        UI.print_success("Live-edit enabled.")
        UI.print_item("Edit Files", str(src_path))
        print(f"  {UI.BOLD}Rebuild Tool :{UI.NC} Run '{UI.GREEN}yocto-build {args.recipe}{UI.NC}'")
    except subprocess.CalledProcessError as e:
        UI.print_error(f"{e.stderr.decode() if e.stderr else e}")
        print(f"\n  {UI.BOLD}Note:{UI.NC} Ensure BitBake environment is sourced.")
        sys.exit(1)
    
if __name__ == "__main__":
    main()
