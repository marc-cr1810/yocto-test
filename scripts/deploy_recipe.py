#!/usr/bin/env python3
import sys
import os
import subprocess
import argparse
import shutil
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI

def main():
    parser = argparse.ArgumentParser(description="Build and deploy a Yocto recipe to an installation directory or remote target")
    parser.add_argument("target", help="Recipe name to build and deploy")
    parser.add_argument("--dest", "-d", help="Destination directory (default: ./deploy/<recipe>)")
    parser.add_argument("--remote", "-r", help="Remote target (user@host or user@host:/path, defaults to / if path omitted)")
    parser.add_argument("--clean", action="store_true", help="Clean before building")
    parser.add_argument("--no-build", action="store_true", help="Skip build, just deploy existing artifacts")
    parser.add_argument("--ssh-opts", default="", help="Additional SSH options (e.g., '-p 2222 -i key.pem')")
    args = parser.parse_args()
    
    workspace_root = Path(__file__).resolve().parent.parent
    
    UI.print_header("Build and Deploy Recipe")
    UI.print_item("Target", args.target)
    
    # Determine destination
    if args.dest:
        dest_dir = Path(args.dest).resolve()
    else:
        dest_dir = workspace_root / "deploy" / args.target
    
    UI.print_item("Destination", str(dest_dir))
    
    # Build if not skipped
    if not args.no_build:
        if args.clean:
            UI.print_item("Action", "Cleaning...")
            subprocess.run(["bitbake", "-c", "clean", args.target])
        
        UI.print_item("Action", "Building...")
        result = subprocess.run(["bitbake", args.target])
        
        if result.returncode != 0:
            UI.print_error("Build failed.")
            print(f"  Check logs with {UI.GREEN}yocto-err{UI.NC}")
            sys.exit(1)
    
    # Find the recipe's deploy directory
    UI.print_item("Status", "Deploying artifacts...")
    
    # Get TMPDIR from bitbake environment
    result = subprocess.run(
        ["bitbake", "-e", args.target],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        UI.print_error("Could not get recipe environment")
        sys.exit(1)
    
    # Parse WORKDIR from bitbake -e output (most reliable)
    workdir = None
    tmpdir = None
    
    for line in result.stdout.split('\n'):
        if line.startswith('WORKDIR='):
            workdir = line.split('=', 1)[1].strip('"')
        elif line.startswith('TMPDIR='):
            tmpdir = line.split('=', 1)[1].strip('"')
    
    if not workdir:
        UI.print_error("Could not determine WORKDIR")
        UI.print_warning("Make sure the recipe exists and built successfully")
        sys.exit(1)
    
    # The work directory contains the recipe's build artifacts
    deploy_dir = Path(workdir)
    
    if not deploy_dir.exists():
        UI.print_warning(f"Work directory does not exist: {deploy_dir}")
        print(f"  Check if the recipe built successfully with {UI.GREEN}bitbake {args.target}{UI.NC}")
        sys.exit(1)
    
    # Find the image/packages directory
    image_dir = deploy_dir / "image"
    packages_split = deploy_dir / "packages-split"
    
    # Create destination (for local) or prepare for remote
    is_remote = args.remote is not None
    
    if is_remote:
        # Parse remote target
        if ':' in args.remote:
            remote_host, remote_path = args.remote.rsplit(':', 1)
            # Default to / if path is empty
            if not remote_path or remote_path == '':
                remote_path = '/'
        else:
            # No colon - just host, default to /
            remote_host = args.remote
            remote_path = '/'
        
        UI.print_item("Remote Host", remote_host)
        UI.print_item("Remote Path", remote_path)
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)
    
    deployed_count = 0
    temp_deploy_dir = None
    
    # For remote deployment, create a temporary staging directory
    if is_remote:
        import tempfile
        temp_deploy_dir = Path(tempfile.mkdtemp(prefix="yocto-deploy-"))
        actual_dest = temp_deploy_dir
    else:
        actual_dest = dest_dir
    
    # Deploy from image directory (preferred - contains installed files)
    if image_dir.exists():
        UI.print_item("Source", "image directory")
        for item in image_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(image_dir)
                dest_file = actual_dest / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
                deployed_count += 1
                # Show actual install path for remote, relative path for local
                if is_remote:
                    print(f"      {remote_path.rstrip('/')}/{rel_path}")
                else:
                    print(f"      {rel_path}")
    
    # Also check packages-split for additional files
    elif packages_split.exists():
        UI.print_item("Source", "packages-split")
        for package_dir in packages_split.iterdir():
            if package_dir.is_dir():
                for item in package_dir.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(package_dir)
                        dest_file = actual_dest / rel_path
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest_file)
                        deployed_count += 1
                        # Show actual install path for remote, relative path for local
                        if is_remote:
                            print(f"      {remote_path.rstrip('/')}/{rel_path}")
                        else:
                            print(f"      {rel_path}")
    else:
        UI.print_warning("No image or packages-split directory found")
        print(f"  This recipe may not install any files.")
    
    # If remote, use rsync to transfer (with scp fallback)
    if is_remote and deployed_count > 0:
        UI.print_item("Action", "Transferring to remote target...")
        
        # Try rsync first (faster and more efficient)
        rsync_cmd = ["rsync", "-avz", "--progress"]
        
        # Add SSH options if provided
        if args.ssh_opts:
            rsync_cmd.extend(["-e", f"ssh {args.ssh_opts}"])
        
        # Add source and destination
        rsync_cmd.append(f"{temp_deploy_dir}/")
        rsync_cmd.append(f"{remote_host}:{remote_path}/")
        
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)
        
        # If rsync failed, try scp as fallback
        if result.returncode != 0:
            if "rsync: not found" in result.stderr or "command not found" in result.stderr:
                UI.print_warning("rsync not available on target, using scp...")
                
                # Use tar + ssh for efficient directory transfer
                tar_cmd = ["tar", "-czf", "-", "-C", str(temp_deploy_dir), "."]
                ssh_cmd = ["ssh"]
                
                if args.ssh_opts:
                    ssh_cmd.extend(args.ssh_opts.split())
                
                ssh_cmd.extend([remote_host, f"tar -xzf - -C {remote_path}"])
                
                # Pipe tar through ssh
                tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
                ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                tar_proc.stdout.close()
                
                stdout, stderr = ssh_proc.communicate()
                
                # Clean up temp directory
                shutil.rmtree(temp_deploy_dir)
                
                if ssh_proc.returncode != 0:
                    UI.print_error("Remote transfer failed")
                    if stderr:
                        print(f"      {stderr.decode()}")
                    sys.exit(1)
            else:
                # Clean up temp directory
                shutil.rmtree(temp_deploy_dir)
                UI.print_error("Remote transfer failed")
                print(f"      {result.stderr}")
                sys.exit(1)
        else:
            # Clean up temp directory after successful rsync
            shutil.rmtree(temp_deploy_dir)
        
        UI.print_success(f"Deployed {deployed_count} files to {args.remote}")
    elif deployed_count > 0:
        UI.print_success(f"Deployed {deployed_count} files to {dest_dir}")
    else:
        UI.print_warning("No files deployed. Recipe may not install anything.")

if __name__ == "__main__":
    main()
