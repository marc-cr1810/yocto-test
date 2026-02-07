import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from yocto_layer_index import LayerIndex
import json

branch = "whinlatter"
print(f"Checking 'tailscale' in branch '{branch}'...")
index = LayerIndex(branch=branch)
bid = index.get_branch_id()
if not bid:
    print(f"Branch '{branch}' invalid.")
    sys.exit(1)

recipes = index.search_recipes("tailscale")
found = False
for r in recipes:
    info = index.get_recipe_layer_info(r)
    if info:
        print(f"FOUND: {info['recipe_name']} (v{info['version']}) in {info['layer_name']}")
        found = True

if not found:
    print(f"No tailscale found in branch '{branch}'.")
