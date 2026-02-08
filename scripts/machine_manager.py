#!/usr/bin/env python3
import os
import sys
import argparse
import re
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer, get_yocto_branch, run_command, prune_machine_fragments
from yocto_layer_index import LayerIndex, DEFAULT_BRANCH

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = WORKSPACE_ROOT / "yocto" / "sources"
BUILD_DIR = WORKSPACE_ROOT / "bitbake-builds" / "poky-master" / "build"

def main():
    # Smart dispatch: If the first argument is not a known command or flag, assume it's a machine name for 'switch'
    # This preserves 'yocto-machine <name>' behavior while allowing subcommands.
    known_commands = {'list', 'search', 'get', 'new', 'status', 'switch'}
    
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if not first_arg.startswith('-') and first_arg not in known_commands:
            # Insert 'switch' command
            sys.argv.insert(1, 'switch')

    parser = argparse.ArgumentParser(description="Manage Yocto target machines")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Status (Default)
    parser_status = subparsers.add_parser("status", help="Show current machine")

    # Switch
    parser_switch = subparsers.add_parser("switch", help="Switch to a target machine")
    parser_switch.add_argument("machine", help="Machine name")

    # List
    parser_list = subparsers.add_parser("list", help="List available machines")

    # New
    parser_new = subparsers.add_parser("new", help="Scaffold a new machine")
    parser_new.add_argument("name", help="Name of the new machine")
    parser_new.add_argument("--layer", help="Layer name (default: auto-detect)")

    # Search
    parser_search = subparsers.add_parser("search", help="Search for machines in Layer Index")
    parser_search.add_argument("term", help="Search term")
    parser_search.add_argument("--branch", help="Override Yocto branch")

    # Get
    parser_get = subparsers.add_parser("get", help="Fetch and install a machine's layer")
    parser_get.add_argument("name", help="Machine name to fetch")
    parser_get.add_argument("--branch", help="Override Yocto branch")

    args = parser.parse_args()

    UI.print_header("Yocto Target Machine Manager")

    poky_dir = WORKSPACE_ROOT / "bitbake-builds" / "poky-master"
    local_conf = poky_dir / "build" / "conf" / "local.conf"

    if args.command == "new":
        scaffold_machine(args.name, WORKSPACE_ROOT, args.layer)
    elif args.command == "list":
        list_machines(WORKSPACE_ROOT, poky_dir)
    elif args.command == "search":
        search_machines(args.term, args.branch)
    elif args.command == "get":
        get_machine(args.name, args.branch)
    elif args.command == "switch":
        switch_machine(args.machine, local_conf)
    else:
        # Default action: status
        show_current_machine(local_conf)

def search_machines(term, branch_override=None):
    branch = branch_override or get_yocto_branch(WORKSPACE_ROOT)
    UI.print_item("Searching", f"'{term}' in branch '{branch}'...")
    
    index = LayerIndex(branch=branch)
    if not index.get_branch_id():
        UI.print_error(f"Invalid branch '{branch}' on Layer Index.", fatal=True)
        
    machines = index.search_machines(term)
    
    if not machines:
        UI.print_warning(f"No machines found matching '{term}'.")
        return
        
    valid_machines = []
    for m in machines:
        info = index.get_machine_layer_info(m)
        if info:
            valid_machines.append(info)
            
    if not valid_machines:
        UI.print_warning(f"Found machines matching '{term}' but none for branch '{branch}'.")
        if not branch_override:
             print(f"  Tip: Try specifying a different branch with {UI.BOLD}--branch <name>{UI.NC}")
             print(f"       e.g. {UI.BOLD}yocto-machine --search {term} --branch master{UI.NC}")
        return
        
    print(f"\n  {UI.BOLD}{'Machine':<30} {'Layer':<25} {'Description'}{UI.NC}")
    print("  " + "-" * 100)
    for m in valid_machines[:15]: # Limit results
        desc = m['description'][:40] + "..." if len(m['description']) > 40 else m['description']
        print(f"  {UI.GREEN}{m['machine_name']:<30}{UI.NC} {UI.CYAN}{m['layer_name']:<25}{UI.NC} {desc}")

def get_machine(machine_name, branch_override=None):
    branch = branch_override or get_yocto_branch(WORKSPACE_ROOT)
    UI.print_item("Resolving", f"'{machine_name}' in branch '{branch}'...")
    
    index = LayerIndex(branch=branch)
    if not index.get_branch_id():
        UI.print_error(f"Invalid branch '{branch}'", fatal=True)
        
    machines = index.search_machines(machine_name)
    target = None
    
    for m in machines:
        if m['name'] == machine_name:
            possible_target = index.get_machine_layer_info(m)
            if possible_target:
                target = possible_target
                break
            
    if not target:
        UI.print_error(f"Machine '{machine_name}' not found for branch '{branch}'.")
        # Try fuzzy match?
        return
        
    UI.print_item("Found", f"{target['machine_name']} in layer {target['layer_name']}")
    
    # Reuse yocto-get logic slightly adapted for just ensuring the layer
    # Since we can't easily import ensure_layer_recursive from yocto-get (it's a script), 
    # we'll implement a simplified version here or shell out to 'yocto-get' with a hack?
    # No, let's implement the layer fetch logic cleanly.
    
    if ensure_layer(index, target, branch):
         UI.print_success(f"Machine '{machine_name}' is ready.")
         print(f"  Run '{UI.BOLD}yocto-machine {machine_name}{UI.NC}' to switch to it.")

def get_active_layers():
    output = run_command("bitbake-layers show-layers", cwd=BUILD_DIR)
    if not output: # run_command returns string if capture=True? 
         # Wait, yocto_utils.run_command returns stdout string.
         pass
    else:
         # yocto_utils.run_command returns string.
         pass
         
    # Let's rely on bitbake-layers output
    try:
        res = subprocess.run("bitbake-layers show-layers", shell=True, check=True, cwd=BUILD_DIR, capture_output=True, text=True)
        lines = res.stdout.splitlines()
        layers = []
        for line in lines:
             parts = line.split()
             if len(parts) >= 2 and parts[0] != "layer":
                 layers.append(parts[0])
        return layers
    except:
        return []

def ensure_layer(index, machine_info, branch):
    layer_name = machine_info['layer_name']
    vcs_url = machine_info['layer_vcs_url']
    subdir = machine_info['vcs_subdir']
    actual_branch = machine_info['actual_branch']
    
    UI.print_item("Checking Layer", layer_name)
    
    active = get_active_layers()
    if layer_name in active:
        UI.print_success(f"Layer '{layer_name}' is active.")
        return True
        
    # Check if exists in sources
    repo_name = vcs_url.split('/')[-1].replace('.git', '')
    repo_path = SOURCES_DIR / repo_name
    
    if not repo_path.exists():
        UI.print_item("Cloning", f"{vcs_url} ({actual_branch})...")
        SOURCES_DIR.mkdir(parents=True, exist_ok=True)
        if actual_branch:
            cmd = f"git clone -b {actual_branch} {vcs_url} {repo_path}"
        else:
            cmd = f"git clone {vcs_url} {repo_path}"
            
        if subprocess.run(cmd, shell=True).returncode != 0:
             UI.print_error("Clone failed.")
             return False
    
    layer_path = repo_path
    if subdir:
        layer_path = repo_path / subdir
        
    UI.print_item("Registering", str(layer_path))
    if subprocess.run(f"bitbake-layers add-layer {layer_path}", shell=True, cwd=BUILD_DIR).returncode == 0:
        return True
    
    return False



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
    
    from yocto_utils import get_available_machines
    machines = get_available_machines(workspace_root)

    if machines['poky']:
        UI.print_item("Poky/Core", ', '.join(machines['poky']))
    if machines['custom']:
        UI.print_item("Local Layer", f"{UI.GREEN}{', '.join(machines['custom'])}{UI.NC}")
    


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


