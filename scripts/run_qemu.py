#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_utils import (
    find_built_images,
    find_image_recipes,
    find_custom_layer,
    get_cached_image,
    set_cached_image,
    select_image_interactive
)

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Build and run QEMU image")
    parser.add_argument("image", nargs="?", default=None, help="Image to build and run (auto-detected if not specified)")
    parser.add_argument("--no-build", action="store_true", help="Skip build step")
    parser.add_argument("--interactive", action="store_true", help="Force interactive selection even with one image")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached image preference")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

    workspace_root = Path(__file__).resolve().parent.parent

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Building and Running QEMU (Headless){NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    # Smart image selection
    image_name = args.image
    
    if image_name is None:
        print(f"  {BOLD}Auto-detecting image...{NC}")
        
        # Get cached image if not disabled
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        
        # Find built images
        built_images = find_built_images(workspace_root)
        
        if built_images:
            # Use interactive selection if forced or multiple images
            if args.interactive or len(built_images) > 1:
                image_name = select_image_interactive(workspace_root, built_images, cached_image, purpose="run")
                if image_name is None:
                    print(f"{BOLD}{RED}No image selected. Exiting.{NC}")
                    sys.exit(1)
            else:
                # Single image - auto-select
                image_name = built_images[0]['name']
                print(f"  Auto-detected image: {BOLD}{image_name}{NC}")
        else:
            # No built images - check for recipes
            print(f"  {YELLOW}No built images found.{NC}")
            try:
                layer_dir = find_custom_layer(workspace_root)
                recipes = find_image_recipes(layer_dir)
                
                if recipes:
                    print(f"  Found image recipes: {', '.join(recipes)}")
                    if len(recipes) == 1:
                        image_name = recipes[0]
                        print(f"  Will build: {BOLD}{image_name}{NC}")
                    else:
                        print(f"\n  Please specify which image to build:")
                        for i, recipe in enumerate(recipes, 1):
                            print(f"    {i}. {recipe}")
                        sys.exit(1)
                else:
                    print(f"{BOLD}{RED}Error: No images or recipes found.{NC}")
                    print(f"  Run '{GREEN}yocto-image{NC}' to create an image recipe first.")
                    sys.exit(1)
            except RuntimeError as e:
                print(f"{BOLD}{RED}Error: {e}{NC}")
                sys.exit(1)

    # Freshness check
    freshness_threshold = 2 * 3600  # 2 hours in seconds
    if not args.no_build:
        built_images = find_built_images(workspace_root)
        for img in built_images:
            if img['name'] == image_name:
                age = time.time() - img['build_time']
                if age < freshness_threshold:
                    response = input(f"  {YELLOW}Image built recently. Rebuild? [y/N]:{NC} ").strip().lower()
                    if response not in ['y', 'yes']:
                        args.no_build = True
                        print(f"  Skipping build step.")
                break

    # Build step
    if not args.no_build:
        print(f"\n  Step 1: Building {BOLD}{image_name}{NC}...")
        try:
            subprocess.run(["bitbake", image_name], check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n{BOLD}{RED}Error building image: {e}{NC}")
            sys.exit(1)
    else:
        print(f"\n  Step 1: Building {BOLD}SKIPPED{NC}")

    # Launch QEMU
    print(f"\n  Step 2: Launching QEMU...")
    print(f"  {BOLD}Exit Command : Press Ctrl+A followed by X{NC}")
    try:
        subprocess.run(["runqemu", "snapshot", "nographic", image_name], check=True)
        
        # Update cache on successful run
        set_cached_image(workspace_root, image_name)
        
    except subprocess.CalledProcessError as e:
        print(f"\n{BOLD}{RED}Error running QEMU: {e}{NC}")
        sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
