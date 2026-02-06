#!/usr/bin/env python3
"""
Helper utilities for Yocto workspace scripts.
Provides common functions like finding the custom layer automatically.
"""
from pathlib import Path
from typing import List, Optional
import re

def get_all_custom_layers(workspace_root: Path) -> List[Path]:
    """
    Get all custom layers in the workspace.
    Looks for layers in yocto/layers/ that are not standard Poky layers.
    
    Returns a list of custom layer paths (excluding meta-skeleton).
    """
    layers_dir = workspace_root / "yocto" / "layers"
    
    if not layers_dir.exists():
        return []
    
    # Standard/template layers to skip
    skip_layers = {"meta-skeleton", "meta-poky", "meta-yocto-bsp"}
    
    # Find all meta-* directories
    custom_layers = []
    for layer_path in layers_dir.iterdir():
        if layer_path.is_dir() and layer_path.name.startswith("meta-"):
            if layer_path.name not in skip_layers:
                # Verify it has a layer.conf to be valid
                if (layer_path / "conf" / "layer.conf").exists():
                    custom_layers.append(layer_path)
    
    return sorted(custom_layers, key=lambda p: p.name)

def find_custom_layer(workspace_root: Path, layer_name: Optional[str] = None) -> Path:
    """
    Find a custom layer in the workspace.
    
    Args:
        workspace_root: Root of the workspace
        layer_name: Optional layer name (with or without 'meta-' prefix).
                   If None, returns the first custom layer found.
    
    Returns the layer path.
    Raises RuntimeError if no custom layer is found or if specified layer doesn't exist.
    """
    custom_layers = get_all_custom_layers(workspace_root)
    
    if not custom_layers:
        raise RuntimeError(
            f"No custom layer found in {workspace_root / 'yocto' / 'layers'}. "
            f"Please create one using 'yocto-layers --new <name>'"
        )
    
    # If no layer specified, return the first one
    if layer_name is None:
        if len(custom_layers) > 1:
            layer_names = [l.name for l in custom_layers]
            print(f"  Note: Multiple layers found ({', '.join(layer_names)}), using {custom_layers[0].name}")
        return custom_layers[0]
    
    # Normalize layer name (add meta- prefix if missing)
    if not layer_name.startswith("meta-"):
        layer_name = f"meta-{layer_name}"
    
    # Find the specified layer
    for layer in custom_layers:
        if layer.name == layer_name:
            return layer
    
    # Layer not found
    available = [l.name for l in custom_layers]
    raise RuntimeError(
        f"Layer '{layer_name}' not found. Available custom layers: {', '.join(available)}"
    )

def get_machine_from_config(workspace_root: Path) -> Optional[str]:
    """
    Read the MACHINE variable from build/conf/local.conf.
    
    Returns the machine name or None if not found.
    """
    local_conf = workspace_root / "bitbake-builds" / "poky-master" / "build" / "conf" / "local.conf"
    
    if not local_conf.exists():
        return None
    
    try:
        with open(local_conf, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('MACHINE') and '=' in line:
                    # Parse MACHINE = "qemux86-64" or MACHINE ?= "qemux86-64"
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        value = parts[1].strip().strip('"').strip("'")
                        return value
    except Exception:
        pass
    
    return None

def find_built_images(workspace_root: Path, machine: Optional[str] = None) -> List[dict]:
    """
    Find all built images in the deploy directory.
    
    Args:
        workspace_root: Root of the workspace
        machine: Optional machine name. If None, auto-detected from local.conf
    
    Returns a list of dicts with keys: name, path, build_time, machine
    """
    if machine is None:
        machine = get_machine_from_config(workspace_root)
    
    if machine is None:
        return []
    
    deploy_dir = workspace_root / "bitbake-builds" / "poky-master" / "build" / "tmp" / "deploy" / "images" / machine
    
    if not deploy_dir.exists():
        return []
    
    images = {}
    
    # Look for image files with common extensions
    for pattern in ["*-image-*.wic", "*-image-*.ext4", "*-image-*.tar.bz2"]:
        for image_file in deploy_dir.glob(pattern):
            # Extract image name from filename
            # e.g., "core-image-falcon-qemux86-64.wic" -> "core-image-falcon"
            name = image_file.name
            
            # Remove machine suffix if present
            if f"-{machine}" in name:
                name = name.split(f"-{machine}")[0]
            
            # Remove extension
            for ext in ['.wic', '.ext4', '.tar.bz2', '.tar.gz']:
                if name.endswith(ext):
                    name = name[:-len(ext)]
            
            # Only keep if it looks like an image name (contains "-image-")
            if "-image-" not in name:
                continue
            
            # Keep the most recent file for each image name
            if name not in images or image_file.stat().st_mtime > images[name]['build_time']:
                images[name] = {
                    'name': name,
                    'path': image_file,
                    'build_time': image_file.stat().st_mtime,
                    'machine': machine
                }
    
    # Sort by build time (most recent first)
    return sorted(images.values(), key=lambda x: x['build_time'], reverse=True)

def find_image_recipes(layer_path: Path) -> List[str]:
    """
    Find all image recipes in a layer.
    
    Returns a list of image names (without .bb extension).
    """
    recipes_dir = layer_path / "recipes-images" / "images"
    
    if not recipes_dir.exists():
        return []
    
    recipes = []
    for recipe_file in recipes_dir.glob("*.bb"):
        # Only include files that look like image recipes
        if "-image-" in recipe_file.name or recipe_file.name.startswith("image-"):
            recipes.append(recipe_file.stem)
    
    return sorted(recipes)

def get_cached_image(workspace_root: Path) -> Optional[str]:
    """
    Read the last-used image from cache.
    
    Returns the image name or None if no cache exists.
    """
    cache_file = workspace_root / ".yocto-cache" / "last-image"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

def set_cached_image(workspace_root: Path, image_name: str):
    """
    Save the last-used image to cache.
    """
    cache_dir = workspace_root / ".yocto-cache"
    cache_dir.mkdir(exist_ok=True)
    
    cache_file = cache_dir / "last-image"
    
    try:
        with open(cache_file, 'w') as f:
            f.write(image_name)
    except Exception:
        pass  # Silently fail if we can't write cache

def format_time_ago(timestamp: float) -> str:
    """
    Format a timestamp as a human-readable 'time ago' string.
    """
    import time
    
    diff = time.time() - timestamp
    
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(diff / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

def select_image_interactive(workspace_root: Path, images: List[dict], cached_image: Optional[str] = None, purpose: str = "use") -> Optional[str]:
    """
    Interactive image selection UI.
    
    Args:
        workspace_root: Root of the workspace
        images: List of image dicts from find_built_images()
        cached_image: Optional cached image name to highlight
        purpose: Description of what the image will be used for (e.g., "build", "run")
    
    Returns the selected image name or None if cancelled.
    """
    if not images:
        return None
    
    # If only one image, auto-select
    if len(images) == 1:
        print(f"  Auto-detected image: {images[0]['name']}")
        return images[0]['name']
    
    # Multiple images - show interactive menu
    print(f"\n  Multiple images found:")
    
    default_choice = 1
    for i, img in enumerate(images, 1):
        time_str = format_time_ago(img['build_time'])
        cached_marker = " [last used]" if img['name'] == cached_image else ""
        print(f"    {i}. {img['name']:<30} (built: {time_str}){cached_marker}")
        
        # Default to cached image if present
        if img['name'] == cached_image:
            default_choice = i
    
    # Prompt for selection
    try:
        choice = input(f"\n  Select image [1-{len(images)}] or Enter for #{default_choice}: ").strip()
        
        if not choice:
            return images[default_choice - 1]['name']
        
        choice_num = int(choice)
        if 1 <= choice_num <= len(images):
            return images[choice_num - 1]['name']
        else:
            print(f"  Invalid choice. Using default.")
            return images[default_choice - 1]['name']
    except (ValueError, KeyboardInterrupt):
        print(f"\n  Selection cancelled.")
        return None

def get_cached_layer(workspace_root: Path) -> Optional[str]:
    """
    Read the last-used layer from cache.
    
    Returns the layer name or None if no cache exists.
    """
    cache_file = workspace_root / ".yocto-cache" / "last-layer"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

def set_cached_layer(workspace_root: Path, layer_name: str):
    """
    Save the last-used layer to cache.
    """
    cache_dir = workspace_root / ".yocto-cache"
    cache_dir.mkdir(exist_ok=True)
    
    cache_file = cache_dir / "last-layer"
    
    try:
        with open(cache_file, 'w') as f:
            f.write(layer_name)
    except Exception:
        pass  # Silently fail if we can't write cache

def select_layer_interactive(workspace_root: Path, layers: List[Path], cached_layer: Optional[str] = None) -> Optional[Path]:
    """
    Interactive layer selection UI.
    
    Args:
        workspace_root: Root of the workspace
        layers: List of layer paths from get_all_custom_layers()
        cached_layer: Optional cached layer name to highlight
    
    Returns the selected layer Path or None if cancelled.
    """
    if not layers:
        return None
    
    # If only one layer, auto-select
    if len(layers) == 1:
        print(f"  Auto-detected layer: {layers[0].name}")
        return layers[0]
    
    # Multiple layers - show interactive menu
    print(f"\n  Multiple custom layers found:")
    
    default_choice = 1
    for i, layer in enumerate(layers, 1):
        # Count recipes in layer
        recipe_count = 0
        recipes_dir = layer / "recipes-images" / "images"
        if recipes_dir.exists():
            recipe_count = len(list(recipes_dir.glob("*.bb")))
        
        # Also count other recipe directories
        for recipes_subdir in layer.glob("recipes-*"):
            if recipes_subdir.is_dir():
                recipe_count += len(list(recipes_subdir.glob("*/*.bb")))
        
        cached_marker = " [last used]" if layer.name == cached_layer else ""
        print(f"    {i}. {layer.name:<20} ({recipe_count} recipes){cached_marker}")
        
        # Default to cached layer if present
        if layer.name == cached_layer:
            default_choice = i
    
    # Prompt for selection
    try:
        choice = input(f"\n  Select layer [1-{len(layers)}] or Enter for #{default_choice}: ").strip()
        
        if not choice:
            return layers[default_choice - 1]
        
        choice_num = int(choice)
        if 1 <= choice_num <= len(layers):
            return layers[choice_num - 1]
        else:
            print(f"  Invalid choice. Using default.")
            return layers[default_choice - 1]
    except (ValueError, KeyboardInterrupt):
        print(f"\n  Selection cancelled.")
        return None

def add_package_to_image(workspace_root: Path, image_name: str, package_name: str) -> bool:
    """
    Add a package to an image recipe's IMAGE_INSTALL list.
    
    Args:
        workspace_root: Root of the workspace
        image_name: Name of the image (e.g., 'core-image-falcon')
        package_name: Name of the package to add
        
    Returns True if successful, False otherwise.
    """
    # Find the image recipe
    image_recipe = None
    for layer in get_all_custom_layers(workspace_root):
        potential_recipe = layer / "recipes-images" / "images" / f"{image_name}.bb"
        if potential_recipe.exists():
            image_recipe = potential_recipe
            break
            
    if not image_recipe:
        # Fallback: look for standard images if they are in meta-poky or similar, 
        # but usually we only want to modify custom ones.
        return False
        
    try:
        with open(image_recipe, 'r') as f:
            content = f.read()
            
        # Check if already present
        if f'"{package_name}"' in content or f' {package_name} ' in content or f' {package_name}\\' in content:
            return True
            
        # Look for IMAGE_INSTALL
        match = re.search(r'IMAGE_INSTALL\s*[?+:]?=\s*"(.*?)"', content, re.DOTALL)
        if match:
            original_val = match.group(0)
            inner_val = match.group(1).rstrip()
            
            # Decide how to append
            if '\\' in inner_val:
                # Multi-line format
                new_inner = inner_val
                if not new_inner.endswith('\\'):
                    new_inner += ' \\'
                new_inner += f'\n    {package_name} \\'
            else:
                # Single line
                new_inner = f"{inner_val} {package_name}"
                
            new_val = f'IMAGE_INSTALL += "{package_name}"' # Using += is safer and cleaner for appending
            
            # Actually, let's just append a new line with IMAGE_INSTALL:append = " package" 
            # or IMAGE_INSTALL += " package" at the end of the file or after the block.
            # But editing the existing block is more "workspace-like"
            
            # Simple approach: if IMAGE_INSTALL exists, append to file
            with open(image_recipe, 'a') as f:
                f.write(f'\nIMAGE_INSTALL += "{package_name}"\n')
            return True
        else:
            # No IMAGE_INSTALL found, let's just create a new += line
            with open(image_recipe, 'a') as f:
                f.write(f'\nIMAGE_INSTALL += "{package_name}"\n')
            return True
            
    except Exception as e:
        print(f"  Error updating image recipe: {e}")
        return False
