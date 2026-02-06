#!/usr/bin/env python3
import sys
import subprocess
import argparse
import shutil
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build and deploy a Yocto recipe to an installation directory or remote target")
    parser.add_argument("target", help="Recipe name to build and deploy")
    parser.add_argument("--dest", "-d", help="Destination directory (default: ./deploy/<recipe>)")
    parser.add_argument("--remote", "-r", help="Remote target (user@host or user@host:/path, defaults to / if path omitted)")
    parser.add_argument("--clean", action="store_true", help="Clean before building")
    parser.add_argument("--no-build", action="store_true", help="Skip build, just deploy existing artifacts")
    parser.add_argument("--ssh-opts", default="", help="Additional SSH options (e.g., '-p 2222 -i key.pem')")
    args = parser.parse_args()
    
    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'
    
    workspace_root = Path(__file__).resolve().parent.parent
    
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Build and Deploy Recipe{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"  Target       : {BOLD}{args.target}{NC}")
    
    # Determine destination
    if args.dest:
        dest_dir = Path(args.dest).resolve()
    else:
        dest_dir = workspace_root / "deploy" / args.target
    
    print(f"  Destination  : {BOLD}{dest_dir}{NC}")
    
    # Build if not skipped
    if not args.no_build:
        if args.clean:
            print(f"\n{BOLD}Cleaning...{NC}")
            subprocess.run(["bitbake", "-c", "clean", args.target])
        
        print(f"\n{BOLD}Building...{NC}")
        result = subprocess.run(["bitbake", args.target])
        
        if result.returncode != 0:
            print(f"\n{BOLD}Build failed. Check logs with {GREEN}yocto-err{NC}")
            sys.exit(1)
    
    # Find the recipe's deploy directory
    print(f"\n{BOLD}Deploying artifacts...{NC}")
    
    # Get TMPDIR from bitbake environment
    result = subprocess.run(
        ["bitbake", "-e", args.target],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"{BOLD}Error: Could not get recipe environment{NC}")
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
        print(f"{BOLD}Error: Could not determine WORKDIR{NC}")
        print(f"{YELLOW}Tip: Make sure the recipe exists and built successfully{NC}")
        sys.exit(1)
    
    # The work directory contains the recipe's build artifacts
    deploy_dir = Path(workdir)
    
    if not deploy_dir.exists():
        print(f"{YELLOW}Warning: Work directory does not exist: {deploy_dir}{NC}")
        print(f"\n{BOLD}Tip:{NC} Check if the recipe built successfully with {GREEN}bitbake {args.target}{NC}")
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
        
        print(f"  Remote Host  : {BOLD}{remote_host}{NC}")
        print(f"  Remote Path  : {BOLD}{remote_path}{NC}")
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
        print(f"  Copying from image directory...")
        for item in image_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(image_dir)
                dest_file = actual_dest / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_file)
                deployed_count += 1
                # Show actual install path for remote, relative path for local
                if is_remote:
                    print(f"    {remote_path.rstrip('/')}/{rel_path}")
                else:
                    print(f"    {rel_path}")
    
    # Also check packages-split for additional files
    elif packages_split.exists():
        print(f"  Copying from packages-split...")
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
                            print(f"    {remote_path.rstrip('/')}/{rel_path}")
                        else:
                            print(f"    {rel_path}")
    else:
        print(f"{YELLOW}Warning: No image or packages-split directory found{NC}")
        print(f"  This recipe may not install any files.")
    
    # If remote, use rsync to transfer (with scp fallback)
    if is_remote and deployed_count > 0:
        print(f"\n{BOLD}Transferring to remote target...{NC}")
        
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
                print(f"{YELLOW}  rsync not available on target, using scp...{NC}")
                
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
                    print(f"\n{BOLD}Error: Remote transfer failed{NC}")
                    if stderr:
                        print(f"{stderr.decode()}")
                    sys.exit(1)
            else:
                # Clean up temp directory
                shutil.rmtree(temp_deploy_dir)
                print(f"\n{BOLD}Error: Remote transfer failed{NC}")
                print(f"{result.stderr}")
                sys.exit(1)
        else:
            # Clean up temp directory after successful rsync
            shutil.rmtree(temp_deploy_dir)
        
        print(f"\n{GREEN}Success! Deployed {deployed_count} files to remote target:{NC}")
        print(f"  {args.remote}")
    elif deployed_count > 0:
        print(f"\n{GREEN}Success! Deployed {deployed_count} files to:{NC}")
        print(f"  {dest_dir}")
    else:
        print(f"\n{YELLOW}No files deployed. Recipe may not install anything.{NC}")
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
