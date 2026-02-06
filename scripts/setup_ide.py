#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

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
    build_dir = workspace_root / "bitbake-builds" / "poky-master" / "build"
    
    print("Searching for Yocto toolchain...")
    
    # 1. Find the cross-compiler
    # We look for something like 'aarch64-poky-linux-gcc'
    compiler_path = None
    compiler_dir = build_dir / "tmp" / "sysroots-components" / "x86_64"
    if compiler_dir.exists():
        compiler_path = find_file(compiler_dir, "*-gcc")
        
    if not compiler_path:
        # Fallback search in tmp
        print("Warning: Standard compiler path not found, searching broader...")
        compiler_path = find_file(build_dir / "tmp", "*-gcc")

    if not compiler_path:
        print("Error: Could not find cross-compiler.")
        sys.exit(1)

    print(f"Found compiler: {compiler_path}")

    # 2. Find the target sysroot
    # We look for things like 'recipe-sysroot' in a target directory
    sysroot_path = None
    target_work_dir = build_dir / "tmp" / "work" / "qemuarm64-poky-linux"
    if target_work_dir.exists():
        # Just pick the first recipe-sysroot we find as a baseline
        for path in target_work_dir.rglob("recipe-sysroot"):
            if path.is_dir():
                sysroot_path = path
                break

    if not sysroot_path:
        print("Warning: Could not find a representative target sysroot.")
        # We can still proceed with just the compiler
    else:
        print(f"Using sysroot: {sysroot_path}")

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
        # Add --sysroot to compiler flags
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

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Setting up IDE & Toolchain Sync{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    # ... (logic remains same)

    print(f"\n{GREEN}Success! Updated {kits_file}{NC}")
    print(f"{BOLD}Action Required:{NC}")
    print("  In VS Code, run 'CMake: Select a Kit' and choose 'Yocto Toolchain'.")
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
