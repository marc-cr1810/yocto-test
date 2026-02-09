#!/usr/bin/env python3
import os
import sys
import argparse
import re
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from yocto_utils import (
        UI,
        run_command,
        get_bitbake_yocto_dir,
        find_custom_layer,
        get_all_custom_layers,
        set_cached_layer,
        get_cached_layer,
        get_cached_image,
        find_image_recipes,
        add_package_to_image,
        set_cached_image,
        sanitize_yocto_name
    )

    if args.url:
        UI.print_item("Git URL", args.url)
        # Treat first arg as name, sanitize it
        project_name = sanitize_yocto_name(args.project_path, "project")
        
        submodules_dir = workspace_root / "submodules"
        submodules_dir.mkdir(exist_ok=True)
        project_dir = submodules_dir / project_name
        
        if project_dir.exists():
            UI.print_warning(f"Submodule directory {project_dir} already exists.")
        else:
            UI.print_item("Status", f"Adding git submodule '{project_name}'...")
            if not (workspace_root / ".git").exists():
                UI.print_error("Workspace is not a git repository. Cannot use submodules.", fatal=True)
            try:
                subprocess.run(["git", "submodule", "add", args.url, str(project_dir)], cwd=workspace_root, check=True)
                UI.print_success("Submodule added.")
            except subprocess.CalledProcessError as e:
                UI.print_error(f"Failed to add submodule: {e}", fatal=True)
    else:
        project_dir = Path(args.project_path).resolve()
        # Sanitize project name
        project_name = sanitize_yocto_name(project_dir.name, "project")
        
        if not project_dir.exists():
            UI.print_error(f"Project directory {project_dir} does not exist.", fatal=True)

    # Auto-detect layer if not specified
    layer_name = args.layer
    if layer_name is None:
        cached_layer = get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            UI.print_error("No custom layers found.")
            print(f"  Run 'yocto-layers --new <name>' to create a layer first.")
            sys.exit(1)
        
        if len(all_layers) == 1:
            # Single layer - auto-select
            layer_name = all_layers[0].name.replace('meta-', '')
            UI.print_item("Auto-detected layer", f"meta-{layer_name}")
        elif cached_layer:
            # Use cached layer
            layer_name = cached_layer.replace('meta-', '')
            UI.print_item("Using last-used layer", f"meta-{layer_name}")
        else:
            # Multiple layers, use first one
            layer_name = all_layers[0].name.replace('meta-', '')
            UI.print_item("Using layer", f"meta-{layer_name}")
    
    # Prefixing logic
    if not layer_name.startswith("meta-"):
        layer_name = f"meta-{layer_name}"
        
    recipe_subdir = args.recipe_dir
    if not recipe_subdir.startswith("recipes-"):
        recipe_subdir = f"recipes-{recipe_subdir}"
    
    # Auto-detection logic
    project_type = args.type
    if project_type == "auto":
        if (project_dir / "CMakeLists.txt").exists():
            project_type = "cpp"
        elif (project_dir / "Cargo.toml").exists():
            project_type = "rust"
        elif (project_dir / "go.mod").exists():
            project_type = "go"
        elif (project_dir / "setup.py").exists() or (project_dir / "pyproject.toml").exists():
            project_type = "python"
        elif (project_dir / "configure.ac").exists() or (project_dir / "Makefile.am").exists():
            project_type = "autotools"
        elif (project_dir / "Makefile").exists():
            project_type = "makefile"
        else:
            UI.print_warning("Could not auto-detect project type. Defaulting to 'cpp'.")
            project_type = "cpp"
    
    UI.print_item("Project Type", project_type)
    
    # Define paths
    workspace_root = Path(__file__).resolve().parent.parent
    layer_dir = workspace_root / "yocto" / "layers" / layer_name
    recipe_dir = layer_dir / recipe_subdir / project_name
    recipe_file = recipe_dir / f"{project_name}_{args.pv}.bb"

    # Create directories
    recipe_dir.mkdir(parents=True, exist_ok=True)

    # Calculate relative path from recipe directory to project directory
    rel_project_path = os.path.relpath(project_dir, recipe_dir)

    # Detect dependencies based on project type
    detected_deps = []
    go_module_path = None
    if project_type in ["cpp", "cmake"]:
        detected_deps = detect_dependencies(project_dir, workspace_root, layer_dir)
    elif project_type == "rust":
        detected_deps = detect_rust_dependencies(project_dir)
    elif project_type == "go":
        go_module_path = detect_go_dependencies(project_dir)
        if go_module_path:
            UI.print_item("Go Module", go_module_path)
    elif project_type == "python":
        detected_deps = detect_python_dependencies(project_dir)
    
    if detected_deps:
        UI.print_item("Dependencies", ', '.join(detected_deps))
    
    # Recipe base content
    inherit_class = ""
    if project_type in ["cpp", "cmake"]:
        inherit_class = "inherit cmake"
    elif project_type == "autotools":
        inherit_class = "inherit autotools"
    elif project_type == "module":
        inherit_class = "inherit module"
    elif project_type == "rust":
        inherit_class = "inherit cargo"
    elif project_type == "go":
        inherit_class = "inherit go"
    elif project_type == "python":
        inherit_class = "inherit setuptools3"
    
    # Basic license handling
    license_text = 'LICENSE = "CLOSED"'
    lic_file = project_dir / "LICENSE"
    if lic_file.exists():
        license_text = 'LICENSE = "MIT"\nLIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"'
                
    depends_str = ""
    if detected_deps:
        depends_str = f'DEPENDS = "{" ".join(detected_deps)}"'

    # Recipe Content
    if project_type in ["cpp", "cmake", "autotools"]:
        recipe_content = f"""SUMMARY = "{project_name} application"
{license_text}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"
EXTERNALSRC_BUILD = "${{WORKDIR}}/build"

{depends_str}
"""
    
    elif project_type == "module":
        recipe_content = f"""SUMMARY = "{project_name} kernel module"
{license_text}
{pn_override}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"
EXTERNALSRC_BUILD = "${{WORKDIR}}/build"

# Set up build directory with symlinks to source files
do_configure:prepend() {{
    # Create build directory
    mkdir -p ${{EXTERNALSRC_BUILD}}
    
    # Symlink source files to build directory
    for file in ${{EXTERNALSRC}}/*; do
        filename=$(basename "$file")
        # Skip symlinks and hidden files
        if [ ! -L "$file" ] && [ "${{filename#.}}" = "$filename" ]; then
            ln -sf "$file" "${{EXTERNALSRC_BUILD}}/$filename"
        fi
    done
}}

{depends_str}

# Kernel modules need to be installed in specific way if strict
"""

    elif project_type == "rust":
        recipe_content = f"""SUMMARY = "{project_name} Rust application"
{license_text}
{pn_override}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"
EXTERNALSRC_BUILD = "${{WORKDIR}}/build"

{depends_str}
"""

    elif project_type == "go":
        go_import = go_module_path if go_module_path else project_name
        recipe_content = f"""SUMMARY = "{project_name} Go application"
{license_text}
{pn_override}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"

GO_IMPORT = "{go_import}"
GO_INSTALL = "${{GO_IMPORT}}/..."

# Remove -buildmode=pie to fix unique.Handle linker errors on some toolchains
GOBUILDFLAGS:remove = "-buildmode=pie"
INSANE_SKIP:${{PN}} += "textrel"

# Override compile task to work with externalsrc and Go modules
do_compile() {{
    cd ${{EXTERNALSRC}}
    export TMPDIR="${{GOTMPDIR}}"
    export GO111MODULE="on"
    ${{GO}} install ${{GO_LINKSHARED}} ${{GOBUILDFLAGS}} ${{GO_INSTALL}}
}}

# Custom install for externalsrc Go projects (skips source install)
do_install() {{
    install -d ${{D}}${{bindir}}
    # Check for binaries in standard Go build locations
    if [ -d ${{B}}/bin/${{TARGET_GOOS}}_${{TARGET_GOARCH}} ]; then
        install -m 0755 ${{B}}/bin/${{TARGET_GOOS}}_${{TARGET_GOARCH}}/* ${{D}}${{bindir}}/
    elif [ -d ${{B}}/bin ]; then
        install -m 0755 ${{B}}/bin/* ${{D}}${{bindir}}/
    fi
}}

# Allow network access for Go module downloads
do_compile[network] = "1"
"""

    elif project_type == "python":
        recipe_content = f"""SUMMARY = "{project_name} Python application"
{license_text}
{pn_override}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"

{depends_str}
"""

    with open(recipe_file, "w") as f:
        f.write(recipe_content)

    UI.print_success(f"Created {project_type} recipe for '{project_name}'")
    UI.print_item("Path", str(recipe_file))

    # Image Integration
    # Default add_to_image to True if not a library and not explicitly set
    add_to_image_flag = args.add_to_image
    if add_to_image_flag is None:
        add_to_image_flag = not args.library

    image_name = None  # Initialize to avoid UnboundLocalError
    if add_to_image_flag:
        image_name = args.image
        if not image_name:
            image_name = get_cached_image(workspace_root)
        
        # Build env info
        bitbake_yocto_dir = get_bitbake_yocto_dir(workspace_root)
        build_dir = bitbake_yocto_dir / "build"
        if not image_name:
            # Try to find custom images
            layer_path = find_custom_layer(workspace_root)
            images = find_image_recipes(layer_path)
            if images:
                image_name = images[0] # Default to first found
                UI.print_item("Auto-selected image", image_name)
        
        if image_name:
            UI.print_item("Integration", f"Adding to {image_name}...")
            if add_package_to_image(workspace_root, image_name, project_name):
                UI.print_success(f"Successfully added '{project_name}' to {image_name}")
                set_cached_image(workspace_root, image_name)
            else:
                UI.print_error(f"Failed to add '{project_name}' to {image_name}")
    else:
        UI.print_item("Image Integration", "Skipped (library or disabled)")

    print(f"\n  {UI.BOLD}Action Required:{UI.NC}")
    print(f"    Run 'yocto-build {project_name}' to build recipe.")
    print(f"    Run 'yocto-build {image_name or 'core-image-falcon'}' to build image.")

if __name__ == "__main__":
    main()
