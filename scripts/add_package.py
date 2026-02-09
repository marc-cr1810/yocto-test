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
    set_cached_image
)

# Special case mappings (only for packages that don't follow the lowercase convention)
CMAKE_TO_YOCTO_MAP = {
    "OpenSSL": "openssl",
    "ZLIB": "zlib",
    "GTest": "googletest",
    "Protobuf": "protobuf",
    "CURL": "curl",
    "SQLite3": "sqlite3",
    "Threads": "",  # Built-in to toolchain
}

def detect_dependencies(project_dir, workspace_root, layer_dir=None):
    deps = set()
    cmake_lists = project_dir / "CMakeLists.txt"
    if cmake_lists.exists():
        with open(cmake_lists, "r") as f:
            content = f.read()
            
            # Find common CMake find_package calls
            matches = re.findall(r"find_package\s*\(\s*(\w+)", content, re.IGNORECASE)
            for m in matches:
                # Check if it's in the special case map
                if m in CMAKE_TO_YOCTO_MAP:
                    yocto_dep = CMAKE_TO_YOCTO_MAP[m]
                    if yocto_dep:  # Skip empty strings (like Threads)
                        deps.add(yocto_dep)
                else:
                    # Check if it's an internal dependency (another project in sw/)
                    # Search across all language directories
                    sw_dir = workspace_root / "sw"
                    found = False
                    for lang_dir in ["cpp", "rust", "go", "python", "module"]:
                        if (sw_dir / lang_dir / m.lower()).exists():
                            deps.add(m.lower())
                            found = True
                            break
                    
                    if not found:
                        # Check if a recipe exists for this dependency in the layer
                        if layer_dir:
                            recipe_pattern = f"{m.lower()}_*.bb"
                            if list(layer_dir.rglob(recipe_pattern)):
                                deps.add(m.lower())
                                found = True
                        
                        if not found:
                            # Default: convert to lowercase (most packages follow this convention)
                            # e.g., spdlog -> spdlog, nlohmann_json -> nlohmann_json
                            deps.add(m.lower())
    return sorted(list(filter(None, deps)))

def detect_rust_dependencies(project_dir):
    """Detect Rust dependencies from Cargo.toml"""
    deps = set()
    cargo_toml = project_dir / "Cargo.toml"
    if cargo_toml.exists():
        with open(cargo_toml, "r") as f:
            content = f.read()
            # Simple regex to find dependencies (not a full TOML parser)
            # Matches lines like: serde = "1.0"
            matches = re.findall(r'^(\w+)\s*=', content, re.MULTILINE)
            for dep in matches:
                # Filter out package metadata fields
                if dep not in ['name', 'version', 'edition', 'authors']:
                    deps.add(dep)
    return sorted(list(deps))

def detect_go_dependencies(project_dir):
    """Detect Go module path from go.mod
    
    Note: Go dependencies are NOT added to DEPENDS as the Go build system
    handles module dependencies automatically during build.
    """
    go_mod = project_dir / "go.mod"
    if go_mod.exists():
        with open(go_mod, "r") as f:
            content = f.read()
            # Extract module name from first line: module github.com/user/project
            match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
            if match:
                return match.group(1)
    return None

def detect_python_dependencies(project_dir):
    """Detect Python dependencies from setup.py or pyproject.toml"""
    deps = set()
    
    # Try setup.py first
    setup_py = project_dir / "setup.py"
    if setup_py.exists():
        with open(setup_py, "r") as f:
            content = f.read()
            # Find install_requires list
            match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if match:
                deps_str = match.group(1)
                # Extract package names (strip quotes and version specs)
                matches = re.findall(r'["\']([^"\'>=<\[]+)', deps_str)
                deps.update(matches)
    
    # Try pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        with open(pyproject, "r") as f:
            content = f.read()
            # Find dependencies in [project] section
            matches = re.findall(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            for match in matches:
                pkg_matches = re.findall(r'["\']([^"\'>=<\[]+)', match)
                deps.update(pkg_matches)
    
    return sorted(list(deps))

def main():
    parser = argparse.ArgumentParser(description="Add a project to a Yocto layer")
    parser.add_argument("project_path", help="Path to the project directory (or name if using --url)")
    parser.add_argument("--layer", default=None, help="Target layer name (default: auto-detect)")
    parser.add_argument("--recipe-dir", default="core", help="Recipe subdirectory (default: core)")
    parser.add_argument("--pv", default="1.0", help="Package version (default: 1.0)")
    parser.add_argument("--type", choices=["cpp", "cmake", "autotools", "makefile", "module", "rust", "go", "python", "auto"], 
                        default="auto", help="Project type (default: auto)")
    parser.add_argument("--library", action="store_true", help="Package is a library")
    parser.add_argument("--add-to-image", action="store_true", default=None, help="Add package to image IMAGE_INSTALL")
    parser.add_argument("--no-add-to-image", action="store_false", dest="add_to_image", help="Do not add package to image")
    parser.add_argument("--image", help="Target image name for integration")
    parser.add_argument("--url", help="Git URL to add as a submodule")
    args = parser.parse_args()

    UI.print_header("Add Project to Yocto")

    workspace_root = Path(__file__).resolve().parent.parent

    if args.url:
        UI.print_item("Git URL", args.url)
        project_name = args.project_path  # Treat first arg as name
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
        project_name = project_dir.name
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
        
    pn_override = ""
    if "_" in project_name:
        # Detect if BitBake might misinterpret the name (e.g. some_project_1.0 -> PN=some, PV=project_1.0)
        # We force PN to be the project name to matching directory name
        # We also MUST set PV to avoid recursion errors (PV -> BP -> PN -> PV)
        pn_override = f'PN = "{project_name}"\nPV = "{args.pv}"'
        
    depends_str = ""
    if detected_deps:
        depends_str = f'DEPENDS = "{" ".join(detected_deps)}"'

    # Recipe Content
    if project_type in ["cpp", "cmake", "autotools"]:
        recipe_content = f"""SUMMARY = "{project_name} application"
{license_text}
{pn_override}

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
