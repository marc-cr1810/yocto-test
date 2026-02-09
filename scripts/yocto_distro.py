#!/usr/bin/env python3
import sys
import os
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_bitbake_yocto_dir

def get_available_distros(workspace_root):
    """
    Scan for available distributions in meta layers.
    Returns a dict of distro_name -> path
    """
    distros = {}
    
    # 1. Scan Poky/OE
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    dirs_to_scan = [
        bitbake_yocto_dir / "layers" / "openembedded-core" / "meta" / "conf" / "distro",
        bitbake_yocto_dir / "layers" / "meta-yocto" / "meta-poky" / "conf" / "distro",
        bitbake_yocto_dir / "layers" / "meta-openembedded" / "meta-oe" / "conf" / "distro" # If present
    ]
    
    # 2. Scan Custom Layers
    layers_dir = workspace_root / "yocto" / "layers"
    if layers_dir.exists():
        for layer in layers_dir.glob("meta-*"):
            dirs_to_scan.append(layer / "conf" / "distro")
            
    for d in dirs_to_scan:
        if d.exists():
            for conf in d.glob("*.conf"):
                # exclude include files
                if conf.name.endswith(".inc"):
                    continue
                distros[conf.stem] = conf
                
    # Add implicit 'nodistro' if we are in a pure OE environment (no poky)
    poky_layer = bitbake_yocto_dir / "layers" / "meta-yocto" / "meta-poky"
    if not poky_layer.exists():
        distros['nodistro'] = None # No specific file, it's the default
                
    return distros

def get_current_distro(workspace_root):
    """Get the current DISTRO from local.conf"""
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    local_conf = bitbake_yocto_dir / "build" / "conf" / "local.conf"
    
    if not local_conf.exists():
        return None
        
    try:
        content = local_conf.read_text()
        # Look for DISTRO ?= "name" or DISTRO = "name"
        # We prefer the last assignment if multiple
        matches = re.findall(r'^DISTRO\s*\??=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if matches:
            return matches[-1]
    except:
        pass
        
    # Default fallback: check if we are in Poky or pure OE
    poky_layer = bitbake_yocto_dir / "layers" / "meta-yocto" / "meta-poky"
    if poky_layer.exists():
        return "poky"
    return "nodistro"

def set_distro(workspace_root, distro_name):
    """Update DISTRO in local.conf"""
    local_conf = get_bitbake_yocto_dir(workspace_root) / "build" / "conf" / "local.conf"
    if not local_conf.exists():
        return False
    
    try:
        content = local_conf.read_text()
        
        # If setting to 'nodistro' in a pure OE env, we might want to just UNSET it
        # But to be safe and explicit, let's see.
        # If 'nodistro' doesn't have a conf file, we MUST unset it.
        available = get_available_distros(workspace_root)
        is_implicit = (distro_name == 'nodistro' and available.get('nodistro') is None)
        
        if is_implicit:
            # Remove DISTRO variable to revert to default
            new_content = re.sub(r'^DISTRO\s*\??=.*$\n?', '', content, flags=re.MULTILINE)
        else:
            # Check if DISTRO is already set
            if re.search(r'^DISTRO\s*\??=', content, re.MULTILINE):
                # Replace existing
                new_content = re.sub(
                    r'^(DISTRO\s*\??=\s*)["\'][^"\']+["\']',
                    f'\\1"{distro_name}"',
                    content,
                    flags=re.MULTILINE
                )
            else:
                # Append if missing
                new_content = content + f'\nDISTRO ?= "{distro_name}"\n'
            
        local_conf.write_text(new_content)
        return True
    except Exception as e:
        UI.print_error(f"Failed to update local.conf: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto Distribution (yocto-distro)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List
    subparsers.add_parser("list", help="List available distributions")
    
    # Set
    parser_set = subparsers.add_parser("set", help="Set the active distribution")
    parser_set.add_argument("distro", help="Distro name (e.g. poky, poky-tiny)")
    
    # Show
    subparsers.add_parser("show", help="Show current distribution")

    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    
    # Create title
    UI.print_header("Yocto Distribution Manager")
    
    current = get_current_distro(workspace_root)
    
    if args.command == "list":
        UI.print_item("Current Distro", current or "Unknown")
        print("\n  Available Distributions:")
        distros = get_available_distros(workspace_root)
        
        # Group by source? Or just alphabetize
        for name in sorted(distros.keys()):
            marker = f" {UI.GREEN}(Active){UI.NC}" if name == current else ""
            print(f"    - {name}{marker}")
            
    elif args.command == "set":
        distro = args.distro
        available = get_available_distros(workspace_root)
        if distro not in available:
            UI.print_warning(f"Distro '{distro}' not found in scanned layers.")
            print(f"  (You can still set it if you are sure it exists)")
            
        if set_distro(workspace_root, distro):
            UI.print_success(f"Distro set to '{distro}'")
            print(f"  {UI.DIM}Note: You may need to run 'yocto-build -c cleansstate' if changing arch.{UI.NC}")
            
    elif args.command == "show" or not args.command:
        UI.print_item("Current Distro", current or "Unknown")
        print(f"\n  To change: yocto-distro set <name>")

if __name__ == "__main__":
    main()
