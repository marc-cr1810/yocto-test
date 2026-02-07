import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from yocto_utils import get_yocto_branch
from yocto_layer_index import LayerIndex

root = Path(".").resolve()
print(f"Workspace Root: {root}")

branch = get_yocto_branch(root)
print(f"Detected Branch: '{branch}'")

print("Checking if this branch exists in Layer Index...")
index = LayerIndex(branch=branch)
bid = index.get_branch_id()
if bid:
    print(f"SUCCESS: Branch '{branch}' exists with ID {bid}.")
else:
    print(f"FAILURE: Branch '{branch}' NOT found in Layer Index.")
    
    # List valid branches?
    print("Listing valid branches matching 'master' or common names...")
    # This might require a broad search or hardcoded check
    pass
