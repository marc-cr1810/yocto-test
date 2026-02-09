#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
from pathlib import Path
from packaging.version import parse as parse_version
sys.path.insert(0, str(Path(__file__).resolve().parent))
from yocto_layer_index import LayerIndex, DEFAULT_BRANCH
from yocto_utils import (
    run_command as utils_run_command, 
    get_yocto_branch, 
    UI, 
    find_custom_layer,
    find_image_recipes,
    get_cached_image,
    set_cached_image,
    get_all_custom_layers,
    get_bitbake_yocto_dir,
    get_bblayers,
    get_active_layers,
    check_branch_compatibility
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = WORKSPACE_ROOT / "yocto" / "sources"
BUILD_DIR = get_bitbake_yocto_dir(WORKSPACE_ROOT) / "build"

def run_command(cmd, cwd=None, capture=False):
    try:
        if capture:
            return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, cwd=cwd).stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return True
    except subprocess.CalledProcessError as e:
        if capture:
            return None
        UI.print_error(f"Command failed: {cmd}")
        return False



def ensure_layer_recursive(index, layer_name, vcs_url, subdir, branch, visited=None):
    if visited is None:
        visited = set()
    
    if layer_name in visited:
        return True
    visited.add(layer_name)

    # Special handling for openembedded-core which is usually 'meta' or 'core'
    # we check if 'meta' exists in the poky directory to be sure it's core
    if layer_name == "openembedded-core" or layer_name == "meta":
        bitbake_yocto_dir = get_bitbake_yocto_dir(WORKSPACE_ROOT)
        core_path = bitbake_yocto_dir / "layers" / "openembedded-core" / "meta"
        
        active_layers = get_active_layers(WORKSPACE_ROOT)
        if "meta" in active_layers or "core" in active_layers or "meta-poky" in active_layers:
            UI.print_success(f"Skipping '{layer_name}' (provided by core/meta/poky)")
            return True
        
        # Also check if the path is actually in bblayers.conf even if names don't match exactly
        active_paths = [str(p.resolve()) for p in get_bblayers(WORKSPACE_ROOT)]
        if str(core_path.resolve()) in active_paths:
            UI.print_success(f"Skipping '{layer_name}' (path already in bblayers.conf)")
            return True

    UI.print_item("Checking layer", layer_name)
    
    # 1. Check if layer is active
    active_layers = get_active_layers(WORKSPACE_ROOT)
    if layer_name in active_layers:
        UI.print_success(f"Layer '{layer_name}' is already active")
        return True

    # 2. Get dependencies and ensure them first
    UI.print_item("Status", f"Resolving dependencies for '{layer_name}'...")
    
    layers_search = index.search_layers(layer_name)
    layer_item = None
    for l in layers_search:
        if l['name'] == layer_name:
            layer_item = l
            break
            
    if layer_item:
        deps = index.get_layer_dependencies(layer_item['id'])
        if deps:
            UI.print_item("Dependencies", ', '.join([d['name'] for d in deps]))
            for dep in deps:
                # Resolve details for dependency using the layer ID to find the correct LayerBranch
                dep_lb = index.get_layerbranch_for_layer(dep['id'])
                
                if dep_lb:
                    dep_vcs = dep_lb.get('vcs_url', dep.get('vcs_url'))
                    dep_subdir = dep_lb.get('vcs_subdir', '')
                    dep_branch = dep_lb.get('actual_branch') or branch 
                    
                    # Recursion
                    if not ensure_layer_recursive(index, dep['name'], dep_vcs, dep_subdir, dep_branch, visited):
                        return False
                else:
                    UI.print_warning(f"Could not resolve details for dependency '{dep['name']}'. Skipping.")
    else:
        UI.print_warning(f"Could not query layer details for '{layer_name}'. Dependencies might be missing.")

    # 3. Check if layer exists locally in sources/
    layer_path = SOURCES_DIR / layer_name
    if not layer_path.exists():
        UI.print_item("Action", f"Cloning '{layer_name}'...")
        SOURCES_DIR.mkdir(parents=True, exist_ok=True)
        
        repo_name = vcs_url.split('/')[-1].replace('.git', '')
        repo_path = SOURCES_DIR / repo_name
        
        if not repo_path.exists():
            print(f"  Cloning {repo_name} from {vcs_url} (branch: {branch})...")
            cmd = f"git clone --depth 1 -b {branch} {vcs_url} {repo_path}"
            if not run_command(cmd):
                UI.print_warning(f"Clone failed with branch '{branch}'. Trying 'master'...")
                cmd_master = f"git clone --depth 1 -b master {vcs_url} {repo_path}"
                if not run_command(cmd_master):
                    return False
        else:
             UI.print_item("Info", f"Repo '{repo_name}' exists, skipping clone.")
             
        if subdir:
             layer_path = repo_path / subdir
        else:
             layer_path = repo_path
             
    else:
         pass 

    # Re-eval layer path
    repo_name = vcs_url.split('/')[-1].replace('.git', '')
    repo_path = SOURCES_DIR / repo_name
    
    final_layer_path = repo_path
    if subdir:
        final_layer_path = repo_path / subdir
        
    # Check if we landed in a valid layer
    if not (final_layer_path / "conf" / "layer.conf").exists():
        if (repo_path / "conf" / "layer.conf").exists():
             final_layer_path = repo_path
        else:
             UI.print_warning(f"No layer.conf found at {final_layer_path}")

    UI.print_item("Registration", f"Syncing {final_layer_path.name}")
    
    # Use bitbake-layers with sourced environment
    bitbake_yocto_dir = get_bitbake_yocto_dir(WORKSPACE_ROOT)
    rel_yocto = bitbake_yocto_dir.relative_to(WORKSPACE_ROOT)
    cmd = f"source {rel_yocto}/layers/openembedded-core/oe-init-build-env {rel_yocto}/build && bitbake-layers add-layer {final_layer_path}"
    
    result = subprocess.run(cmd, shell=True, cwd=WORKSPACE_ROOT, executable="/bin/bash", capture_output=True, text=True)
    if result.returncode == 0:
        UI.print_success(f"Layer '{layer_name}' added successfully")
        return True
        
    UI.print_error(f"Failed to add layer '{layer_name}'.")
    if result.stdout:
        print(f"{UI.RED}{result.stdout}{UI.NC}")
    if result.stderr:
        print(f"{UI.RED}{result.stderr}{UI.NC}")
    return False

def add_to_image(recipe_name, image_name):
    """Placeholder or minimal implementation for add_to_image."""
    if not image_name:
        return
    UI.print_item("Adding to image", f"{recipe_name} -> {image_name}")
    from yocto_utils import add_package_to_image
    if add_package_to_image(WORKSPACE_ROOT, image_name, recipe_name):
        UI.print_success(f"Updated {image_name}")
    else:
        UI.print_error(f"Failed to update {image_name}")

def detect_target_image(args):
    """
    Detect the target image to add the package to.
    Priorities:
    1. --image argument
    2. Cached image (last used)
    3. First image found in first custom layer
    """
    if args.image:
        set_cached_image(WORKSPACE_ROOT, args.image)
        return args.image
        
    # Check cache
    cached = get_cached_image(WORKSPACE_ROOT)
    if cached:
        UI.print_item("Target Image", f"{cached} (cached)")
        return cached
        
    # Scan custom layers
    layers = get_all_custom_layers(WORKSPACE_ROOT)
    if not layers:
        return None
    
    for layer in layers:
        recipes = find_image_recipes(layer)
        if recipes:
            image = recipes[0]
            UI.print_item("Target Image", f"{image} (auto-detected from {layer.name})")
            set_cached_image(WORKSPACE_ROOT, image)
            return image
            
    return None

def main():
    default_branch = get_yocto_branch(WORKSPACE_ROOT)
    parser = argparse.ArgumentParser(description="Fetch and install recipes from OpenEmedded Layer Index")
    parser.add_argument("recipe", help="Recipe name to fetch")
    parser.add_argument("--image", help="Target image to add recipe to")
    parser.add_argument("--branch", default=default_branch, help=f"Yocto Branch (default: {default_branch})")
    args = parser.parse_args()

    UI.print_header("Yocto Recipe Installer")
    UI.print_item("Workspace Branch", default_branch)
    
    # Detect image early
    target_image = detect_target_image(args)

    # 1. Search
    UI.print_item("Searching", f"'{args.recipe}' in branch '{args.branch}'...")
    index = LayerIndex(branch=args.branch)
    if not index.get_branch_id():
        UI.print_error(f"Invalid branch '{args.branch}'", fatal=True)
        
    recipes = index.search_recipes(args.recipe)
    
    candidate = None
    
    # Filter for exact matches first
    exact_matches = [r for r in recipes if r['pn'] == args.recipe]
    
    potential_candidates = []
    
    if exact_matches:
        # Resolve info for all exact matches
        for r in exact_matches:
            info = index.get_recipe_layer_info(r)
            if info:
                 potential_candidates.append(info)
    elif recipes:
        # Fallback to fuzzy matches if no exact match
         for r in recipes:
            info = index.get_recipe_layer_info(r)
            if info:
                potential_candidates.append(info)

    if potential_candidates:
        # Sort by version (newest first)
        potential_candidates.sort(key=lambda x: parse_version(x['version']), reverse=True)
        candidate = potential_candidates[0]
                
    if not candidate:
        UI.print_error(f"Recipe '{args.recipe}' not found in branch '{args.branch}'", fatal=True)
        
    UI.print_item("Found", f"{UI.GREEN}{candidate['recipe_name']}{UI.NC} (layer: {UI.CYAN}{candidate['layer_name']}{UI.NC})")
    
    # Check branch compatibility
    if not check_branch_compatibility(WORKSPACE_ROOT, args.branch):
        UI.print_error("Cancelled due to branch mismatch.")
        return

    # 2. Ensure Layer (Recursive)
    if not ensure_layer_recursive(index, candidate['layer_name'], candidate['layer_vcs_url'], candidate['vcs_subdir'], candidate.get('actual_branch', args.branch)):
        UI.print_error("Failed to configure layer", fatal=True)
        
    # 3. Add to Image
    if target_image:
        add_to_image(candidate['recipe_name'], target_image)
    else:
        UI.print_warning("No target image detected or specified. Skipping add to image.")
    
    print(f"\n  {UI.BOLD}{UI.GREEN}Setup complete!{UI.NC}")
    if target_image:
         print(f"  Run {UI.CYAN}yocto-build {target_image}{UI.NC} to build.")
    else:
         print(f"  Run {UI.CYAN}yocto-build <your-image>{UI.NC} to build.")

if __name__ == "__main__":
    main()

