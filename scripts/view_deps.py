#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Visualize BitBake dependencies as a Mermaid diagram")
    parser.add_argument("recipe", help="Recipe name to visualize")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Dependency Visualization Tree{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    print(f"  Target       : {BOLD}{args.recipe}{NC}")
    print(f"  Status       : Generating BitBake dependency data...")
    
    # ... (logic remains same)

    if not edges:
        print(f"  {BOLD}Status       : No non-trivial dependencies found.{NC}")
        sys.exit(0)

    print(f"\n{BOLD}Dependency Tree:{NC}")
    
    # Simple recursive tree printer
    def print_tree(node, level=0, visited=None):
        if visited is None:
            visited = set()
        
        indent = "    " * level
        marker = "└── " if level > 0 else ""
        color = GREEN if level == 0 else NC
        print(f"{indent}{marker}{color}{node}{NC}")
        
        # ... (rest of tree logic same)

    print_tree(target)
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
