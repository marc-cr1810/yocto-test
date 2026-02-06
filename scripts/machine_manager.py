#!/usr/bin/env python3
import os
import sys
import argparse
import re
from pathlib import Path

def get_bold_text(text, bold): return f"\033[1m{text}\033[0m" if bold else text

def main():
    parser = argparse.ArgumentParser(description="Manage Yocto target machines")
    parser.add_argument("machine", nargs="?", help="Machine name to switch to")
    parser.add_argument("--list", action="store_true", help="List available machines")
    parser.add_argument("--new", metavar="NAME", help="Scaffold a new machine configuration")
    parser.add_argument("--layer", help="Layer name to use for --new (default: auto-detect)")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    workspace_root = Path(__file__).resolve().parent.parent
    poky_dir = workspace_root / "bitbake-builds" / "poky-master"
    local_conf = poky_dir / "build" / "conf" / "local.conf"
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Yocto Target Machine Manager{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    if args.new:
        scaffold_machine(args.new, workspace_root, args.layer, BOLD, GREEN, CYAN, NC)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    if args.list:
        list_machines(workspace_root, poky_dir, BOLD, GREEN, NC)
        print(f"{BOLD}{CYAN}=================================================={NC}")
        return

    if args.machine:
        switch_machine(args.machine, local_conf, BOLD, GREEN, RED, NC)
    else:
        show_current_machine(local_conf, BOLD, YELLOW, NC)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

def show_current_machine(local_conf, BOLD, YELLOW, NC):
    if not local_conf.exists():
        print(f"  {BOLD}Status       :{NC} local.conf not found.")
        return

    with open(local_conf, "r") as f:
        for line in f:
            if line.strip().startswith("MACHINE"):
                match = re.search(r'MACHINE\s*=\s*"([^"]+)"', line)
                if match:
                    print(f"  Current      : {BOLD}{YELLOW}{match.group(1)}{NC}")
                    return
    print(f"  Current      : {BOLD}Unknown (not set in local.conf){NC}")

def list_machines(workspace_root, poky_dir, BOLD, GREEN, NC):
    print(f"  {BOLD}Available Machines:{NC}")
    
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
        print(f"    Poky/Core  : {', '.join(sorted(poky_machines))}")
    if local_machines:
        print(f"    Local Layer: {GREEN}{', '.join(sorted(local_machines))}{NC}")
    
    print(f"\n  {BOLD}Usage:{NC} yocto-machine <name>")

def switch_machine(target_machine, local_conf, BOLD, GREEN, RED, NC):
    if not local_conf.exists():
        print(f"  {RED}Error: {local_conf} does not exist.{NC}")
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

    print(f"  Target       : {BOLD}{target_machine}{NC}")
    print(f"  {GREEN}Status       : Successfully updated local.conf{NC}")

def scaffold_machine(name, workspace_root, layer_name, BOLD, GREEN, CYAN, NC):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from yocto_utils import find_custom_layer
    layer_dir = find_custom_layer(workspace_root, layer_name)
    machine_dir = layer_dir / "conf" / "machine"
    machine_file = machine_dir / f"{name}.conf"

    if machine_file.exists():
        print(f"  {BOLD}Error        :{NC} Machine '{name}' already exists.")
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

    print(f"  New Machine  : {BOLD}{name}{NC}")
    print(f"  Config Path  : {machine_file}")
    print(f"\n{GREEN}Success! Machine scaffolded.{NC}")
    print(f"  Run '{BOLD}yocto-machine {name}{NC}' to activate it.")

if __name__ == "__main__":
    main()
