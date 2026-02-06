#!/usr/bin/env python3
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_utils import (
    find_custom_layer,
    find_image_recipes,
    get_cached_image,
    set_cached_image,
    get_all_custom_layers,
    get_cached_layer,
    set_cached_layer,
    select_layer_interactive
)

def main():
    import argparse
    
    # ANSI Colors (define early so they can be used throughout)
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'
    
    parser = argparse.ArgumentParser(description="Refresh the main image recipe with workspace packages")
    parser.add_argument("image", nargs="?", default=None, help="Target image recipe name (auto-detected if not specified)")
    parser.add_argument("--layer", help="Layer name to use (default: auto-detect)")
    parser.add_argument("--interactive", action="store_true", help="Force interactive selection even with one recipe/layer")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached image/layer preference")
    parser.add_argument("--layer-interactive", action="store_true", help="Force interactive layer selection")
    parser.add_argument("--layer-no-cache", action="store_true", help="Ignore cached layer preference")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    
    # Smart layer selection
    layer_dir = None
    if args.layer:
        # Explicit layer specified
        layer_dir = find_custom_layer(workspace_root, args.layer)
    else:
        # Auto-detect layer
        cached_layer = None if (args.no_cache or args.layer_no_cache) else get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            print(f"{BOLD}{RED}Error: No custom layers found.{NC}")
            print(f"  Run '{GREEN}yocto-layers --new <name>{NC}' to create a layer first.")
            sys.exit(1)
        
        # Use interactive selection if forced or multiple layers
        if args.interactive or args.layer_interactive or len(all_layers) > 1:
            layer_dir = select_layer_interactive(workspace_root, all_layers, cached_layer)
            if layer_dir is None:
                print(f"{BOLD}{RED}No layer selected. Exiting.{NC}")
                sys.exit(1)
        else:
            # Single layer - auto-select
            layer_dir = all_layers[0]
            print(f"  Auto-detected layer: {BOLD}{layer_dir.name}{NC}")

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Refreshing Image Recipe Content{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    # Smart recipe selection
    image_name = args.image
    
    if image_name is None:
        print(f"  {BOLD}Auto-detecting image recipe...{NC}")
        
        # Get cached image if not disabled
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        
        # Find existing recipes
        recipes = find_image_recipes(layer_dir)
        
        if recipes:
            if args.interactive or len(recipes) > 1:
                # Interactive selection
                print(f"\n  Multiple image recipes found:")
                
                default_choice = 1
                for i, recipe in enumerate(recipes, 1):
                    cached_marker = " [last used]" if recipe == cached_image else ""
                    print(f"    {i}. {recipe}{cached_marker}")
                    
                    if recipe == cached_image:
                        default_choice = i
                
                try:
                    choice = input(f"\n  Select recipe [1-{len(recipes)}] or Enter for #{default_choice}: ").strip()
                    
                    if not choice:
                        image_name = recipes[default_choice - 1]
                    else:
                        choice_num = int(choice)
                        if 1 <= choice_num <= len(recipes):
                            image_name = recipes[choice_num - 1]
                        else:
                            print(f"  Invalid choice. Using default.")
                            image_name = recipes[default_choice - 1]
                except (ValueError, KeyboardInterrupt):
                    print(f"\n  Selection cancelled. Using default.")
                    image_name = recipes[default_choice - 1]
            else:
                # Single recipe - auto-select
                image_name = recipes[0]
                print(f"  Auto-detected recipe: {BOLD}{image_name}{NC}")
        else:
            # No recipes - prompt for new name
            print(f"  {YELLOW}No existing image recipes found.{NC}")
            suggested_name = cached_image if cached_image else "test-image"
            
            response = input(f"  Create new recipe '{suggested_name}'? [Y/n]: ").strip().lower()
            if response in ['n', 'no']:
                custom_name = input(f"  Enter recipe name: ").strip()
                image_name = custom_name if custom_name else suggested_name
            else:
                image_name = suggested_name
            
            print(f"  Will create: {BOLD}{image_name}{NC}")
    
    # Handle .bb extension if provided
    if image_name.endswith(".bb"):
        image_name = image_name[:-3]
        
    image_recipe = layer_dir / "recipes-images" / "images" / f"{image_name}.bb"

    print(f"  Target Image : {BOLD}{image_name}{NC}")

    # Ensure image recipe directory exists
    image_recipe.parent.mkdir(parents=True, exist_ok=True)

    print("  Scanning for workspace packages...")
    packages = []
    sw_dir = workspace_root / "sw"
    if sw_dir.exists():
        for d in sw_dir.iterdir():
            if d.is_dir():
                # Check if it has a recipe in meta-test
                # We assume if it's in sw/, it's intended to be in the image
                # A robust check would look for the recipe file, but for now we trust the folder structure
                packages.append(d.name)
    
    # Sort for stability
    packages.sort()

    if not packages:
        print(f"  {BOLD}Status       : No workspace packages found.{NC}")
        # We might still want to create the empty image recipe if it doesn't exist
    else:
        print(f"  Status       : Found {len(packages)} packages: {', '.join(packages)}")

    # Construct recipe content
    # We always regenerate it to ensure it's up to date
    install_append = ""
    for p in packages:
        install_append += f"    {p} \\\n"
    
    recipe_content = f"""SUMMARY = "Custom minimal image {image_name}"
LICENSE = "MIT"

inherit core-image

# Minimal image configuration (like core-image-minimal)
IMAGE_INSTALL = "packagegroup-core-boot \\
{install_append}"

# Add SSH server
IMAGE_FEATURES += "ssh-server-dropbear"

# Keep image minimal
IMAGE_LINGUAS = ""
"""

    with open(image_recipe, "w") as f:
        f.write(recipe_content)

    print(f"\n{GREEN}Success! Updated image recipe at:{NC}")
    print(f"  Path         : {image_recipe}")
    print(f"\n{BOLD}Action Required:{NC}")
    print(f"  Run '{GREEN}bitbake {image_name}{NC}' to build the full image.")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    
    # Update caches on successful recipe update
    set_cached_image(workspace_root, image_name)
    set_cached_layer(workspace_root, layer_dir.name)

if __name__ == "__main__":
    main()
