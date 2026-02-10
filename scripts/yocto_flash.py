#!/usr/bin/env python3
import sys
import os
import subprocess
import argparse
import shutil
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_built_images, get_machine_from_config

def get_block_devices():
    """Return a list of block devices with their details."""
    devices = []
    try:
        # lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL
        cmd = ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,RM"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        data = json.loads(result.stdout)
        
        for device in data.get('blockdevices', []):
            devices.append(device)
            
    except Exception:
        pass
    return devices

def is_safe_device(device_name):
    """
    Check if a device is safe to write to.
    UNSAFE if:
    - It has partitions mounted as / or /boot
    - It is not removable (optional check, but good heuristic)
    """
    # Use lsblk to check mountpoints of device and its children
    cmd = ["lsblk", "/dev/" + device_name, "-J", "-o", "NAME,MOUNTPOINT"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        data = json.loads(result.stdout)
        
        def check_mounts(node):
            if node.get('mountpoint') in ['/', '/boot', '/home']:
                return False
            for child in node.get('children', []):
                if not check_mounts(child):
                    return False
            return True
            
        for dev in data.get('blockdevices', []):
            if not check_mounts(dev):
                return False
                
    except Exception:
        # If we can't verify, assume unsafe
        return False
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Safely write Yocto image to SD card (yocto-flash)")
    parser.add_argument("image", nargs="?", help="Image name (e.g. core-image-falcon)")
    parser.add_argument("device", nargs="?", help="Target device (e.g. sdb)")
    parser.add_argument("--machine", help="Force specific machine")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    
    UI.print_header("Yocto Image Flasher")

    # 1. Select Image
    if not args.image:
        # Interactive selection
        images = find_built_images(workspace_root, args.machine)
        from yocto_utils import select_image_interactive, get_cached_image
        selected = select_image_interactive(workspace_root, images, get_cached_image(workspace_root), "flash")
        if not selected:
            sys.exit(1)
        image_name = selected
        
        # Find the actual file path again for the selected name
        # (This is a bit redundant but safe)
        image_path = None
        for img in images:
            if img['name'] == image_name:
                image_path = img['path']
                break
    else:
        # Resolve explicit image
        images = find_built_images(workspace_root, args.machine)
        image_name = args.image
        image_path = None
        for img in images:
            if img['name'] == image_name:
                image_path = img['path']
                break
        
        if not image_path:
             UI.print_error(f"Image '{image_name}' not found in deploy directory.")
             sys.exit(1)

    UI.print_item("Image", f"{image_name} ({image_path.name})")

    # 2. Select Device
    if not args.device:
        # List removable devices
        print("\n  Scanning for removable devices...")
        devices = get_block_devices()
        candidates = []
        for dev in devices:
            # Filter logic: Removable (rm=True) or explicit user choice?
            # Let's show all "disk" types that are not system
            if dev.get('type') == 'disk':
                name = dev.get('name')
                if is_safe_device(name):
                     candidates.append(dev)
        
        if not candidates:
             UI.print_error("No safe removable devices found.")
             print("  Please insert an SD card or specify device manually.")
             sys.exit(1)
             
        print("\n  Available Devices:")
        for i, dev in enumerate(candidates, 1):
             print(f"    {i}. {dev.get('name')} ({dev.get('size')}) - {dev.get('model', 'Unknown')}")
             
        try:
            choice = input(f"\n  Select device [1-{len(candidates)}]: ").strip()
            if not choice: sys.exit(1)
            device_name = candidates[int(choice)-1]['name']
        except:
            sys.exit(1)
    else:
        device_name = args.device.replace("/dev/", "")
        if not is_safe_device(device_name):
            UI.print_error(f"Device /dev/{device_name} appears to be a system drive!")
            UI.print_error("Safety check failed. Aborting to prevent data loss.", fatal=True)

    target_dev = f"/dev/{device_name}"
    UI.print_item("Target", target_dev)
    
    # 3. Confirm
    print(f"\n  {UI.RED}{UI.BOLD}WARNING: All data on {target_dev} will be erased!{UI.NC}")
    if input("  Type 'yes' to continue: ").strip() != 'yes':
        print("  Aborted.")
        sys.exit(0)

    # 4. Flash
    # 4. Flash
    # Prefer bmaptool if available and bmap file exists
    bmaptool_path = shutil.which("bmaptool")
    
    # Check multiple locations for bmap file
    bmap_candidates = [
        image_path.with_suffix(".bmap"),            # e.g. image.wic.bz2 -> image.wic.bmap
        image_path.with_name(image_path.name + ".bmap") # e.g. image.wic -> image.wic.bmap
    ]
    
    bmap_file = None
    for cand in bmap_candidates:
        if cand.exists():
            bmap_file = cand
            break
    
    use_bmap = False
    if bmaptool_path and bmap_file:
        use_bmap = True
        UI.print_item("Method", "bmaptool (fast & safe)")
        UI.print_item("Bmap", bmap_file.name)
    else:
        UI.print_item("Method", "dd (sector-by-sector)")

    UI.print_item("Status", "Flashing...")
    
    try:
        if use_bmap:
            # bmaptool handles decompression automatically
            cmd = ["sudo", bmaptool_path, "copy", str(image_path), target_dev, "--bmap", str(bmap_file)]
            subprocess.run(cmd, check=True)
        else:
            # Fallback to dd
            cmd = ["sudo", "dd", f"if={image_path}", f"of={target_dev}", "bs=4M", "status=progress", "conv=fsync"]
            
            # If compressed, we need to decompress
            if str(image_path).endswith(".tar.bz2"):
                # Not bootable typically
                UI.print_warning("Selected image is a tarball, not a disk image. It may not be bootable.")
                subprocess.run(cmd, check=True)
            elif str(image_path).endswith(".gz"):
                cmd = f"gunzip -c {image_path} | sudo dd of={target_dev} bs=4M status=progress conv=fsync"
                subprocess.run(cmd, shell=True, check=True)
            elif str(image_path).endswith(".bz2"):
                cmd = f"bunzip2 -c {image_path} | sudo dd of={target_dev} bs=4M status=progress conv=fsync"
                subprocess.run(cmd, shell=True, check=True)
            elif str(image_path).endswith(".xz"):
                 cmd = f"xz -dc {image_path} | sudo dd of={target_dev} bs=4M status=progress conv=fsync"
                 subprocess.run(cmd, shell=True, check=True)
            else:
                subprocess.run(cmd, check=True)
        
        UI.print_success("Flashing complete!")
        print("  You may now remove the SD card.")
        
    except subprocess.CalledProcessError as e:
        UI.print_error(f"Flashing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Aborted by user.")
        sys.exit(130)
