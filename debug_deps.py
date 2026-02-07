import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from yocto_layer_index import LayerIndex
import json

branch = "master" # or whinlatter
print(f"Checking dependencies for 'meta-python' in '{branch}'...")
index = LayerIndex(branch=branch)

# 1. Get meta-python layer
layers = index.search_layers("meta-python")
if not layers:
    print("meta-python not found")
    sys.exit(1)
    
layer_id = layers[0]['id']
print(f"meta-python ID: {layer_id}")

# 2. Get layerbranch
# We need to find the layerbranch for this layer in this branch
# Search layerBranches filter=layer:ID;branch__name:branch
# But we can't filter by branch name easily multiple params.
# We can filter by layer:ID and verify branch in client.
branch_id = index.get_branch_id()
print(f"Branch ID: {branch_id}")

layerbranches = index._make_request("layerBranches", {"filter": f"layer:{layer_id}"})
target_lb = None
for lb in layerbranches:
    if lb['branch'] == branch_id:
        target_lb = lb
        break
        
if not target_lb:
    print("LayerBranch not found for this branch")
    sys.exit(1)
    
print(f"LayerBranch ID: {target_lb['id']}")

# 3. Get Dependencies
deps = index._make_request("layerDependencies", {"filter": f"layerbranch:{target_lb['id']}"})
print(f"Found {len(deps)} dependencies.")
for d in deps:
    dep_layer_id = d['dependency']
    # Resolve name
    dep_layer = index.get_layer_item(dep_layer_id)
    print(f" - Depends on: {dep_layer['name']} (ID: {dep_layer_id})")
