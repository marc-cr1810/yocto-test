#!/usr/bin/env python3
import sys
import os
import subprocess
import argparse
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI

def main():
    parser = argparse.ArgumentParser(description="Inspect Yocto variables (yocto-query)")
    parser.add_argument("variable", help="Variable name to query (e.g. IMAGE_INSTALL, WORKDIR)")
    parser.add_argument("recipe", nargs="?", help="Recipe context (optional, defaults to global)")
    parser.add_argument("--raw", action="store_true", help="Print raw output (don't strip quotes/whitespace)")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent

    # Construct bitbake command
    cmd = ["bitbake", "-e"]
    if args.recipe:
        cmd.append(args.recipe)
    
    UI.print_header("Yocto Variable Query")
    context = args.recipe if args.recipe else "Global Configuration"
    UI.print_item("Context", context)
    UI.print_item("Variable", args.variable)
    UI.print_item("Status", "Querying BitBake environment (this may take a few seconds)...")

    try:
        # Run bitbake -e
        # We pipe to grep manually in python to avoid shell injection risk if we used shell=True with user input
        # heavily, though bitbake args are fairly safe.
        # But parsing full output in python is safer and cleaner than piping to grep.
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=workspace_root)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            UI.print_error("BitBake execution failed.")
            if stderr:
                print(f"Error output:\n{stderr}")
            sys.exit(1)
            
        # Parse output for the variable
        # Format is usually: VARIABLE="value" or VARIABLE = "value"
        # bitbake -e output is final expanded values
        
        # Regex to find the variable definition
        # We look for ^VARIABLE= or ^export VARIABLE=
        pattern = re.compile(f'^(?:export )?{re.escape(args.variable)}=')
        
        found = False
        for line in stdout.splitlines():
            if pattern.match(line):
                found = True
                # Extract value part
                # override line with exact match
                value = line.split('=', 1)[1]
                
                # Check for "unexpanded" markers if any? No, -e gives expanded.
                
                if not args.raw:
                    # Clean up quotes
                    value = value.strip().strip('"').strip("'")
                
                UI.print_success("Value found:")
                print(f"\n{value}\n")
                
                # We stop at first match? bitbake -e usually outputs the final value last?
                # Actually bitbake -e outputs the final environment.
                # However, sometimes history is shown.
                # But the final valid assignment is what we want.
                # In parsed output, usually unique keys.
                break
        
        if not found:
            UI.print_warning(f"Variable '{args.variable}' not found in environment.")
            
    except Exception as e:
        UI.print_error(f"Execution error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
