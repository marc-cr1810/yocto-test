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
    
    # ... (logic remains same)

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
