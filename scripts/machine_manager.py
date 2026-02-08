#!/usr/bin/env python3
import os
import sys
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto target machines")
    parser.add_argument("machine", nargs="?", help="Machine name to switch to")
    parser.add_argument("--list", action="store_true", help="List available machines")
    parser.add_argument("--new", metavar="NAME", help="Scaffold a new machine configuration")
    parser.add_argument("--layer", help="Layer name to use for --new (default: auto-detect)")
    args = parser.parse_args()

    UI.print_header("Yocto Target Machine Manager")

    workspace_root = Path(__file__).resolve().parent.parent
    poky_dir = workspace_root / "bitbake-builds" / "poky-master"
    local_conf = poky_dir / "build" / "conf" / "local.conf"
    
    if args.new:
        scaffold_machine(args.new, workspace_root, args.layer)
        return

    if args.list:
        list_machines(workspace_root, poky_dir)
        return

    if args.machine:
        switch_machine(args.machine, local_conf)
    else:
        show_current_machine(local_conf)

def show_current_machine(local_conf):
    if not local_conf.exists():
        UI.print_warning("local.conf not found.")
        return

    with open(local_conf, "r") as f:
        for line in f:
            if line.strip().startswith("MACHINE"):
                match = re.search(r'MACHINE\s*=\s*"([^"]+)"', line)
                if match:
                    UI.print_item("Current Machine", match.group(1))
                    return
    UI.print_item("Current Machine", "Unknown (not set in local.conf)")

def list_machines(workspace_root, poky_dir):
    UI.print_item("Status", "Scanning for available machines...")
    
    # Standard Poky machines
    poky_machines = []
    meta_dir = poky_dir / "layers" / "openembedded-core" / "meta"
    if meta_dir.exists():
        for m in (meta_dir / "conf" / "machine").glob("*.conf"):
            poky_machines.append(m.stem)
            
    # Local layer machines
    local_machines = []
    layer_dir = workspace_root / "yocto" / "layers"
    if layer_dir.exists():
        for m in layer_dir.rglob("conf/machine/*.conf"):
            local_machines.append(m.stem)

    if poky_machines:
        UI.print_item("Poky/Core", ', '.join(sorted(poky_machines)))
    if local_machines:
        UI.print_item("Local Layer", f"{UI.GREEN}{', '.join(sorted(local_machines))}{UI.NC}")
    
    print(f"\n  {UI.BOLD}Usage:{UI.NC} yocto-machine <name>")

def switch_machine(target_machine, local_conf):
    if not local_conf.exists():
        UI.print_error(f"{local_conf} does not exist.")
        return

    with open(local_conf, "r") as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("MACHINE"):
            new_lines.append(f'MACHINE = "{target_machine}"\n')
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        # Prepend to the file if MACHINE not found
        new_lines.insert(0, f'MACHINE = "{target_machine}"\n')

    with open(local_conf, "w") as f:
        f.writelines(new_lines)

    UI.print_item("Target Machine", target_machine)
    UI.print_success("Successfully updated local.conf")

def scaffold_machine(name, workspace_root, layer_name):
    try:
        layer_dir = find_custom_layer(workspace_root, layer_name)
    except RuntimeError as e:
        UI.print_error(str(e), fatal=True)
        
    machine_dir = layer_dir / "conf" / "machine"
    machine_file = machine_dir / f"{name}.conf"

    if machine_file.exists():
        UI.print_warning(f"Machine '{name}' already exists.")
        return

    machine_dir.mkdir(parents=True, exist_ok=True)
    
    content = f"""#@TYPE: Machine
#@NAME: {name}
#@DESCRIPTION: Baseline machine configuration for {name}

# Default to a generic qemuarm64-like setup for portability
TARGET_ARCH = "aarch64"
TUNE_FEATURES:tune-aarch64 = "aarch64"
DEFAULTTUNE = "aarch64"

# Use virtual/kernel and virtual/bootloader providers as needed
# PREFERRED_PROVIDER_virtual/kernel = "linux-yocto"

# Serial console setting
SERIAL_CONSOLES = "115200;ttyAMA0"

# Filesystem features
IMAGE_FSTYPES += "tar.bz2 ext4 wic"
"""

    with open(machine_file, "w") as f:
        f.write(content)

    UI.print_success(f"Machine '{name}' scaffolded.")
    UI.print_item("Config Path", str(machine_file))
    print(f"\n  Run '{UI.BOLD}yocto-machine {name}{UI.NC}' to activate it.")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
