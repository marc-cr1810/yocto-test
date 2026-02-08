#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import time
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import (
    UI,
    find_built_images,
    find_image_recipes,
    find_custom_layer,
    get_cached_image,
    set_cached_image,
    select_image_interactive
)

def main():
    parser = argparse.ArgumentParser(description="Build and run QEMU image")
    parser.add_argument("image", nargs="?", default=None, help="Image to build and run (auto-detected if not specified)")
    parser.add_argument("--no-build", action="store_true", help="Skip build step")
    parser.add_argument("--interactive", action="store_true", help="Force interactive selection even with one image")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached image preference")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent

    UI.print_header("Building and Running QEMU (Headless)")

    # Smart image selection
    image_name = args.image
    
    if image_name is None:
        UI.print_item("Status", "Auto-detecting image...")
        
        # Get cached image if not disabled
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        
        # Find built images
        built_images = find_built_images(workspace_root)
        
        if built_images:
            # Use interactive selection if forced or multiple images
            if args.interactive or len(built_images) > 1:
                image_name = select_image_interactive(workspace_root, built_images, cached_image, purpose="run")
                if image_name is None:
                    UI.print_error("No image selected.", fatal=True)
            else:
                # Single image - auto-select
                image_name = built_images[0]['name']
                UI.print_item("Selected image", image_name)
        else:
            # No built images - check for recipes
            UI.print_warning("No built images found. Searching for recipes...")
            try:
                layer_dir = find_custom_layer(workspace_root)
                recipes = find_image_recipes(layer_dir)
                
                if recipes:
                    if len(recipes) == 1:
                        image_name = recipes[0]
                        UI.print_item("Selected recipe", image_name)
                    else:
                        UI.print_error("Multiple image recipes found. Please specify one.")
                        for recipe in recipes:
                            print(f"      - {recipe}")
                        sys.exit(1)
                else:
                    UI.print_error("No images or recipes found.")
                    print(f"  Run 'yocto-image' to create an image recipe first.")
                    sys.exit(1)
            except RuntimeError as e:
                UI.print_error(str(e), fatal=True)

    # Freshness check
    freshness_threshold = 2 * 3600  # 2 hours in seconds
    if not args.no_build:
        built_images = find_built_images(workspace_root)
        for img in built_images:
            if img['name'] == image_name:
                age = time.time() - img['build_time']
                if age < freshness_threshold:
                    response = input(f"  {UI.YELLOW}[WARN]{UI.NC} Image built recently ({int(age/60)}m ago). Rebuild? [y/N]: ").strip().lower()
                    if response not in ['y', 'yes']:
                        args.no_build = True
                        UI.print_item("Build", "Skipped (recently built)")
                break

    # Build step
    if not args.no_build:
        UI.print_item("Step 1", f"Building {image_name}...")
        try:
            subprocess.run(["bitbake", image_name], check=True)
        except subprocess.CalledProcessError:
            UI.print_error("Building image failed.")
            sys.exit(1)
    else:
        UI.print_item("Step 1", "Building SKIPPED")

    # Launch QEMU
    UI.print_item("Step 2", "Launching QEMU...")
    UI.print_item("Exit Command", "Press Ctrl+A followed by X")
    
    try:
        subprocess.run(["runqemu", "snapshot", "nographic", image_name], check=True)
        
        # Update cache on successful run
        set_cached_image(workspace_root, image_name)
        
    except subprocess.CalledProcessError:
        UI.print_error("Running QEMU failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
