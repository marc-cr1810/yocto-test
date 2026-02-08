#!/usr/bin/env python3
import os
import sys
import multiprocessing
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Optimize Yocto local.conf settings")
    parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    local_conf = workspace_root / "bitbake-builds" / "poky-master" / "build" / "conf" / "local.conf"

    UI.print_header("Optimizing Workspace Configuration")

    if not local_conf.exists():
        UI.print_error(f"Could not find {local_conf}", fatal=True)

    UI.print_item("Target", str(local_conf))

    # Shared directories (relative to build/ which is ${TOPDIR})
    # build is at bitbake-builds/poky-master/build
    # shared is at bitbake-builds/shared
    # So relative path is ../../shared/downloads
    shared_dir = workspace_root / "bitbake-builds" / "shared"
    dl_dir = shared_dir / "downloads"
    sstate_dir = shared_dir / "sstate-cache"
    
    dl_dir_rel = "../../shared/downloads"
    sstate_dir_rel = "../../shared/sstate-cache"

    dl_dir.mkdir(parents=True, exist_ok=True)
    sstate_dir.mkdir(parents=True, exist_ok=True)

    # CPU core count
    cores = multiprocessing.cpu_count()
    
    # Simple tuning: use all cores
    bb_threads = cores
    pm_threads = cores

    settings = {
        "DL_DIR": f'"${{TOPDIR}}/{dl_dir_rel}"',
        "SSTATE_DIR": f'"${{TOPDIR}}/{sstate_dir_rel}"',
        "BB_NUMBER_THREADS": f'"{bb_threads}"',
        "PARALLEL_MAKE": f'"-j {pm_threads}"',
    }

    with open(local_conf, "r") as f:
        lines = f.readlines()

    new_lines = []
    keys_handled = set()

    for line in lines:
        handling_line = False
        for key, value in settings.items():
            if line.startswith(f"{key} ") or line.startswith(f"{key}="):
                new_lines.append(f'{key} = {value}\n')
                keys_handled.add(key)
                handling_line = True
                break
        if not handling_line:
            new_lines.append(line)

    # Add missing keys at the end
    for key, value in settings.items():
        if key not in keys_handled:
            new_lines.append(f'{key} = {value}\n')

    with open(local_conf, "w") as f:
        f.writelines(new_lines)

    print(f"\n{UI.GREEN}Success! Applied optimization settings:{UI.NC}")
    for key, value in settings.items():
        print(f"  {UI.BOLD}{key:20}{UI.NC} = {value}")

if __name__ == "__main__":
    main()
