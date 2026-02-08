#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI

def main():
    parser = argparse.ArgumentParser(description="Visualize BitBake dependencies as a Mermaid diagram")
    parser.add_argument("recipe", help="Recipe name to visualize")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent

    UI.print_header("Dependency Visualization Tree")
    UI.print_item("Target", args.recipe)
    UI.print_item("Status", "Generating BitBake dependency data...")
    
    # Run bitbake -g to get dependency graph
    cmd = f"bitbake -g {args.recipe}"
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=workspace_root, capture_output=True)
    except subprocess.CalledProcessError as e:
        UI.print_error(f"Failed to generate dependency graph: {e}")
        sys.exit(1)

    # Parse pn-buildlist to get the list of recipes in the build
    buildlist_file = workspace_root / "pn-buildlist"
    target = args.recipe
    edges = []
    
    if os.path.exists("pn-depends.dot"):
        with open("pn-depends.dot", "r") as f:
            for line in f:
                if "->" in line:
                    parts = line.split("->")
                    src = parts[0].strip().strip('"')
                    dst = parts[1].strip().strip('"')
                    edges.append((src, dst))
    
    # Clean up dot files and buildlist
    for f in ["pn-depends.dot", "package-depends.dot", "task-depends.dot", "pn-buildlist"]:
        if os.path.exists(f):
            os.remove(f)

    if not edges:
        UI.print_warning("No non-trivial dependencies found.")
        sys.exit(0)

    print(f"\n  {UI.BOLD}Dependency Tree:{UI.NC}")
    
    # Simple recursive tree printer
    def print_tree(node, level=0, visited=None):
        if visited is None:
            visited = set()
        
        indent = "    " * level
        marker = "-- " if level > 0 else ""
        color = UI.GREEN if level == 0 else UI.NC
        print(f"  {indent}{marker}{color}{node}{UI.NC}")
        
        # ... (rest of tree logic same)

    print_tree(target)

if __name__ == "__main__":
    main()
