#!/usr/bin/env python3
import os
import sys
import argparse
import re
import subprocess
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import yocto_utils

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

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Adding Project to Yocto Layer{NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    workspace_root = Path(__file__).resolve().parent.parent

    if args.url:
        print(f"  URL          : {args.url}")
        project_name = args.project_path  # Treat first arg as name
        submodules_dir = workspace_root / "submodules"
        submodules_dir.mkdir(exist_ok=True)
        project_dir = submodules_dir / project_name
        
        if project_dir.exists():
            print(f"  {BOLD}Status       : Submodule directory {project_dir} already exists.{NC}")
        else:
            print(f"  Status       : Adding git submodule '{project_name}'...")
            if not (workspace_root / ".git").exists():
                print(f"  Error: Workspace is not a git repository. Cannot use submodules.")
                sys.exit(1)
            try:
                subprocess.run(["git", "submodule", "add", args.url, str(project_dir)], cwd=workspace_root, check=True)
                print(f"  {GREEN}Success! Submodule added.{NC}")
            except subprocess.CalledProcessError as e:
                print(f"  Error adding submodule: {e}")
                sys.exit(1)
    else:
        project_dir = Path(args.project_path).resolve()
        project_name = project_dir.name
        if not project_dir.exists():
            print(f"Error: Project directory {project_dir} does not exist.")
            sys.exit(1)

    # Auto-detect layer if not specified
    layer_name = args.layer
    if layer_name is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from yocto_utils import get_all_custom_layers, get_cached_layer
        
        cached_layer = get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            print(f"{BOLD}{RED}Error: No custom layers found.{NC}")
            print(f"  Run '{GREEN}yocto-layers --new <name>{NC}' to create a layer first.")
            sys.exit(1)
        
        if len(all_layers) == 1:
            # Single layer - auto-select
            layer_name = all_layers[0].name.replace('meta-', '')
            print(f"  Auto-detected layer: {BOLD}meta-{layer_name}{NC}")
        elif cached_layer:
            # Use cached layer
            layer_name = cached_layer.replace('meta-', '')
            print(f"  Using last-used layer: {BOLD}meta-{layer_name}{NC}")
        else:
            # Multiple layers, use first one
            layer_name = all_layers[0].name.replace('meta-', '')
            print(f"  Using layer: {BOLD}meta-{layer_name}{NC}")
    
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
            # Default to cpp if unsure for this context, or warn
            print(f"  {BOLD}Warning:{NC} Could not auto-detect project type. Defaulting to 'cpp'.")
            project_type = "cpp"
    
    print(f"  Project Type : {project_type}")
    
    # Define paths
    workspace_root = Path(__file__).resolve().parent.parent
    layer_dir = workspace_root / "yocto" / "layers" / layer_name
    recipe_dir = layer_dir / recipe_subdir / project_name
    recipe_file = recipe_dir / f"{project_name}_{args.pv}.bb"

    # Create directories
    recipe_dir.mkdir(parents=True, exist_ok=True)

    # Calculate relative path from recipe directory to project directory
    # Use os.path.relpath to get a reliable relative path
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
            print(f"  Go Module    : {go_module_path}")
    elif project_type == "python":
        detected_deps = detect_python_dependencies(project_dir)
    
    if detected_deps:
        print(f"  Dependencies : {', '.join(detected_deps)}")
    
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
        # Ideally we'd calculate checksum, but for local dev "CLOSED" or "MIT" is common placeholder
        license_text = 'LICENSE = "MIT"\nLIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"'
        
    depends_str = ""
    if detected_deps:
        depends_str = f'DEPENDS = "{" ".join(detected_deps)}"'

    # Points to local source
    src_uri = f'SRC_URI = "file://${{THISDIR}}/{rel_project_path};subdir=${{BP}}"'
    
    # Recipe Content
    recipe_content = f"""SUMMARY = "{project_name} application"
{license_text}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"
EXTERNALSRC_BUILD = "${{WORKDIR}}/build"

{depends_str}
"""
    
    # Module specific adjustment
    if project_type == "module":
        recipe_content = f"""SUMMARY = "{project_name} kernel module"
{license_text}

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

    # Rust specific recipe
    elif project_type == "rust":
        recipe_content = f"""SUMMARY = "{project_name} Rust application"
{license_text}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"
EXTERNALSRC_BUILD = "${{WORKDIR}}/build"

{depends_str}
"""

    # Go specific recipe
    elif project_type == "go":
        go_import = go_module_path if go_module_path else project_name
        recipe_content = f"""SUMMARY = "{project_name} Go application"
{license_text}

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

    # Python specific recipe
    elif project_type == "python":
        recipe_content = f"""SUMMARY = "{project_name} Python application"
{license_text}

{inherit_class}

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${{THISDIR}}/{rel_project_path}"

{depends_str}
"""


    with open(recipe_file, "w") as f:
        f.write(recipe_content)

    print(f"\n{GREEN}Success! Created {project_type} recipe for '{project_name}'{NC}")
    print(f"  Path         : {recipe_file}")

    # Image Integration
    # Default add_to_image to True if not a library and not explicitly set
    add_to_image = args.add_to_image
    if add_to_image is None:
        add_to_image = not args.library

    image_name = None  # Initialize to avoid UnboundLocalError
    if add_to_image:
        image_name = args.image
        if not image_name:
            image_name = yocto_utils.get_cached_image(workspace_root)
        
        if not image_name:
            # Try to find custom images
            layer_path = yocto_utils.find_custom_layer(workspace_root)
            images = yocto_utils.find_image_recipes(layer_path)
            if images:
                image_name = images[0] # Default to first found
                print(f"  Auto-selected image: {BOLD}{image_name}{NC}")
        
        if image_name:
            print(f"  Integrating with image: {BOLD}{image_name}{NC}...")
            if yocto_utils.add_package_to_image(workspace_root, image_name, project_name):
                print(f"  {GREEN}Successfully added '{project_name}' to {image_name}{NC}")
                yocto_utils.set_cached_image(workspace_root, image_name)
            else:
                print(f"  {RED}Failed to add '{project_name}' to {image_name}{NC}")
    else:
        print(f"  Skipping image integration (package is a library or explicitly disabled)")

    print(f"\n{BOLD}Action Required:{NC}")
    print(f"  Run '{GREEN}bitbake {project_name}{NC}' to build recipe.")
    print(f"  Run '{GREEN}bitbake {image_name or 'core-image-falcon'}{NC}' to build image.")
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
