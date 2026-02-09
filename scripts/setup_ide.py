#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer, get_all_custom_layers, get_bitbake_yocto_dir

def find_file(base_dir, pattern):
    for path in base_dir.rglob(pattern):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Setup VS Code integration for Yocto")
    parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    build_dir = get_bitbake_yocto_dir(workspace_root) / "build"
    
    UI.print_header("Setting up IDE & Toolchain Sync")
    
    UI.print_item("Status", "Searching for Yocto toolchain...")
    
    # 1. Find the cross-compiler
    compiler_path = None
    compiler_dir = build_dir / "tmp" / "sysroots-components" / "x86_64"
    if compiler_dir.exists():
        compiler_path = find_file(compiler_dir, "*-gcc")
        
    if not compiler_path:
        # Fallback search in tmp
        UI.print_warning("Standard compiler path not found, searching broader...")
        compiler_path = find_file(build_dir / "tmp", "*-gcc")

    if not compiler_path:
        UI.print_error("Could not find cross-compiler.", fatal=True)

    UI.print_success(f"Found compiler: {compiler_path.name}")

    # 2. Find the target sysroot
    sysroot_path = None
    target_work_dir = build_dir / "tmp" / "work" / "qemuarm64-poky-linux"
    if target_work_dir.exists():
        for path in target_work_dir.rglob("recipe-sysroot"):
            if path.is_dir():
                sysroot_path = path
                break

    if not sysroot_path:
        UI.print_warning("Could not find a representative target sysroot.")
    else:
        UI.print_success(f"Found sysroot: {sysroot_path.name}")

    # 3. Generate .vscode/cmake-kits.json
    vscode_dir = workspace_root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    kits_file = vscode_dir / "cmake-kits.json"

    # Convert paths to be relative to workspace root for portability in VS Code
    def to_ws_relative(path):
        try:
            rel = os.path.relpath(path, workspace_root)
            return f"${{workspaceFolder}}/{rel}"
        except ValueError:
            return str(path)

    kit = {
        "name": "Yocto Toolchain",
        "compilers": {
            "C": to_ws_relative(compiler_path),
            "CXX": to_ws_relative(str(compiler_path).replace("-gcc", "-g++"))
        }
    }

    if sysroot_path:
        kit["toolchainFile"] = "" # Use compiler flags instead of toolchain file for simplicity
        kit["cmakeSettings"] = {
            "CMAKE_SYSROOT": to_ws_relative(sysroot_path)
        }

    # Load existing kits if they exist
    kits = []
    if kits_file.exists():
        try:
            with open(kits_file, "r") as f:
                kits = json.load(f)
        except:
            pass

    # Update or add the kit
    found = False
    for i, k in enumerate(kits):
        if k.get("name") == "Yocto Toolchain":
            kits[i] = kit
            found = True
            break
    if not found:
        kits.append(kit)

    with open(kits_file, "w") as f:
        json.dump(kits, f, indent=4)

    print(f"\n{UI.GREEN}Success! Updated {kits_file}{UI.NC}")
    print(f"{UI.BOLD}Action Required:{UI.NC}")
    print("  In VS Code, run 'CMake: Select a Kit' and choose 'Yocto Toolchain'.")

if __name__ == "__main__":
    main()
