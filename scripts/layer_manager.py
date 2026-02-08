#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_utils import (
    get_cached_layer,
    set_cached_layer,
    select_layer_interactive,
    get_all_custom_layers,
    run_command,
    UI
)

def main():
    parser = argparse.ArgumentParser(description="Manage local Yocto layers")
    parser.add_argument("--list", action="store_true", help="List active and available layers")
    parser.add_argument("--new", metavar="NAME", help="Scaffold a new local layer")
    parser.add_argument("--info", nargs="?", const="", metavar="LAYER", help="Show detailed info about a layer (auto-detect if not specified)")
    parser.add_argument("--recipes", nargs="?", const="", metavar="LAYER", help="List all recipes in a layer (auto-detect if not specified)")
    parser.add_argument("--interactive", action="store_true", help="Force interactive layer selection")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached layer preference")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    layers_base = workspace_root / "yocto" / "layers"
    
    UI.print_header("Yocto Layer Management")

    if args.new:
        scaffold_layer(args.new, layers_base)
        return

    # Handle --info command
    if args.info is not None:
        layer = get_layer_for_command(workspace_root, args.info, args.interactive, args.no_cache)
        if layer:
            show_layer_info(layer)
            set_cached_layer(workspace_root, layer.name)
        return

    # Handle --recipes command
    if args.recipes is not None:
        layer = get_layer_for_command(workspace_root, args.recipes, args.interactive, args.no_cache)
        if layer:
            list_layer_recipes(layer)
            set_cached_layer(workspace_root, layer.name)
        return

    if not layers_base.is_dir():
        UI.print_error(f"Layers directory not found: {layers_base}", fatal=True)

    # Default: Management Logic (Syncing layers)
    sync_layers(workspace_root, layers_base)

def get_layer_for_command(workspace_root, layer_arg, interactive, no_cache):
    """
    Get a layer for a command that operates on a single layer.
    Returns the layer Path or None if error.
    """
    all_layers = get_all_custom_layers(workspace_root)
    
    if not all_layers:
        UI.print_error("No custom layers found.")
        print(f"  Run 'yocto-layers --new <name>' to create a layer first.")
        return None
    
    # If layer explicitly specified
    if layer_arg:
        layer_name = layer_arg if layer_arg.startswith("meta-") else f"meta-{layer_arg}"
        for layer in all_layers:
            if layer.name == layer_name:
                return layer
        UI.print_error(f"Layer '{layer_name}' not found.")
        return None
    
    # Auto-detect layer
    cached_layer = None if no_cache else get_cached_layer(workspace_root)
    
    # Use interactive selection if forced or multiple layers
    if interactive or len(all_layers) > 1:
        return select_layer_interactive(workspace_root, all_layers, cached_layer)
    else:
        # Single layer - auto-select
        UI.print_item("Auto-detected", all_layers[0].name)
        return all_layers[0]

def show_layer_info(layer_path):
    """Show detailed information about a layer."""
    UI.print_item("Layer Name", layer_path.name)
    UI.print_item("Path", str(layer_path))
    
    # Count recipes by type
    recipe_dirs = {}
    total_recipes = 0
    
    for recipes_dir in layer_path.glob("recipes-*"):
        if recipes_dir.is_dir():
            category = recipes_dir.name.replace("recipes-", "")
            count = len(list(recipes_dir.glob("*/*.bb")))
            if count > 0:
                recipe_dirs[category] = count
                total_recipes += count
    
    UI.print_item("Total Recipes", str(total_recipes))
    
    if recipe_dirs:
        print(f"\n  {UI.BOLD}Recipe Categories:{UI.NC}")
        for category, count in sorted(recipe_dirs.items()):
            print(f"    {UI.GREEN}{category:<15}{UI.NC} : {count} recipes")
    
    # Check for layer.conf
    layer_conf = layer_path / "conf" / "layer.conf"
    if layer_conf.exists():
        UI.print_success("Layer configuration found")
    else:
        UI.print_warning("No layer.conf found")

def list_layer_recipes(layer_path):
    """List all recipes in a layer."""
    UI.print_item("Layer", layer_path.name)
    
    recipes_found = False
    
    for recipes_dir in sorted(layer_path.glob("recipes-*")):
        if recipes_dir.is_dir():
            category = recipes_dir.name.replace("recipes-", "")
            recipes = list(recipes_dir.glob("*/*.bb"))
            
            if recipes:
                recipes_found = True
                print(f"\n  {UI.BOLD}{category}:{UI.NC}")
                for recipe in sorted(recipes):
                    recipe_name = recipe.stem
                    print(f"    {UI.GREEN}{recipe_name}{UI.NC}")
    
    if not recipes_found:
        UI.print_warning("No recipes found in this layer.")

def sync_layers(workspace_root, layers_base):
    # Find local layers
    local_layers = [d for d in layers_base.iterdir() if d.is_dir() and d.name.startswith("meta-")]
    UI.print_item("Available", f"{len(local_layers)} local layers found")
    
    # Check currently active layers
    check_layers = run_command("bitbake-layers show-layers")
    
    if "ERROR: The BBPATH variable is not set" in check_layers:
        UI.print_error("BitBake environment not detected.")
        print(f"  Please source the environment first (e.g., 'source scripts/env_init.sh')")
        return

    active_layers = check_layers.splitlines()
    
    build_dir = workspace_root / "bitbake-builds" / "poky-master" / "build"
    
    for layer_path in local_layers:
        # Use relative path from build directory to layer for portability in bblayers.conf
        try:
            layer_rel_path = os.path.relpath(layer_path, build_dir)
        except ValueError:
            layer_rel_path = str(layer_path.resolve())
            
        layer_abs_path = str(layer_path.resolve())
        is_active = any(layer_abs_path in line for line in active_layers)
        
        if is_active:
            print(f"  Layer '{layer_path.name}' : {UI.GREEN}ACTIVE{UI.NC}")
        else:
            print(f"  Adding layer '{layer_path.name}'...")
            # Use relative path if possible
            output = run_command(f"bitbake-layers add-layer {layer_rel_path}", cwd=build_dir)
            if "ERROR" in output:
                UI.print_error(f"Failed to add layer: {output.strip()}")
            else:
                UI.print_success(f"Added layer '{layer_path.name}'")

    UI.print_header("Active Layer Configuration")
    # Extract only the summary from show-layers to keep output clean
    layers_summary = run_command("bitbake-layers show-layers")
    for line in layers_summary.splitlines():
        if line.startswith("meta-") or "layer" in line.lower():
            print(f"    {line}")

def scaffold_layer(name, layers_base):
    if not name.startswith("meta-"):
        name = f"meta-{name}"
    
    layer_dir = layers_base / name
    if layer_dir.exists():
        UI.print_error(f"Layer '{name}' already exists.")
        return

    UI.print_item("New Layer", name)
    UI.print_item("Status", "Creating directory structure...")
    
    # Create structure
    (layer_dir / "conf").mkdir(parents=True, exist_ok=True)
    
    # conf/layer.conf
    layer_conf_content = f"""# We have a conf and classes directory, add to BBPATH
BBPATH .= ":${{LAYERDIR}}"

# We have recipes-* directories, add to BBFILES
BBFILES += "${{LAYERDIR}}/recipes-*/*/*.bb \\
            ${{LAYERDIR}}/recipes-*/*/*.bbappend"

BBFILE_COLLECTIONS += "{name.replace('meta-', '')}"
BBFILE_PATTERN_{name.replace('meta-', '')} = "^${{LAYERDIR}}/"
BBFILE_PRIORITY_{name.replace('meta-', '')} = "6"

LAYERDEPENDS_{name.replace('meta-', '')} = "core"
LAYERSERIES_COMPAT_{name.replace('meta-', '')} = "whinlatter"
"""
    with open(layer_dir / "conf" / "layer.conf", "w") as f:
        f.write(layer_conf_content)

    # README
    with open(layer_dir / "README", "w") as f:
        f.write(f"This is the {name} layer.\n")

    UI.print_success(f"Layer scaffolded at: {layer_dir}")
    print(f"\n  {UI.BOLD}Next Steps:{UI.NC}")
    print(f"    Run 'yocto-layers' to register it with your build.")

if __name__ == "__main__":
    main()
