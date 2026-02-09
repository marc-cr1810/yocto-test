#!/usr/bin/env python3
"""
Helper utilities for Yocto workspace scripts.
Provides common functions like finding the custom layer automatically.
"""
from pathlib import Path
from typing import List, Optional
import re
import subprocess
import sys
import json

def get_bitbake_yocto_dir(workspace_root: Path) -> Path:
    """
    Dynamically find the BitBake/Yocto distribution directory in bitbake-builds/.
    Returns the path to the first poky-* or oe-* directory found.
    Defaults to workspace_root / 'bitbake-builds' / 'poky-master' if not found.
    """
    try:
        # Search for both poky-* and oe-*
        build_roots = list((workspace_root / "bitbake-builds").glob("poky-*"))
        build_roots.extend(list((workspace_root / "bitbake-builds").glob("oe-*")))
        
        if build_roots:
            return build_roots[0]
    except Exception:
        pass
    return workspace_root / "bitbake-builds" / "poky-master"

class UI:
    """Centralized UI styling and output utilities."""
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    DIM = '\033[2m'
    NC = '\033[0m' # No Color
    
    # Handle environment without color
    if not sys.stdout.isatty():
        BOLD = CYAN = GREEN = RED = YELLOW = DIM = NC = ''

    @classmethod
    def print_header(cls, text: str):
        """Print a clean, professional header."""
        print(f"\n{cls.BOLD}{cls.CYAN}# {text}{cls.NC}")

    @classmethod
    def print_success(cls, text: str):
        """Print a success message."""
        print(f"  {cls.GREEN}[OK]{cls.NC} {text}")

    @classmethod
    def print_warning(cls, text: str):
        """Print a warning message."""
        print(f"  {cls.YELLOW}[WARN]{cls.NC} {text}")

    @classmethod
    def print_error(cls, text: str, fatal: bool = False):
        """Print an error message."""
        print(f"  {cls.RED}[ERROR]{cls.NC} {text}")
        if fatal:
            sys.exit(1)

    @classmethod
    def print_item(cls, label: str, value: str = "", indent: int = 1):
        """Print a labeled data item."""
        spaces = "  " * indent
        if value:
            print(f"{spaces}{cls.DIM}{label:14}:{cls.NC} {cls.BOLD}{value}{cls.NC}")
        else:
            print(f"{spaces}{cls.BOLD}{label}{cls.NC}")

    @classmethod
    def print_footer(cls):
        """Minimal footer to separate sections if needed."""
        # Optional: could be empty or a subtle divider
        pass

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Return error details so caller can handle or display them
        return f"ERROR: {e}\nOutput: {e.stdout}\nError: {e.stderr}"

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
    # Layer not found
    available = [l.name for l in custom_layers]
    raise RuntimeError(
        f"Layer '{layer_name}' not found. Available custom layers: {', '.join(available)}"
    )

def get_available_machines(workspace_root: Path) -> dict:
    """
    Get all available machines from Poky and local layers.
    Returns a dict with keys 'poky' and 'custom', each containing a list of machine names.
    """
    machines = {'poky': [], 'custom': []}
    
    # 1. Scan Yocto Distribution
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    meta_dir = bitbake_yocto_dir / "layers" / "openembedded-core" / "meta"
    if meta_dir.exists():
        for m in (meta_dir / "conf" / "machine").glob("*.conf"):
            machines['poky'].append(m.stem)
            
    # 2. Scan Custom Layers
    layers_dir = workspace_root / "yocto" / "layers"
    if layers_dir.exists():
        for m in layers_dir.rglob("conf/machine/*.conf"):
            # Exclude anything that might be in a nested poky repo if it exists (sanity check)
            if "openembedded-core" not in str(m):
                machines['custom'].append(m.stem)

    # 3. Scan Sources (External Layers)
    sources_dir = workspace_root / "yocto" / "sources"
    if sources_dir.exists():
        for m in sources_dir.rglob("conf/machine/*.conf"):
            # Avoid duplicates if they somehow exist in both
            if m.stem not in machines['custom'] and m.stem not in machines['poky']:
                 machines['custom'].append(m.stem)
                
    machines['poky'].sort()
    machines['custom'].sort()
    return machines

def get_bblayers(workspace_root: Path) -> List[Path]:
    """
    Parse bblayers.conf to get a list of active layer paths.
    """
    bblayers_conf = get_bitbake_yocto_dir(workspace_root) / "build" / "conf" / "bblayers.conf"
    layers = []
    
    if not bblayers_conf.exists():
        return []
        
    try:
        content = bblayers_conf.read_text()
        # Extract paths between quotes or just listed
        # Typical format: BBLAYERS ?= " \n /path/to/layer \n "
        
        # Simple regex to find paths - assumes absolute paths or handling by caller
        # Look for lines that look like paths inside the variable definition
        # Actually, let's just find strings that look like paths
        
        # Robust parsing: look for BBLAYERS variable
        match = re.search(r'BBLAYERS\s*\??=\s*"(.*?)"', content, re.DOTALL)
        if match:
             raw_paths = match.group(1).split()
             for p in raw_paths:
                 if p.strip() and p != "\\":
                     layers.append(Path(p.strip()))
    except Exception:
        pass
        
    return layers

def scan_all_recipes(workspace_root: Path) -> List[str]:
    """
    Scan all active layers for available recipes using bitbake-layers.
    Returns a sorted list of recipe names.
    """
    # Use bitbake-layers for authoritative source
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    rel_yocto = bitbake_yocto_dir.relative_to(workspace_root)
    cmd = f"source {rel_yocto}/layers/openembedded-core/oe-init-build-env {rel_yocto}/build && bitbake-layers show-recipes"
    
    try:
        # Check if we can run bitbake-layers (env might be tricky from python wrapper if not set)
        # We rely on run_command but we need to source env first.
        # Note: This might be slow (5-10s).
        
        # We use a shell command with verify=False to avoid crashing if it fails
        # USE /bin/bash explicitly to support 'source'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=workspace_root, executable="/bin/bash")
        
        if result.returncode != 0:
            # Fallback to manual scan if bitbake fails (e.g. parsing error)
            UI.print_warning("bitbake-layers failed, falling back to manual scan.")
            return _scan_all_recipes_manual(workspace_root)
            
        output = result.stdout
        recipes = set()
        
        for line in output.splitlines():
            # Output format:
            # recipe-name:
            #   layer-name       version
            if line.endswith(':'):
                name = line[:-1].strip()
                # Filter out garbage or non-recipe lines that might randomly end in :
                if ' ' not in name and '/' not in name:
                     recipes.add(name)
                     
        return sorted(list(recipes))
        
    except Exception as e:
        UI.print_warning(f"Error scanning recipes: {e}")
        return _scan_all_recipes_manual(workspace_root)

def _scan_all_recipes_manual(workspace_root: Path) -> List[str]:
    """Fallback manual scanner"""
    layers = get_bblayers(workspace_root)
    recipes = set()
    
    for layer in layers:
        if not layer.exists():
            continue
            
        for recipe_file in layer.rglob("*.bb"):
            if recipe_file.suffix == ".bb":
                # Try to be smarter about PN
                # If content has PN = "name", use it?
                # This is expensive to read all files.
                # Just blindly look for matching patterns
                stem = recipe_file.stem
                
                # If filename has _v, assume it is version separator?
                # BitBake default: first underscore.
                # But we can try to guess if it matches standard patterns.
                parts = stem.split('_')
                if len(parts) > 1:
                    name = parts[0]
                    # ALSO add the full stem just in case? No.
                    # Add strictly name.
                    recipes.add(name)
                    
                    # ALSO add the name assuming the override exists?
                    # Example: legs_main_1.0 -> legs_main
                    # If we can't read the file, we can't know.
                    # But we can add heuristics: if part[1] is NOT a number?
                    # legs_main_1.0 -> main is not number.
                    # So maybe 'legs_main' is the name?
                    # logic: name ends at first part that starts with digit?
                    
                    candidate = parts[0]
                    for i in range(1, len(parts)):
                        if parts[i][0].isdigit():
                            break
                        candidate += "_" + parts[i]
                    recipes.add(candidate)
                else:
                    recipes.add(stem)
                
    return sorted(list(recipes))

def get_machine_from_config(workspace_root: Path) -> Optional[str]:
    """
    Read the MACHINE variable from build/conf/local.conf.
    
    Returns the machine name or None if not found.
    """
    local_conf = get_bitbake_yocto_dir(workspace_root) / "build" / "conf" / "local.conf"
    
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
    
    deploy_dir = get_bitbake_yocto_dir(workspace_root) / "build" / "tmp" / "deploy" / "images" / machine
    
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

def read_image_install(recipe_path: Path):
    """
    Read the IMAGE_INSTALL variable from a recipe.
    Returns (packages_list, original_content).
    """
    if not recipe_path.exists():
        return [], ""
    
    with open(recipe_path, 'r') as f:
        content = f.read()
        
    # Regex to find all IMAGE_INSTALL lines
    # Matches: IMAGE_INSTALL = "...", IMAGE_INSTALL += "...", IMAGE_INSTALL:append = "..."
    # Captures the value inside quotes
    matches = re.findall(r'IMAGE_INSTALL(?:[:_\w]+)?\s*[+:]?=\s*"(.*?)"', content, re.DOTALL)
    
    packages = []
    for raw in matches:
        clean = raw.replace('\\', ' ').replace('\n', ' ')
        for p in clean.split():
            if p.strip():
                packages.append(p.strip())
        
    return packages, content

def update_image_install(recipe_path: Path, packages: List[str], original_content: str) -> bool:
    """
    Rewrite the IMAGE_INSTALL variable in a recipe with the new list of packages.
    """
    sorted_packages = sorted(list(set(packages))) # Dedup and sort
    
    # Format cleanly
    install_lines = []
    for p in sorted_packages:
         install_lines.append(f"    {p}")
    install_str = " \\\n".join(install_lines)
    
    # Construct new block
    new_block = f'IMAGE_INSTALL = "{install_str} \\\n"'
    
    # regex to match valid IMAGE_INSTALL lines
    pattern = r'IMAGE_INSTALL(?:[:_\w]+)?\s*[+:]?=\s*".*?"'
    
    # Check if we have any matches
    if not re.search(pattern, original_content, re.DOTALL):
        # Determine where to add
        # Try to find inherit line
        if "inherit core-image" in original_content:
            new_content = original_content.replace("inherit core-image", f"inherit core-image\n\n{new_block}")
        else:
            new_content = original_content + f"\n\n{new_block}"
    else:
        # Find all spans
        matches = list(re.finditer(pattern, original_content, re.DOTALL))
        
        # We will reconstruct the content piece by piece
        new_content = ""
        last_pos = 0
        
        for i, m in enumerate(matches):
            # Append content before this match
            new_content += original_content[last_pos:m.start()]
            
            # If it's the first match, insert the new block
            if i == 0:
                new_content += new_block
                
            # Update last_pos to end of this match (skipping the original line)
            last_pos = m.end()
            
        # Append remaining content
        new_content += original_content[last_pos:]
    
    with open(recipe_path, 'w') as f:
        f.write(new_content)
        
    return True

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
        packages, content = read_image_install(image_recipe)
        
        if package_name in packages:
            return True
            
        packages.append(package_name)
        return update_image_install(image_recipe, packages, content)
            
    except Exception as e:
        print(f"  Error updating image recipe: {e}")
        return False

def get_yocto_branch(workspace_root: Path) -> str:
    """
    detect the Yocto branch/series from the environment.
    Strategy:
    1. Find bitbake-builds/poky-* or oe-* directory
    2. Read config/sources-fixed-revisions.json
    3. Extract sources.bitbake.git-remote.branch
    4. Fallback to LAYERSERIES_COMPAT in layer.conf
    5. Fallback to 'master'
    """
    try:
        bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
        
        # 1. Preferred Method: Read from sources-fixed-revisions.json
        # This reflects the actual git branch used.
        branch = None
        config_file = bitbake_yocto_dir / "config" / "sources-fixed-revisions.json"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                data = json.load(f)
                branch = data.get('sources', {}).get('bitbake', {}).get('git-remote', {}).get('branch')

        # 2. Hybrid Check: If branch is 'master' or not found, we need the actual Yocto series name
        # for Layer Index compatibility (e.g. 'whinlatter').
        if not branch or branch == "master":
            candidates = [
                bitbake_yocto_dir / "layers" / "openembedded-core" / "meta" / "conf" / "layer.conf",
                bitbake_yocto_dir / "layers" / "meta-yocto" / "meta-poky" / "conf" / "layer.conf"
            ]
                 
            for layer_conf in candidates:
                if layer_conf.exists():
                    with open(layer_conf, 'r') as f:
                        for line in f:
                            # Use LAYERSERIES_COMPAT_core as the authoritative series name
                            if "LAYERSERIES_COMPAT_core" in line or "LAYERSERIES_COMPAT_poky" in line:
                                parts = line.split('=')
                                if len(parts) > 1:
                                    val = parts[1].strip().strip('"')
                                    # Take the last one if space-separated
                                    # Handle cases like "nanbield scarthgap"
                                    # We return the first one as the 'primary' series or just use the last
                                    # Actually, returning the last one is common for compatibility checks
                                    # but we'll return the first one as it's the more specific 'base' usually.
                                    # Wait, whinlatter is what BitBake said.
                                    return val.split()[-1]
            
            # If we found 'master' in JSON but no metadata override, use 'master'
            if branch:
                return branch
                
    except Exception:
        pass
        
    return "master"

def get_active_layers(workspace_root: Path) -> List[str]:
    """
    Get names of currently active layers.
    """
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    build_dir = bitbake_yocto_dir / "build"
    layers = []
    
    # 1. Try bitbake-layers (authoritative but fragile)
    try:
        # We need a shell that can source. oe-init-build-env is required.
        rel_yocto = bitbake_yocto_dir.relative_to(workspace_root)
        cmd = f"source {rel_yocto}/layers/openembedded-core/oe-init-build-env {rel_yocto}/build && bitbake-layers show-layers"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=workspace_root, executable="/bin/bash")
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] != "layer":
                     if parts[0] in ["NOTE:", "WARNING:", "ERROR:"]:
                         continue
                     layers.append(parts[0]) # name
    except Exception:
        pass
    
    # 2. Fallback to manual bblayers.conf parsing if empty
    if not layers:
        layer_paths = get_bblayers(workspace_root)
        for lp in layer_paths:
            layers.append(lp.name)
            
    return list(set(layers))

def check_branch_compatibility(workspace_root: Path, requested_branch: str) -> bool:
    """
    Check if the requested branch is compatible with the workspace branch.
    Returns True if compatible or if user chooses to proceed.
    """
    ws_branch = get_yocto_branch(workspace_root)
    
    if requested_branch == ws_branch:
        return True
        
    UI.print_warning(f"Branch Mismatch: Workspace is '{ws_branch}', but requested '{requested_branch}'.")
    UI.print_item("Potential Issue", "Using a different branch may lead to layer compatibility errors.")
    
    try:
        choice = input(f"  Proceed anyway? [y/N]: ").strip().lower()
        return choice == 'y'
    except (EOFError, KeyboardInterrupt):
        return False

def prune_machine_fragments(workspace_root: Path):
    """
    Check for and disable conflicting machine/* fragments in toolcfg.conf.
    This resolves issues where bitbake complains about duplicate MACHINE assignments.
    """
    if not workspace_root:
        return

    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    # Use the collection name instead of directory name where possible
    # to avoid hardcoding "meta-test" etc.
    if config_mode:
        toolcfg = bitbake_yocto_dir / "build" / "conf" / "toolcfg.conf"
    
    if not toolcfg.exists():
        return
        
    try:
        content = toolcfg.read_text()
        matches = re.findall(r'machine/([\w-]+)', content)
        
        if matches:
            UI.print_item("Config Fix", "Disabling conflicting machine fragments...")
            
            new_content = content
            for machine in matches:
                fragment = f"machine/{machine}"
                # Remove fragment and potential surrounding whitespace
                if f" {fragment}" in new_content:
                    new_content = new_content.replace(f" {fragment}", "")
                elif f"{fragment} " in new_content:
                    new_content = new_content.replace(f"{fragment} ", "")
                else:
                    new_content = new_content.replace(fragment, "")
                
                UI.print_item("Disabled", fragment)

            if new_content != content:
                toolcfg.write_text(new_content)
                UI.print_success("Updated toolcfg.conf to remove machine fragments")
                
    except Exception as e:
        print(f"  {UI.YELLOW}[WARN] Failed to prune fragments: {e}{UI.NC}")

def get_layer_collection_name(layer_path: Path) -> Optional[str]:
    """
    Get the BBFILE_COLLECTIONS name for a layer from its conf/layer.conf.
    
    Args:
        layer_path: Path to the layer root
        
    Returns:
        The collection name (e.g. "core", "falcon") or None if not found/error.
    """
    layer_conf = layer_path / "conf" / "layer.conf"
    if not layer_conf.exists():
        return None
        
    try:
        with open(layer_conf, 'r') as f:
            for line in f:
                line = line.strip()
                # Look for BBFILE_COLLECTIONS += "name" or similar
                if "BBFILE_COLLECTIONS" in line and ("+=" in line or "=" in line):
                    # parse simple assignment or append
                    parts = line.split("=")
                    if len(parts) > 1:
                        # Value might be quoted
                        val = parts[1].strip().strip('"').strip("'")
                        # If it's an append (+=), it might have leading space which strip handles
                        # Often it's just one name, but could be multiple? Standard is one per layer.
                        # We'll take the first non-empty part
                        val_parts = val.split()
                        if val_parts:
                            return val_parts[0]
    except Exception:
        pass
        
    return None
