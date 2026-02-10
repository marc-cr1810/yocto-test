#!/usr/bin/env python3
import sys
import os
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, get_all_custom_layers, run_command

def find_recipe(workspace_root, recipe_name):
    """Find a recipe file in custom layers."""
    for layer in get_all_custom_layers(workspace_root):
        # Look in all subdirectories
        matches = list(layer.rglob(f"{recipe_name}.bb"))
        if matches:
            return matches[0]
        # Try appending version wildcard if likely
        matches = list(layer.rglob(f"{recipe_name}_*.bb"))
        if matches:
            return matches[0]
    return None

def is_kernel_module(recipe_path):
    """Check if recipe inherits module."""
    try:
        content = recipe_path.read_text()
        return "inherit module" in content
    except:
        return False

def enable_service(recipe_path, recipe_name):
    """Enable service or module autoload."""
    if not recipe_path.exists():
        return False, "Recipe not found"

    try:
        content = recipe_path.read_text()
        new_content = content
        
        if is_kernel_module(recipe_path):
            # It's a kernel module -> KERNEL_MODULE_AUTOLOAD
            if f'KERNEL_MODULE_AUTOLOAD += "{recipe_name}"' in content:
                return True, "Already enabled"
            
            # Append to end
            new_content += f'\n# Autoload module on boot\nKERNEL_MODULE_AUTOLOAD += "{recipe_name}"\n'
            msg = f"Added KERNEL_MODULE_AUTOLOAD for {recipe_name}"
        else:
            # It's an app -> SYSTEMD_AUTO_ENABLE (and inherit systemd)
            # Check for existing SYSTEMD_AUTO_ENABLE
            if 'SYSTEMD_AUTO_ENABLE' in content:
                 new_content = re.sub(
                    r'SYSTEMD_AUTO_ENABLE\s*=\s*"disable"',
                    'SYSTEMD_AUTO_ENABLE = "enable"',
                    new_content
                 )
            else:
                 new_content += '\n# Enable systemd service\nSYSTEMD_AUTO_ENABLE = "enable"\n'
            
            # Ensure inherit systemd is present? 
            # Usuallly required if not using a class that does it. 
            # But let's assume the user has a service file configured or we might need to add that too?
            # For now, just toggling the variable.
            msg = f"Enabled SYSTEMD_AUTO_ENABLE for {recipe_name}"

        recipe_path.write_text(new_content)
        return True, msg

    except Exception as e:
        return False, str(e)

def disable_service(recipe_path, recipe_name):
    """Disable service or module autoload."""
    if not recipe_path.exists():
        return False, "Recipe not found"

    try:
        content = recipe_path.read_text()
        new_content = content
        
        if is_kernel_module(recipe_path):
            # Remove KERNEL_MODULE_AUTOLOAD line
            pattern = f'.*KERNEL_MODULE_AUTOLOAD.*"{recipe_name}".*\n?'
            if re.search(pattern, content):
                new_content = re.sub(pattern, '', content)
                recipe_path.write_text(new_content)
                return True, f"Removed KERNEL_MODULE_AUTOLOAD for {recipe_name}"
            return True, "Already disabled"
        else:
            # Set SYSTEMD_AUTO_ENABLE = "disable"
            if 'SYSTEMD_AUTO_ENABLE' in content:
                 new_content = re.sub(
                    r'SYSTEMD_AUTO_ENABLE\s*=\s*"enable"',
                    'SYSTEMD_AUTO_ENABLE = "disable"',
                    new_content
                 )
                 recipe_path.write_text(new_content)
                 return True, f"Disabled SYSTEMD_AUTO_ENABLE for {recipe_name}"
            return True, "Already disabled (default)"

    except Exception as e:
        return False, str(e)

def get_status(recipe_path, recipe_name):
    """Get status string."""
    try:
        content = recipe_path.read_text()
        if is_kernel_module(recipe_path):
            if f'KERNEL_MODULE_AUTOLOAD += "{recipe_name}"' in content:
                return f"{UI.GREEN}Enabled{UI.NC} (Kernel Module)"
            return f"{UI.DIM}Disabled{UI.NC} (Kernel Module)"
        else:
            if 'SYSTEMD_AUTO_ENABLE = "enable"' in content:
                return f"{UI.GREEN}Enabled{UI.NC} (Systemd)"
            return f"{UI.DIM}Disabled{UI.NC} (Systemd)"
    except:
        return "Error"

def scan_services(workspace_root):
    """Scan for enabled services and modules."""
    enabled_items = []
    
    # Iterate through all custom layers
    for layer in get_all_custom_layers(workspace_root):
        # Recursively find all .bb files
        for recipe_file in layer.rglob("*.bb"):
            try:
                content = recipe_file.read_text()
                name = recipe_file.stem.split('_')[0]
                
                # Check Kernel Module Autoload
                if 'KERNEL_MODULE_AUTOLOAD' in content:
                    # check if it actually enables it (not just modification)
                    # Simple check: does it look like += "name"?
                    if re.search(r'KERNEL_MODULE_AUTOLOAD\s*\+=\s*"[^"]+"', content):
                        enabled_items.append({'name': name, 'type': 'Kernel Module', 'path': recipe_file})
                
                # Check Systemd Enable
                if 'SYSTEMD_AUTO_ENABLE' in content:
                    if 'SYSTEMD_AUTO_ENABLE = "enable"' in content or "SYSTEMD_AUTO_ENABLE ?= \"enable\"" in content:
                         enabled_items.append({'name': name, 'type': 'Systemd Service', 'path': recipe_file})
                         
            except Exception:
                continue
                
    return sorted(enabled_items, key=lambda x: x['name'])


def main():
    parser = argparse.ArgumentParser(description="Manage Yocto Services (yocto-service)")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Enable
    p_enable = subparsers.add_parser("enable", help="Enable a service/module")
    p_enable.add_argument("name", help="Recipe/Service name")
    
    # Disable
    p_disable = subparsers.add_parser("disable", help="Disable a service/module")
    p_disable.add_argument("name", help="Recipe/Service name")

    # Status/List?
    # For now just checking specific ones or listing all?
    # Let's verify specific one for CLI
    p_status = subparsers.add_parser("status", help="Check status")
    p_status.add_argument("name", help="Recipe/Service name")

    # List
    p_list = subparsers.add_parser("list", help="List enabled services")

    args = parser.parse_args()
    workspace_root = Path(__file__).resolve().parent.parent
    UI.print_header("Yocto Service Manager")

    # Default to list if no command provided
    if not args.command:
        args.command = "list"

    if args.command == "list":
        items = scan_services(workspace_root)
        if items:
            print(f"  {'Service/Module':<30} | {'Type':<20} | {'Status'}")
            print(f"  {'-'*30}-+-{'-'*20}-+-{'-'*10}")
            for item in items:
                print(f"  {item['name']:<30} | {item['type']:<20} | {UI.GREEN}Enabled{UI.NC}")
        else:
             print("  No enabled services found in custom layers.")
        return

    recipe_path = find_recipe(workspace_root, args.name)
    if not recipe_path:
        UI.print_error(f"Recipe '{args.name}' not found in custom layers.")
        return

    if args.command == "enable":
        success, msg = enable_service(recipe_path, args.name)
        if success:
            UI.print_success(msg)
        else:
            UI.print_error(msg)
            
    elif args.command == "disable":
        success, msg = disable_service(recipe_path, args.name)
        if success:
            UI.print_success(msg)
        else:
            UI.print_error(msg)

    elif args.command == "status":
        status = get_status(recipe_path, args.name)
        UI.print_item(args.name, status)

if __name__ == "__main__":
    main()
