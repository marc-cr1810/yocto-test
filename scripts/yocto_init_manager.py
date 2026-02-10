#!/usr/bin/env python3
import sys
import os
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_bitbake_yocto_dir

def get_available_init_managers(workspace_root):
    """
    Scan for available init managers in openembedded-core/meta/conf/distro/include.
    Returns a list of available init manager names (e.g., 'systemd', 'sysvinit').
    """
    init_managers = []
    
    # Init managers are typically defined in meta/conf/distro/include/init-manager-*.inc
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    include_dir = bitbake_yocto_dir / "layers" / "openembedded-core" / "meta" / "conf" / "distro" / "include"
    
    if include_dir.exists():
        for inc in include_dir.glob("init-manager-*.inc"):
            # Extract name: init-manager-NAME.inc
            name = inc.stem.replace("init-manager-", "")
            init_managers.append(name)
            
    return sorted(init_managers)

def get_current_init_manager(workspace_root):
    """Get the current INIT_MANAGER from local.conf"""
    bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
    local_conf = bitbake_yocto_dir / "build" / "conf" / "local.conf"
    
    if not local_conf.exists():
        return None
        
    try:
        content = local_conf.read_text()
        # Look for INIT_MANAGER ?= "name" or INIT_MANAGER = "name"
        # We prefer the last assignment if multiple
        matches = re.findall(r'^INIT_MANAGER\s*\??=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if matches:
            return matches[-1]
    except:
        pass
        
    return "none" # Default fallback if not set (or typically 'sysvinit' depending on distro, but 'none' is safe bet for unset)

def set_init_manager(workspace_root, init_manager):
    """Update INIT_MANAGER in local.conf"""
    local_conf = get_bitbake_yocto_dir(workspace_root) / "build" / "conf" / "local.conf"
    if not local_conf.exists():
        return False
    
    try:
        content = local_conf.read_text()
        
        # Check if INIT_MANAGER is already set
        if re.search(r'^INIT_MANAGER\s*\??=', content, re.MULTILINE):
            # Replace existing
            new_content = re.sub(
                r'^(INIT_MANAGER\s*\??=\s*)["\'][^"\']+["\']',
                f'\\1"{init_manager}"',
                content,
                flags=re.MULTILINE
            )
        else:
            # Append if missing
            new_content = content + f'\nINIT_MANAGER ?= "{init_manager}"\n'
            
        local_conf.write_text(new_content)
        return True
    except Exception as e:
        UI.print_error(f"Failed to update local.conf: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto Init System (yocto-init-manager)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List
    subparsers.add_parser("list", help="List available init managers")
    
    # Set
    parser_set = subparsers.add_parser("set", help="Set the active init manager")
    parser_set.add_argument("init_manager", help="Init manager name (e.g. systemd, sysvinit)")
    
    # Show
    subparsers.add_parser("show", help="Show current init manager")

    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    
    # Create title
    UI.print_header("Yocto Init System Manager")
    
    current = get_current_init_manager(workspace_root)
    
    if args.command == "list":
        UI.print_item("Current Init Manager", current or "Unknown")
        print("\n  Available Init Managers:")
        managers = get_available_init_managers(workspace_root)
        
        for name in managers:
            marker = f" {UI.GREEN}(Active){UI.NC}" if name == current else ""
            print(f"    - {name}{marker}")
            
    elif args.command == "set":
        manager = args.init_manager
        available = get_available_init_managers(workspace_root)
        if manager not in available:
            UI.print_warning(f"Init manager '{manager}' not found in standard includes.")
            print(f"  (You can still set it if you are sure it exists)")
            
        if set_init_manager(workspace_root, manager):
            UI.print_success(f"Init Manager set to '{manager}'")
            print(f"  {UI.DIM}Note: You may need to run 'yocto-build -c cleansstate' for changes to take effect.{UI.NC}")
            
    elif args.command == "show" or not args.command:
        UI.print_item("Current Init Manager", current or "Unknown")
        print(f"\n  To change: yocto-init-manager set <name>")

if __name__ == "__main__":
    main()
