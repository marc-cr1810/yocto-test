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
    select_layer_interactive,
    select_layer_interactive,
    scan_all_recipes,
    read_image_install,
    update_image_install,
    get_bitbake_yocto_dir
)

def get_image_recipe_path(workspace_root, args):
    """Resolve the target image recipe path."""
    # Smart layer selection
    layer_dir = None
    if args.layer:
        layer_dir = find_custom_layer(workspace_root, args.layer)
    else:
        cached_layer = None if (args.no_cache or args.layer_no_cache) else get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            UI.print_error("No custom layers found.")
            sys.exit(1)
        
        if args.interactive or args.layer_interactive or len(all_layers) > 1:
            layer_dir = select_layer_interactive(workspace_root, all_layers, cached_layer)
            if layer_dir is None:
                UI.print_error("No layer selected.", fatal=True)
        else:
            layer_dir = all_layers[0]

    # Smart recipe selection
    image_name = args.image
    
    if image_name is None:
        cached_image = None if args.no_cache else get_cached_image(workspace_root)
        recipes = find_image_recipes(layer_dir)
        
        if recipes:
            if args.interactive or len(recipes) > 1:
                if cached_image and cached_image in recipes and not args.interactive:
                    image_name = cached_image
                else: 
                     image_name = cached_image if (cached_image and cached_image in recipes) else recipes[0]
            else:
                image_name = recipes[0]
        else:
            UI.print_error("No image recipes found in layer.")
            sys.exit(1)

    if image_name.endswith(".bb"):
        image_name = image_name[:-3]
        
    image_recipe = layer_dir / "recipes-images" / "images" / f"{image_name}.bb"
    
    # Update caches
    set_cached_image(workspace_root, image_name)
    set_cached_layer(workspace_root, layer_dir.name)

    return image_recipe, image_name

def cmd_create(workspace_root, args):
    """Create a new image recipe."""
    image_name = args.image
    if not image_name:
        UI.print_error("Image name is required for creation.")
        sys.exit(1)
        
    # Layer selection
    layer_dir = None
    if args.layer:
        # Handle missing meta- prefix
        layer_name = args.layer
        if not layer_name.startswith("meta-"):
            layer_name = f"meta-{layer_name}"
        layer_dir = find_custom_layer(workspace_root, layer_name)
    else:
        cached_layer = None if (args.no_cache or args.layer_no_cache) else get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            UI.print_error("No custom layers found.")
            sys.exit(1)
            
        if args.interactive or args.layer_interactive or len(all_layers) > 1:
            layer_dir = select_layer_interactive(workspace_root, all_layers, cached_layer)
            if layer_dir is None:
                UI.print_error("No layer selected.", fatal=True)
        else:
            layer_dir = all_layers[0]

    # Target path
    images_dir = layer_dir / "recipes-images" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    recipe_path = images_dir / f"{image_name}.bb"
    
    if recipe_path.exists():
        UI.print_error(f"Image recipe '{image_name}' already exists in {layer_dir.name}.")
        sys.exit(1)
        
    # Create content
    content = f"""SUMMARY = "A custom image: {image_name}"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL = "packagegroup-core-boot ${{CORE_IMAGE_EXTRA_INSTALL}}"

IMAGE_LINGUAS = " "

"""
    with open(recipe_path, "w") as f:
        f.write(content)
        
    UI.print_success(f"Created image recipe: {recipe_path}")
    
    # Update cache
    set_cached_layer(workspace_root, layer_dir.name)

def get_current_image_info(workspace_root):
    """
    Helper to get current image info using simplified defaults (cached or auto-detect).
    Returns (recipe_path, image_name, packages_list) or raises Exception.
    """
    class Args:
        layer = None
        image = None
        no_cache = False
        layer_no_cache = False
        interactive = False
        layer_interactive = False
    
    args = Args()
    try:
        recipe_path, image_name = get_image_recipe_path(workspace_root, args)
        packages, _ = read_image_install(recipe_path)
        return recipe_path, image_name, packages
    except Exception as e:
        raise e

def cmd_list(workspace_root, args):
    recipe_path, name = get_image_recipe_path(workspace_root, args)
    UI.print_item("Image", name)
    
    packages, _ = read_image_install(recipe_path)
    UI.print_header(f"Installed Packages ({len(packages)})")
    for p in packages:
        print(f"  - {p}")

def cmd_available(workspace_root, args):
    UI.print_header("Scanning for Available Recipes...")
    recipes = scan_all_recipes(workspace_root)
    
    if args.filter:
        recipes = [r for r in recipes if args.filter in r]
        
    for r in recipes:
        print(f"  {r}")
    
    print(f"\n  Found {len(recipes)} recipes.")

def cmd_add(workspace_root, args):
    recipe_path, name = get_image_recipe_path(workspace_root, args)
    
    packages, content = read_image_install(recipe_path)
    
    added = []
    for pkg in args.packages:
        if pkg not in packages:
            packages.append(pkg)
            added.append(pkg)
        else:
            UI.print_warning(f"Package '{pkg}' already in image.")
            
    if added:
        update_image_install(recipe_path, packages, content)
        UI.print_success(f"Added: {', '.join(added)}")
    else:
        print("Nothing to add.")

def cmd_remove(workspace_root, args):
    recipe_path, name = get_image_recipe_path(workspace_root, args)
    
    packages, content = read_image_install(recipe_path)
    
    removed = []
    for pkg in args.packages:
        if pkg in packages:
            packages.remove(pkg)
            removed.append(pkg)
        else:
             UI.print_warning(f"Package '{pkg}' not found in image.")

    if removed:
        update_image_install(recipe_path, packages, content)
        UI.print_success(f"Removed: {', '.join(removed)}")
    else:
        print("Nothing to remove.")

def cmd_refresh(workspace_root, args):
    recipe_path, image_name = get_image_recipe_path(workspace_root, args)
    UI.print_item("Target Image", image_name)
    
    # Scan workspace
    UI.print_item("Status", "Scanning workspace packages...")
    sw_dir = workspace_root / "sw"
    
    all_recipes = set(scan_all_recipes(workspace_root))
    
    # workspace_pkgs are directories in sw/ that match a valid recipe name
    workspace_pkgs = []
    if sw_dir.exists():
        for item in sw_dir.iterdir():
            if item.is_dir() and item.name in all_recipes:
                workspace_pkgs.append(item.name)
    
    workspace_pkgs = sorted(workspace_pkgs)
    
    # Read existing
    current_pkgs, content = read_image_install(recipe_path)
    
    current_pkgs = sorted(list(set(current_pkgs))) # Deduplicate immediately to avoid double counting
    
    # Track changes
    added_count = 0
    removed_count = 0
    
    # 1. Add missing workspace packages
    for wp in workspace_pkgs:
        if wp not in current_pkgs:
            current_pkgs.append(wp)
            added_count += 1
            
    # 2. Remove packages that are no longer in workspace OR layer
    # We remove packages that are not valid recipes (orphan projects)
    
    UI.print_item("Status", "Verifying package validity...")
    all_known_recipes = set(scan_all_recipes(workspace_root))
    
    packages_to_keep = []
    for i, pkg in enumerate(current_pkgs):
        # Must preserve variables and groups that might not show up as simple recipes
        if "${" in pkg or pkg.startswith("packagegroup-") or pkg == "kernel-modules":
            packages_to_keep.append(pkg)
            continue
            
        # Check if it exists in the universe of recipes
        if pkg in all_known_recipes:
             packages_to_keep.append(pkg)
        else:
             UI.print_warning(f"Removing invalid package '{pkg}' (recipe not found)")
             removed_count += 1
             
    if added_count > 0 or removed_count > 0:
        update_image_install(recipe_path, packages_to_keep, content)
        if added_count > 0:
            UI.print_success(f"Added {added_count} new packages.")
        if removed_count > 0:
            UI.print_success(f"Removed {removed_count} invalid packages.")
    else:
        UI.print_success("Image is up to date.")

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto Image Content")
    
    # Shared arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("image", nargs="?", default=None, help="Target image (auto-detected)")
    parent_parser.add_argument("--layer", help="Target layer")
    parent_parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parent_parser.add_argument("--no-cache", action="store_true", help="Ignore cache")
    parent_parser.add_argument("--layer-interactive", action="store_true", help="Interactive layer mode")
    parent_parser.add_argument("--layer-no-cache", action="store_true", help="Ignore layer cache")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Subcommands
    cmd_refresh_p = subparsers.add_parser("refresh", parents=[parent_parser], help="Refresh workspace packages (Default)")
    
    cmd_add_p = subparsers.add_parser("add", parents=[parent_parser], help="Add package(s)")
    cmd_add_p.add_argument("packages", nargs="+", help="Package names to add")
    
    cmd_remove_p = subparsers.add_parser("remove", parents=[parent_parser], help="Remove package(s)")
    cmd_remove_p.add_argument("packages", nargs="+", help="Package names to remove")
    
    cmd_list_p = subparsers.add_parser("list", parents=[parent_parser], help="List installed packages")
    
    cmd_avail_p = subparsers.add_parser("available", parents=[parent_parser], help="List all available recipes")
    cmd_avail_p.add_argument("filter", nargs="?", help="Filter by name")

    cmd_create_p = subparsers.add_parser("create", parents=[parent_parser], help="Create a new image recipe")

    # If no arguments, default to 'refresh' command to ensure arguments are populated
    if len(sys.argv) == 1:
        args = parser.parse_args(['refresh'])
    # If arguments provided but not a known command, assume 'refresh' with args
    elif len(sys.argv) > 1 and sys.argv[1] not in ['refresh', 'add', 'remove', 'list', 'available', 'create', '-h', '--help']:
        args = parser.parse_args(['refresh'] + sys.argv[1:])
    else:
        args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    
    if args.command == 'refresh':
        cmd_refresh(workspace_root, args)
    elif args.command == 'add':
        cmd_add(workspace_root, args)
    elif args.command == 'remove':
        cmd_remove(workspace_root, args)
    elif args.command == 'list':
        cmd_list(workspace_root, args)
    elif args.command == 'available':
        cmd_available(workspace_root, args)
    elif args.command == 'create':
        cmd_create(workspace_root, args)

if __name__ == "__main__":
    main()
