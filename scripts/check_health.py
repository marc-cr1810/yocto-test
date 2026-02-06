#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
from pathlib import Path

# ANSI Colors
BOLD = '\033[1m'
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m' # No Color

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024

def check_disk_space(path):
    total, used, free = shutil.disk_usage(path)
    percent = (used / total) * 100
    return {
        "total": format_size(total),
        "used": format_size(used),
        "free": format_size(free),
        "percent": percent
    }

def print_header(text):
    print(f"\n{BOLD}{CYAN}--- {text} ---{NC}")

def get_status_label(level):
    if level == "OK": return f"{GREEN}[ OK ]{NC}"
    if level == "WARN": return f"{YELLOW}[ WARN ]{NC}"
    if level == "CRIT": return f"{RED}[ CRIT ]{NC}"
    return f"[ {level} ]"

def main():
    workspace_root = Path(__file__).resolve().parent.parent
    build_dir = workspace_root / "bitbake-builds" / "poky-master" / "build"
    sstate_dir = workspace_root / "bitbake-builds" / "shared" / "sstate-cache"
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Yocto Workspace Health Dashboard{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    
    # 1. Disk Space
    print_header("Disk Space")
    try:
        disk = check_disk_space(workspace_root)
        status = "OK"
        if disk['percent'] > 90: status = "CRIT"
        elif disk['percent'] > 80: status = "WARN"
        
        print(f"  {get_status_label(status)} Usage: {disk['percent']:.1f}% used of {disk['total']}")
        print(f"           Available: {disk['free']}")
    except Exception as e:
        print(f"  {get_status_label('CRIT')} Error checking disk space: {e}")
        
    # 2. Cache Status
    print_header("Cache Health")
    if sstate_dir.exists():
        count = len(list(sstate_dir.glob("*")))
        status = "OK" if count > 0 else "WARN"
        print(f"  {get_status_label(status)} SState Cache: ~{count} objects in shared cache")
    else:
        print(f"  {get_status_label('WARN')} SState Cache: Not found (Shared cache not initialized?)")
        
    # 3. Environment Status
    print_header("Environment")
    bitbake_path = workspace_root / "bitbake-builds" / "poky-master" / "layers" / "bitbake"
    bb_status = "OK" if bitbake_path.exists() else "CRIT"
    print(f"  {get_status_label(bb_status)} BitBake Tools")
    
    build_status = "OK" if build_dir.exists() else "WARN"
    print(f"  {get_status_label(build_status)} Build Folder")
        
    # 4. Layer Sanity
    print_header("Layer Sanity")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from yocto_utils import find_custom_layer
        custom_layer = find_custom_layer(workspace_root)
        conf = custom_layer / "conf" / "layer.conf"
        status = "OK" if conf.exists() else "CRIT"
        print(f"  {get_status_label(status)} {custom_layer.name} layer")
    except RuntimeError as e:
        print(f"  {get_status_label('CRIT')} No custom layer found")

    # 5. Local Projects
    print_header("Local Projects")
    sw_dir = workspace_root / "sw"
    if sw_dir.exists():
        projects = [d.name for d in sw_dir.iterdir() if d.is_dir()]
        print(f"  Total Projects: {len(projects)}")
        for p in projects:
            recipe_exists = any((custom_layer).rglob(f"{p}_*.bb"))
            status = "OK" if recipe_exists else "WARN"
            label = "REGISTERED" if recipe_exists else "UNREGISTERED"
            print(f"    {get_status_label(status)} {p:15} ({label})")
    else:
        print(f"  {get_status_label('CRIT')} sw/ directory not found")

    print(f"\n{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
