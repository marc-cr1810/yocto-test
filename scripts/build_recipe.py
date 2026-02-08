#!/usr/bin/env python3
import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_cached_image, find_custom_layer, find_image_recipes

def main():
    parser = argparse.ArgumentParser(description="Build a Yocto recipe or image")
    parser.add_argument("target", nargs="?", default=None, help="Recipe or image name to build (auto-detects image if not specified)")
    parser.add_argument("-c", "--clean", action="store_true", help="Clean before building")
    parser.add_argument("--cleansstate", action="store_true", help="Clean shared state before building")
    args = parser.parse_args()
    
    workspace_root = Path(__file__).resolve().parent.parent
    target = args.target
    
    # Auto-detect image if no target specified
    if target is None:
        UI.print_item("Status", "Auto-detecting image...")
        
        # Try to get cached image
        cached_image = get_cached_image(workspace_root)
        
        # Try to find layer and recipes
        try:
            layer_dir = find_custom_layer(workspace_root, None)
            recipes = find_image_recipes(layer_dir)
            
            if recipes:
                if cached_image and cached_image in recipes:
                    target = cached_image
                    UI.print_item("Selected", f"Last-used image: {target}")
                elif len(recipes) == 1:
                    target = recipes[0]
                    UI.print_item("Selected", f"Auto-detected: {target}")
                else:
                    # Multiple recipes, use cached or first
                    target = cached_image if (cached_image and cached_image in recipes) else recipes[0]
                    UI.print_item("Selected", target)
        except RuntimeError:
            pass
        
        if target is None:
            UI.print_error("No image found. Please specify a target.")
            print(f"  Usage: yocto-build <recipe-name>")
            sys.exit(1)
    
    UI.print_header("Yocto Build Manager")
    UI.print_item("Target", target)
    
    # Clean if requested
    if args.cleansstate:
        UI.print_item("Action", "Cleaning shared state...")
        subprocess.run(["bitbake", "-c", "cleansstate", target])
    elif args.clean:
        UI.print_item("Action", "Cleaning...")
        subprocess.run(["bitbake", "-c", "clean", target])
    
    # Build
    UI.print_item("Action", "Building...")
    result = subprocess.run(["bitbake", target])
    
    if result.returncode == 0:
        UI.print_success(f"Built {target}")
    else:
        UI.print_error(f"Build failed.")
        print(f"  Check logs with {UI.GREEN}yocto-err{UI.NC}")
        sys.exit(1)

if __name__ == "__main__":
    main()
