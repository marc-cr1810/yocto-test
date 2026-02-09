#!/usr/bin/env python3
import os
import sys
import re
from pathlib import Path

# Add scripts directory to path to import yocto_utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from yocto_utils import UI, find_custom_layer, get_all_custom_layers, get_cached_layer

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
                            deps.add(m.lower())
    return sorted(list(filter(None, deps)))

def update_recipe(recipe_file, new_deps):
    if not recipe_file.exists():
        return False
    
    with open(recipe_file, "r") as f:
        lines = f.readlines()
    
    new_deps_str = f'DEPENDS = "{" ".join(new_deps)}"\n'
    updated = False
    new_lines = []
    depends_found = False
    
    for line in lines:
        if line.startswith("DEPENDS ="):
            if not updated and new_deps:
                new_deps_str_old = line
                if new_deps_str != new_deps_str_old:
                    new_lines.append(new_deps_str)
                    updated = True
                else:
                    new_lines.append(line)
            depends_found = True
        else:
            new_lines.append(line)
            
    # If no DEPENDS was found but we have deps to add
    if not depends_found and new_deps:
        # Find a good place to insert (after LICENSE)
        insert_idx = -1
        for i, line in enumerate(new_lines):
            if line.startswith("LICENSE ="):
                insert_idx = i + 1
                break
        
        if insert_idx != -1:
            new_lines.insert(insert_idx, "\n" + new_deps_str)
            updated = True
        else:
            new_lines.insert(0, new_deps_str + "\n")
            updated = True

    if updated:
        with open(recipe_file, "w") as f:
            f.writelines(new_lines)
        return True
    return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Synchronize CMake dependencies with Yocto recipes")
    parser.add_argument("--layer", default=None, help="Layer name to use (default: auto-detect)")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    sw_dir = workspace_root / "sw"
    
    # Smart layer detection
    if args.layer:
        layer_dir = find_custom_layer(workspace_root, args.layer)
    else:
        cached_layer = get_cached_layer(workspace_root)
        all_layers = get_all_custom_layers(workspace_root)
        
        if not all_layers:
            UI.print_error("No custom layers found.")
            print(f"  Run '{UI.GREEN}yocto-layers --new <name>{UI.NC}' to create a layer first.")
            sys.exit(1)
        
        if len(all_layers) == 1:
            # Single layer - auto-select
            layer_dir = all_layers[0]
        elif cached_layer:
            # Use cached layer
            layer_dir = workspace_root / "yocto" / "layers" / cached_layer
        else:
            # Multiple layers, use first one
            layer_dir = all_layers[0]
    
    UI.print_header("Synchronizing Workspace Dependencies")
    UI.print_item("Layer", layer_dir.name)
    
    updated_count = 0
    # Recursively scan all subdirectories in sw/ including language-specific folders
    for project_dir in sw_dir.rglob("CMakeLists.txt"):
        project_dir = project_dir.parent
        # Get the project name relative to sw/ to handle nested structures
        rel_path = project_dir.relative_to(sw_dir)
        project_name = rel_path.name if len(rel_path.parts) == 1 else rel_path.parts[-1]
        
        # Find the recipe
        recipe_file = None
        for r in layer_dir.rglob(f"{project_name}_*.bb"):
            recipe_file = r
            break
        
        if not recipe_file:
            continue
            
        detected_deps = detect_dependencies(project_dir, workspace_root, layer_dir)
        if update_recipe(recipe_file, detected_deps):
            print(f"  {UI.GREEN}[UPDATED]{UI.NC} {project_name:15} -> {', '.join(detected_deps)}")
            updated_count += 1
        else:
            print(f"  [ OK ]    {project_name:15}")
                
    print(f"\n{UI.GREEN}Done. Updated {updated_count} recipes.{UI.NC}")

if __name__ == "__main__":
    main()
