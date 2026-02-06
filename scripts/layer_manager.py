#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_utils import (
    get_all_custom_layers,
    get_cached_layer,
    set_cached_layer,
    select_layer_interactive
)

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e}\nOutput: {e.stdout}\nError: {e.stderr}"

def main():
    parser = argparse.ArgumentParser(description="Manage local Yocto layers")
    parser.add_argument("--list", action="store_true", help="List active and available layers")
    parser.add_argument("--new", metavar="NAME", help="Scaffold a new local layer")
    parser.add_argument("--info", nargs="?", const="", metavar="LAYER", help="Show detailed info about a layer (auto-detect if not specified)")
    parser.add_argument("--recipes", nargs="?", const="", metavar="LAYER", help="List all recipes in a layer (auto-detect if not specified)")
    parser.add_argument("--interactive", action="store_true", help="Force interactive layer selection")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cached layer preference")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'

    workspace_root = Path(__file__).resolve().parent.parent
    layers_base = workspace_root / "yocto" / "layers"
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Yocto Layer Management & Registration{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    if args.new:
        scaffold_layer(args.new, layers_base, BOLD, GREEN, CYAN, NC)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    # Handle --info command
    if args.info is not None:
        layer = get_layer_for_command(workspace_root, args.info, args.interactive, args.no_cache, BOLD, GREEN, RED, NC)
        if layer:
            show_layer_info(layer, BOLD, GREEN, CYAN, NC)
            set_cached_layer(workspace_root, layer.name)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    # Handle --recipes command
    if args.recipes is not None:
        layer = get_layer_for_command(workspace_root, args.recipes, args.interactive, args.no_cache, BOLD, GREEN, RED, NC)
        if layer:
            list_layer_recipes(layer, BOLD, GREEN, CYAN, NC)
            set_cached_layer(workspace_root, layer.name)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    if not layers_base.is_dir():
        print(f"  {RED}Error: {layers_base} not found{NC}")
        print(f"{BOLD}{CYAN}=================================================={NC}")
        sys.exit(1)

    # Default: Management Logic (Syncing layers)
    sync_layers(workspace_root, layers_base, BOLD, GREEN, RED, NC)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

def get_layer_for_command(workspace_root, layer_arg, interactive, no_cache, BOLD, GREEN, RED, NC):
    """
    Get a layer for a command that operates on a single layer.
    Returns the layer Path or None if error.
    """
    all_layers = get_all_custom_layers(workspace_root)
    
    if not all_layers:
        print(f"  {RED}Error: No custom layers found.{NC}")
        print(f"  Run '{GREEN}yocto-layers --new <name>{NC}' to create a layer first.")
        return None
    
    # If layer explicitly specified
    if layer_arg:
        layer_name = layer_arg if layer_arg.startswith("meta-") else f"meta-{layer_arg}"
        for layer in all_layers:
            if layer.name == layer_name:
                return layer
        print(f"  {RED}Error: Layer '{layer_name}' not found.{NC}")
        return None
    
    # Auto-detect layer
    cached_layer = None if no_cache else get_cached_layer(workspace_root)
    
    # Use interactive selection if forced or multiple layers
    if interactive or len(all_layers) > 1:
        return select_layer_interactive(workspace_root, all_layers, cached_layer)
    else:
        # Single layer - auto-select
        print(f"  Auto-detected layer: {BOLD}{all_layers[0].name}{NC}")
        return all_layers[0]

def show_layer_info(layer_path, BOLD, GREEN, CYAN, NC):
    """Show detailed information about a layer."""
    print(f"  Layer Name   : {BOLD}{layer_path.name}{NC}")
    print(f"  Path         : {layer_path}")
    
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
    
    print(f"  Total Recipes: {BOLD}{total_recipes}{NC}")
    
    if recipe_dirs:
        print(f"\n  {BOLD}Recipe Categories:{NC}")
        for category, count in sorted(recipe_dirs.items()):
            print(f"    {GREEN}{category:<15}{NC} : {count} recipes")
    
    # Check for layer.conf
    layer_conf = layer_path / "conf" / "layer.conf"
    if layer_conf.exists():
        print(f"\n  {GREEN}✓{NC} Layer configuration found")
    else:
        print(f"\n  {CYAN}⚠{NC} No layer.conf found")

def list_layer_recipes(layer_path, BOLD, GREEN, CYAN, NC):
    """List all recipes in a layer."""
    print(f"  Layer        : {BOLD}{layer_path.name}{NC}")
    
    recipes_found = False
    
    for recipes_dir in sorted(layer_path.glob("recipes-*")):
        if recipes_dir.is_dir():
            category = recipes_dir.name.replace("recipes-", "")
            recipes = list(recipes_dir.glob("*/*.bb"))
            
            if recipes:
                recipes_found = True
                print(f"\n  {BOLD}{category}:{NC}")
                for recipe in sorted(recipes):
                    recipe_name = recipe.stem
                    print(f"    {GREEN}{recipe_name}{NC}")
    
    if not recipes_found:
        print(f"\n  {CYAN}No recipes found in this layer.{NC}")

def sync_layers(workspace_root, layers_base, BOLD, GREEN, RED, NC):
    # Find local layers
    local_layers = [d for d in layers_base.iterdir() if d.is_dir() and d.name.startswith("meta-")]
    print(f"  Available     : {len(local_layers)} local layers found")
    
    # Check currently active layers
    check_layers = run_command("bitbake-layers show-layers")
    
    if "ERROR: The BBPATH variable is not set" in check_layers:
        print(f"\n  {RED}Error: BitBake environment not detected.{NC}")
        print(f"  Please source the environment first (e.g., '{GREEN}source scripts/env_init.sh{NC}')")
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
            print(f"  Layer '{layer_path.name}' : {GREEN}ACTIVE{NC}")
        else:
            print(f"  Adding layer '{layer_path.name}'...")
            # Use relative path if possible
            output = run_command(f"bitbake-layers add-layer {layer_rel_path}", cwd=build_dir)
            if "ERROR" in output:
                print(f"  {RED}[FAIL] Failed to add layer: {output.strip()}{NC}")
            else:
                print(f"  {GREEN}[SUCCESS] Added layer '{layer_path.name}'.{NC}")

    print(f"\n{BOLD}Active Layer Configuration:{NC}")
    # Extract only the summary from show-layers to keep output clean
    layers_summary = run_command("bitbake-layers show-layers")
    for line in layers_summary.splitlines():
        if line.startswith("meta-") or "layer" in line.lower():
            print(f"    {line}")

def scaffold_layer(name, layers_base, BOLD, GREEN, CYAN, NC):
    if not name.startswith("meta-"):
        name = f"meta-{name}"
    
    layer_dir = layers_base / name
    if layer_dir.exists():
        print(f"  {BOLD}Error        :{NC} Layer '{name}' already exists.")
        return

    print(f"  New Layer    : {BOLD}{name}{NC}")
    print(f"  Status       : Creating directory structure...")
    
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

    print(f"  {GREEN}Success! Layer scaffolded at:{NC}")
    print(f"    {layer_dir}")
    print(f"\n  {BOLD}Next Steps:{NC}")
    print(f"    Run '{GREEN}yocto-layers{NC}' to register it with your build.")

if __name__ == "__main__":
    main()
