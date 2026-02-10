#!/usr/bin/env python3
import os
import sys
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_bitbake_yocto_dir

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = get_bitbake_yocto_dir(WORKSPACE_ROOT) / "build"
TOOLCFG_PATH = BUILD_DIR / "conf" / "toolcfg.conf"

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto configuration fragments (yocto-config)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List
    parser_list = subparsers.add_parser("list", help="List active fragments")

    # Enable
    parser_enable = subparsers.add_parser("enable", help="Enable a fragment")
    parser_enable.add_argument("fragment", help="Fragment name (e.g. machine/raspberrypi4)")

    # Disable
    parser_disable = subparsers.add_parser("disable", help="Disable a fragment")
    parser_disable.add_argument("fragment", help="Fragment name (e.g. machine/qemuarm64)")

    # List Available
    parser_avail = subparsers.add_parser("list-available", help="List all available fragments in layers")

    args = parser.parse_args()

    UI.print_header("Yocto Fragment Manager")
    
    if not TOOLCFG_PATH.exists():
        UI.print_error(f"Configuration file not found: {TOOLCFG_PATH}", fatal=True)

    if args.command == "list":
        list_fragments()
    elif args.command == "enable":
        enable_fragment(args.fragment)
    elif args.command == "disable":
        disable_fragment(args.fragment)
    elif args.command == "list-available":
        list_available_fragments()
    else:
        list_fragments()

def get_fragments():
    """Read and parse OE_FRAGMENTS from toolcfg.conf."""
    try:
        content = TOOLCFG_PATH.read_text()
        match = re.search(r'OE_FRAGMENTS\s*\+=\s*"([^"]*)"', content)
        if match:
            # Split by whitespace and filter empty strings
            fragments = [f.strip() for f in match.group(1).split()]
            return fragments
        return []
    except Exception as e:
        UI.print_error(f"Failed to read toolcfg.conf: {e}")
        return []

def save_fragments(fragments):
    """Save the list of fragments back to toolcfg.conf."""
    try:
        content = TOOLCFG_PATH.read_text()
        
        # Join fragments with spaces
        new_val = " ".join(fragments)
        
        # Replace the OE_FRAGMENTS line
        # We look for the line with OE_FRAGMENTS += "..."
        new_content = re.sub(
            r'(OE_FRAGMENTS\s*\+=\s*)"([^"]*)"', 
            f'\\1"{new_val}"', 
            content
        )
        
        # If no match/substitution happened (maybe empty list case logic needed?), append it?
        # Assuming the file structure is static as seen in cat output.
        if new_content == content and "OE_FRAGMENTS" not in content:
             UI.print_warning("OE_FRAGMENTS not found in toolcfg.conf. Appending...")
             new_content += f'\nOE_FRAGMENTS += "{new_val}"\n'
             
        TOOLCFG_PATH.write_text(new_content)
        return True
    except Exception as e:
        UI.print_error(f"Failed to write toolcfg.conf: {e}")
        return False

def list_fragments():
    fragments = get_fragments()
    UI.print_item("Active Fragments")
    print("  " + "-" * 50)
    if not fragments:
        print("  (None)")
    else:
        for f in fragments:
            print(f"  {UI.GREEN}{f}{UI.NC}")
    print("  " + "-" * 50)

def enable_fragment(fragment):
    fragments = get_fragments()
    if fragment in fragments:
        UI.print_warning(f"Fragment '{fragment}' is already enabled.")
        return

    UI.print_item("Enabling", fragment)
    fragments.append(fragment)
    if save_fragments(fragments):
        UI.print_success(f"Enabled '{fragment}'")

def disable_fragment(fragment):
    fragments = get_fragments()
    if fragment not in fragments:
        UI.print_warning(f"Fragment '{fragment}' is not enabled.")
        return
    
    UI.print_item("Disabling", fragment)
    fragments.remove(fragment)
    if save_fragments(fragments):
        UI.print_success(f"Disabled '{fragment}'")


def get_available_fragments():
    """Scan layers for available configuration fragments."""
    try:
        from yocto_utils import get_bblayers, get_layer_collection_name
        layers = get_bblayers(WORKSPACE_ROOT)
    except ImportError:
        UI.print_error("Could not import get_bblayers from yocto_utils")
        return {}

    available = {} # dict of fragment_name -> path

    for layer in layers:
        if not layer.exists():
            continue
            
        # Get collection name for prefix (e.g. "core", "falcon")
        # If not found, fall back to layer name (e.g. "meta-falcon")
        collection = get_layer_collection_name(layer)
        if not collection:
            collection = layer.name
            
        # Look for conf/fragments/*.conf
        fragment_dir = layer / "conf" / "fragments"
        if fragment_dir.exists():
            for conf in fragment_dir.rglob("*.conf"):
                rel_path = conf.relative_to(fragment_dir)
                # Fragment name is collection/path/to/fragment (without .conf)
                # e.g. core/yocto/root-login-with-empty-password
                name = f"{collection}/{str(rel_path.with_suffix(''))}"
                available[name] = conf
    return available

def list_available_fragments():
    available = get_available_fragments()
    active = get_fragments()
    
    UI.print_item("Available Fragments")
    print("  " + "-" * 50)
    
    if not available:
        print("  (None found in conf/fragments/)")
    else:
        # Group by folder (e.g. machine/, distro/, etc)
        sorted_keys = sorted(available.keys())
        for name in sorted_keys:
            status = f"{UI.GREEN}[Active]{UI.NC}" if name in active else ""
            print(f"  {name:<30} {status}")
            
    print("  " + "-" * 50)

if __name__ == "__main__":
    main()
