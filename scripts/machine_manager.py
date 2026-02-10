#!/usr/bin/env python3
import os
import sys
import argparse
import re
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer, get_yocto_branch, run_command, prune_machine_fragments, get_bitbake_yocto_dir, get_active_layers, check_branch_compatibility
from yocto_layer_index import LayerIndex, DEFAULT_BRANCH

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = WORKSPACE_ROOT / "yocto" / "sources"
BUILD_DIR = get_bitbake_yocto_dir(WORKSPACE_ROOT) / "build"

def main():
    known_commands = {'list', 'search', 'get', 'new', 'status', 'switch'}
    
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if not first_arg.startswith('-') and first_arg not in known_commands:
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

    bitbake_yocto_dir = get_bitbake_yocto_dir(WORKSPACE_ROOT)
    local_conf = bitbake_yocto_dir / "build" / "conf" / "local.conf"

    if args.command == "new":
        scaffold_machine(args.name, WORKSPACE_ROOT, args.layer)
    elif args.command == "list":
        list_machines(WORKSPACE_ROOT, bitbake_yocto_dir)
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
             print(f"       e.g. {UI.BOLD}yocto-machine search {term} --branch master{UI.NC}")
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
        return
        
    UI.print_item("Found", f"{target['machine_name']} in layer {target['layer_name']}")
    
    # Check branch compatibility
    if not check_branch_compatibility(WORKSPACE_ROOT, branch):
        UI.print_error("Cancelled due to branch mismatch.")
        return

    if ensure_layer(index, target, branch):
         UI.print_success(f"Machine '{machine_name}' is ready.")
         print(f"  Run '{UI.BOLD}yocto-machine switch {machine_name}{UI.NC}' to switch to it.")


def ensure_layer(index, machine_info, branch):
    layer_name = machine_info['layer_name']
    vcs_url = machine_info['layer_vcs_url']
    subdir = machine_info['vcs_subdir']
    actual_branch = machine_info['actual_branch']
    
    UI.print_item("Checking Layer", layer_name)
    
    active = get_active_layers(WORKSPACE_ROOT)
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
            cmd = f"git clone --depth 1 -b {actual_branch} {vcs_url} {repo_path}"
        else:
            cmd = f"git clone --depth 1 {vcs_url} {repo_path}"
            
        if subprocess.run(cmd, shell=True).returncode != 0:
             UI.print_error("Clone failed.")
             return False
    
    layer_path = repo_path
    if subdir:
        layer_path = repo_path / subdir
        
    UI.print_item("Registering", str(layer_path))
    
    # Use bitbake-layers with sourced environment
    bitbake_yocto_dir = get_bitbake_yocto_dir(WORKSPACE_ROOT)
    rel_yocto = bitbake_yocto_dir.relative_to(WORKSPACE_ROOT)
    cmd = f"source {rel_yocto}/layers/openembedded-core/oe-init-build-env {rel_yocto}/build && bitbake-layers add-layer {layer_path}"
    
    result = subprocess.run(cmd, shell=True, cwd=WORKSPACE_ROOT, executable="/bin/bash", capture_output=True, text=True)
    if result.returncode == 0:
        return True
    
    UI.print_error(f"Failed to add layer '{layer_name}'.")
    if result.stdout:
        print(f"{UI.RED}{result.stdout}{UI.NC}")
    if result.stderr:
        print(f"{UI.RED}{result.stderr}{UI.NC}")
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

def list_machines(workspace_root, bitbake_yocto_dir):
    UI.print_item("Status", "Scanning for available machines...")
    
    from yocto_utils import get_available_machines
    machines = get_available_machines(workspace_root)

    if machines['poky']:
        UI.print_item("Poky/Core", ', '.join(machines['poky']))
    if machines['custom']:
        UI.print_item("Local Layer", ', '.join(machines['custom']))
    


def switch_machine(target_machine, local_conf):
    import config_manager
    
    # 1. Check for available fragments
    available_fragments = config_manager.get_available_fragments()
    target_fragment = None
    
    # Try exact match or suffix match for machine fragments
    # e.g. "machine/qemuarm64" or "my-layer/machine/my-machine"
    for name in available_fragments.keys():
        if name == f"machine/{target_machine}" or name.endswith(f"/machine/{target_machine}"):
            target_fragment = name
            break
    
    active_fragments = config_manager.get_fragments()
    
    # Helper to remove active machine fragments
    def disable_machine_fragments():
        for frag in active_fragments:
            if "/machine/" in frag or frag.startswith("machine/"):
                if frag != target_fragment: # Don't disable if it's the one we want (optimization)
                   config_manager.disable_fragment(frag)

    if target_fragment:
        UI.print_item("Configuration", f"Using fragment '{target_fragment}'")
        
        # Enable the fragment
        if target_fragment not in active_fragments:
            config_manager.enable_fragment(target_fragment)
            
        # Disable other machine fragments
        disable_machine_fragments()
        
        # Remove MACHINE from local.conf to avoid conflict
        if local_conf.exists():
            with open(local_conf, "r") as f:
                lines = f.readlines()
            
            new_lines = [line for line in lines if not line.strip().startswith("MACHINE")]
            
            if len(lines) != len(new_lines):
                 with open(local_conf, "w") as f:
                    f.writelines(new_lines)
                 UI.print_item("local.conf", "Removed explicit MACHINE setting (conflict prevented)")
                 
    else:
        UI.print_item("Configuration", f"Setting MACHINE in local.conf")
        
        # We are using local.conf, so we MUST disable any machine fragments to prevent conflict
        disable_machine_fragments()

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
    UI.print_success(f"Switched to {target_machine}")

def scaffold_machine(name, workspace_root, layer_name):
    from yocto_utils import sanitize_yocto_name
    name = sanitize_yocto_name(name, "machine")
    
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
    print(f"\n  Run '{UI.BOLD}yocto-machine switch {name}{UI.NC}' to activate it.")



if __name__ == "__main__":
    main()


