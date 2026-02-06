#!/usr/bin/env python3
import sys
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build a Yocto recipe or image")
    parser.add_argument("target", nargs="?", default=None, help="Recipe or image name to build (auto-detects image if not specified)")
    parser.add_argument("-c", "--clean", action="store_true", help="Clean before building")
    parser.add_argument("--cleansstate", action="store_true", help="Clean shared state before building")
    args = parser.parse_args()
    
    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'
    
    target = args.target
    
    # Auto-detect image if no target specified
    if target is None:
        print(f"{BOLD}Auto-detecting image...{NC}")
        
        workspace_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from yocto_utils import get_cached_image, find_custom_layer, find_image_recipes
        
        # Try to get cached image
        cached_image = get_cached_image(workspace_root)
        
        # Try to find layer and recipes
        layer_dir = find_custom_layer(workspace_root, None)
        if layer_dir:
            recipes = find_image_recipes(layer_dir)
            
            if recipes:
                if cached_image and cached_image in recipes:
                    target = cached_image
                    print(f"  Using last-used image: {BOLD}{target}{NC}")
                elif len(recipes) == 1:
                    target = recipes[0]
                    print(f"  Auto-detected: {BOLD}{target}{NC}")
                else:
                    # Multiple recipes, use cached or first
                    target = cached_image if cached_image in recipes else recipes[0]
                    print(f"  Using: {BOLD}{target}{NC}")
        
        if target is None:
            print(f"{YELLOW}No image found. Please specify a target.{NC}")
            print(f"Usage: yocto-build <recipe-name>")
            sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Building Yocto Recipe{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"  Target       : {BOLD}{target}{NC}")
    
    # Clean if requested
    if args.cleansstate:
        print(f"  Cleaning shared state...")
        subprocess.run(["bitbake", "-c", "cleansstate", target])
    elif args.clean:
        print(f"  Cleaning...")
        subprocess.run(["bitbake", "-c", "clean", target])
    
    # Build
    print(f"\n{BOLD}Building...{NC}")
    result = subprocess.run(["bitbake", target])
    
    if result.returncode == 0:
        print(f"\n{GREEN}Success! Built {target}{NC}")
    else:
        print(f"\n{BOLD}Build failed. Check logs with {GREEN}yocto-err{NC}")
        sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
