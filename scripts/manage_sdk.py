#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
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
    parser = argparse.ArgumentParser(description="Manage Yocto cross-development SDKs")
    parser.add_argument("image", nargs="?", default=None, help="Image name to build SDK for (auto-detected if not specified)")
    parser.add_argument("--build", action="store_true", help="Build the SDK (populate_sdk)")
    parser.add_argument("--list", action="store_true", help="List generated SDK installers")
    parser.add_argument("--interactive", action="store_true", help="Force interactive selection even with one image")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached image preference")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    workspace_root = Path(__file__).resolve().parent.parent
    poky_dir = workspace_root / "bitbake-builds" / "poky-master"
    deploy_dir_sdk = poky_dir / "build" / "tmp" / "deploy" / "sdk"
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Yocto SDK & Toolchain Manager{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    if args.list:
        list_sdks(deploy_dir_sdk, BOLD, GREEN, NC)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    # Smart image selection
    image_name = args.image
    
    if image_name is None and args.build:
        print(f"  {BOLD}Auto-detecting image...{NC}")
        
        # Get cached image if not disabled
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        
        # Find built images
        built_images = find_built_images(workspace_root)
        
        if built_images:
            # Use interactive selection if forced or multiple images
            if args.interactive or len(built_images) > 1:
                image_name = select_image_interactive(workspace_root, built_images, cached_image, purpose="build SDK")
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
                        print(f"  Will use: {BOLD}{image_name}{NC}")
                    else:
                        print(f"\n  Please specify which image to use:")
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

    if args.build:
        if image_name is None:
            print(f"{BOLD}{RED}Error: No image specified or detected.{NC}")
            sys.exit(1)
        build_sdk(image_name, deploy_dir_sdk, workspace_root, BOLD, GREEN, NC)
    else:
        # Show usage
        if image_name:
            print(f"  Target Image : {BOLD}{image_name}{NC}")
        print(f"\n  {BOLD}Usage:{NC}")
        print(f"    yocto-sdk --build      : Build SDK for {'detected' if image_name is None else image_name} image")
        print(f"    yocto-sdk --list       : Show available installers")
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

def list_sdks(deploy_dir_sdk, BOLD, GREEN, NC):
    print(f"  {BOLD}Available SDK Installers:{NC}")
    
    if not deploy_dir_sdk.exists():
        print(f"    (No SDKs found in {deploy_dir_sdk})")
        return

    count = 0
    for sdk_file in deploy_dir_sdk.glob("*.sh"):
        print(f"    {GREEN}{sdk_file.name}{NC}")
        print(f"      Path: {sdk_file}")
        count += 1
    
    if count == 0:
        print(f"    (No .sh installers found in {deploy_dir_sdk})")

def build_sdk(image_name, deploy_dir_sdk, workspace_root, BOLD, GREEN, NC):
    print(f"  Target Image : {BOLD}{image_name}{NC}")
    print(f"  Action       : Running populate_sdk (this will take time)...")
    
    try:
        # We assume bitbake is in PATH (env sourced)
        subprocess.run(["bitbake", "-c", "populate_sdk", image_name], check=True)
        
        print(f"\n{GREEN}Success! SDK generated.{NC}")
        print(f"  {BOLD}Installers available in:{NC}")
        print(f"    {deploy_dir_sdk}")
        
        # Update cache on successful SDK build
        set_cached_image(workspace_root, image_name)
        
    except subprocess.CalledProcessError as e:
        print(f"\n  {BOLD}Error:{NC} SDK generation failed.")
        print(f"  Ensure BitBake environment is sourced and local layers are healthy.")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\n  {BOLD}Error:{NC} BitBake command not found.")
        print(f"  Please source and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
