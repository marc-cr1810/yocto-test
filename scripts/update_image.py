#!/usr/bin/env python3
import os
import sys
import re
import argparse
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import (
    UI,
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
            UI.print_error("No custom layers found.")
            print(f"  Run '{UI.GREEN}yocto-layers --new <name>{UI.NC}' to create a layer first.")
            sys.exit(1)
        
        # Use interactive selection if forced or multiple layers
        if args.interactive or args.layer_interactive or len(all_layers) > 1:
            layer_dir = select_layer_interactive(workspace_root, all_layers, cached_layer)
            if layer_dir is None:
                UI.print_error("No layer selected.", fatal=True)
        else:
            # Single layer - auto-select
            layer_dir = all_layers[0]
            UI.print_item("Layer", layer_dir.name)

    UI.print_header("Refreshing Image Recipe Content")

    # Smart recipe selection
    image_name = args.image
    
    if image_name is None:
        UI.print_item("Status", "Auto-detecting image recipe...")
        
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
                    print(f"      {i}. {recipe}{cached_marker}")
                    
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
                UI.print_item("Recipe", image_name)
        else:
            # No recipes - prompt for new name
            UI.print_warning("No existing image recipes found.")
            suggested_name = cached_image if cached_image else "test-image"
            
            response = input(f"  Create new recipe '{suggested_name}'? [Y/n]: ").strip().lower()
            if response in ['n', 'no']:
                custom_name = input(f"  Enter recipe name: ").strip()
                image_name = custom_name if custom_name else suggested_name
            else:
                image_name = suggested_name
            
            UI.print_item("Action", f"Creating {image_name}")
    
    # Handle .bb extension if provided
    if image_name.endswith(".bb"):
        image_name = image_name[:-3]
        
    image_recipe = layer_dir / "recipes-images" / "images" / f"{image_name}.bb"

    UI.print_item("Target Image", image_name)

    # Ensure image recipe directory exists
    image_recipe.parent.mkdir(parents=True, exist_ok=True)

    UI.print_item("Status", "Scanning for workspace packages...")
    packages = []
    sw_dir = workspace_root / "sw"
    
    # 1. Get all recipe names from the layer to validate against
    layer_recipe_names = set()
    for recipe_file in layer_dir.rglob("*.bb"):
        # Handle versioned recipes (e.g., example_1.0.bb -> example)
        stem = recipe_file.stem
        if "_" in stem:
            pn = stem.split("_")[0]
        else:
            pn = stem
        layer_recipe_names.add(pn)

    # 2. Walk sw/ recursively to find matching directories
    found_packages = set()
    if sw_dir.exists():
        for root, dirs, files in os.walk(sw_dir):
            for d in dirs:
                if d in layer_recipe_names:
                    found_packages.add(d)
                
    packages = sorted(list(found_packages))

    if not packages:
        UI.print_warning("No workspace packages found.")
    else:
        UI.print_item("Found", f"{len(packages)} workspace packages: {', '.join(packages)}")

    # 3. Read existing recipe to preserve manual additions
    preserved_packages = set()
    core_packages = {"packagegroup-core-boot"} # Always keep this
    
    if image_recipe.exists():
        with open(image_recipe, 'r') as f:
            content = f.read()
            
        match = re.search(r'IMAGE_INSTALL\s*=\s*"(.*?)"', content, re.DOTALL)
        if match:
            existing_val = match.group(1)
            clean_val = existing_val.replace('\\', ' ').replace('\n', ' ')
            existing_items = clean_val.split()
            
            for item in existing_items:
                item = item.strip()
                if item and item != "\\" and item not in packages and item not in core_packages:
                     preserved_packages.add(item)

    if preserved_packages:
        UI.print_item("Preserved", ', '.join(sorted(preserved_packages)))

    # Construct recipe content
    all_packages = sorted(list(core_packages)) + sorted(list(preserved_packages)) + packages
    
    install_lines = []
    for i, p in enumerate(all_packages):
         install_lines.append(f"    {p}")
    
    install_str = " \\\n".join(install_lines)
    
    recipe_content = f"""SUMMARY = "Custom minimal image {image_name}"
LICENSE = "MIT"

inherit core-image

# Minimal image configuration (like core-image-minimal)
IMAGE_INSTALL = "{install_str} \\
"

# Add SSH server
IMAGE_FEATURES += "ssh-server-dropbear"

# Keep image minimal
IMAGE_LINGUAS = ""
"""

    with open(image_recipe, "w") as f:
        f.write(recipe_content)

    UI.print_success("Updated image recipe")
    UI.print_item("Path", str(image_recipe))
    print(f"\n  Run '{UI.GREEN}yocto-build {image_name}{UI.NC}' to build the full image.")
    
    # Update caches on successful recipe update
    set_cached_image(workspace_root, image_name)
    set_cached_layer(workspace_root, layer_dir.name)

if __name__ == "__main__":
    main()
