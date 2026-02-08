#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_utils import (
    UI,
    find_built_images,
    find_image_recipes,
    find_custom_layer,
    get_cached_image,
    set_cached_image,
    select_image_interactive
)

def list_sdks(deploy_dir_sdk):
    UI.print_item("Status", "Checking for SDK installers...")
    
    if not deploy_dir_sdk.exists():
        UI.print_warning(f"No SDKs found in {deploy_dir_sdk}")
        return

    count = 0
    for sdk_file in deploy_dir_sdk.glob("*.sh"):
        UI.print_item("Installer", sdk_file.name)
        print(f"      Path: {sdk_file}")
        count += 1
    
    if count == 0:
        UI.print_warning(f"No .sh installers found in {deploy_dir_sdk}")

def build_sdk(image_name, deploy_dir_sdk, workspace_root):
    UI.print_item("Target Image", image_name)
    UI.print_item("Action", "Running populate_sdk (this may take 15-30+ minutes)...")
    
    try:
        # We assume bitbake is in PATH (env sourced)
        subprocess.run(["bitbake", "-c", "populate_sdk", image_name], check=True)
        
        UI.print_success("SDK generation complete")
        UI.print_item("Location", str(deploy_dir_sdk))
        
        # Update cache on successful SDK build
        set_cached_image(workspace_root, image_name)
        
    except subprocess.CalledProcessError:
        UI.print_error("SDK generation failed.")
        print(f"  Ensure BitBake environment is sourced and local layers are healthy.")
        sys.exit(1)
    except FileNotFoundError:
        UI.print_error("BitBake command not found.")
        print(f"  Please source environment (e.g. 'source scripts/env_init.sh') and try again.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto cross-development SDKs")
    parser.add_argument("image", nargs="?", default=None, help="Image name to build SDK for (auto-detected if not specified)")
    parser.add_argument("--build", action="store_true", help="Build the SDK (populate_sdk)")
    parser.add_argument("--list", action="store_true", help="List generated SDK installers")
    parser.add_argument("--interactive", action="store_true", help="Force interactive selection even with one image")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached image preference")
    args = parser.parse_args()

    UI.print_header("Yocto SDK Manager")

    workspace_root = Path(__file__).resolve().parent.parent
    poky_dir = workspace_root / "bitbake-builds" / "poky-master"
    deploy_dir_sdk = poky_dir / "build" / "tmp" / "deploy" / "sdk"

    if args.list:
        list_sdks(deploy_dir_sdk)
        return

    # Smart image selection
    image_name = args.image
    
    if image_name is None and args.build:
        UI.print_item("Status", "Auto-detecting image...")
        
        # Get cached image if not disabled
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        
        # Find built images
        built_images = find_built_images(workspace_root)
        
        if built_images:
            # Use interactive selection if forced or multiple images
            if args.interactive or len(built_images) > 1:
                image_name = select_image_interactive(workspace_root, built_images, cached_image, purpose="build SDK")
                if image_name is None:
                    UI.print_error("No image selected.", fatal=True)
            else:
                # Single image - auto-select
                image_name = built_images[0]['name']
                UI.print_item("Auto-detected image", image_name)
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
                            print(f"    - {recipe}")
                        sys.exit(1)
                else:
                    UI.print_error("No images or recipes found.")
                    print(f"  Run 'yocto-image' to create an image recipe first.")
                    sys.exit(1)
            except RuntimeError as e:
                UI.print_error(str(e), fatal=True)

    if args.build:
        if image_name is None:
            UI.print_error("No image specified or detected.", fatal=True)
        build_sdk(image_name, deploy_dir_sdk, workspace_root)
    else:
        # Show usage
        if image_name:
            UI.print_item("Target Image", image_name)
        print(f"\n  {UI.BOLD}Commands:{UI.NC}")
        print(f"    --build      Build SDK package")
        print(f"    --list       Show installers")

if __name__ == "__main__":
    main()
