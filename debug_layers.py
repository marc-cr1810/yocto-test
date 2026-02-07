import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
# We need to import the function from yocto-get? 
# It's better to just run the command and parse it like yocto-get does.

import subprocess
GREEN = '\033[0;32m'
NC = '\033[0m'

BUILD_DIR = Path("bitbake-builds/poky-master/build").resolve()

def run_command(cmd, cwd=None, capture=False):
    try:
        if capture:
            return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, cwd=cwd).stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd)
            return True
    except subprocess.CalledProcessError as e:
        print(e)
        return None

def get_active_layers():
    output = run_command("bitbake-layers show-layers", cwd=BUILD_DIR, capture=True)
    if not output:
        return []
    layers = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] != "layer":
             layers.append(parts[0]) # name
    return layers

print("Checking active layers...")
active = get_active_layers()
print(f"Active layers: {active}")

if "meta" in active:
    print(f"{GREEN}meta found.{NC}")
if "core" in active: # sometimes it's named core?
    print(f"{GREEN}core found.{NC}")
