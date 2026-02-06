#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new project (C++, Rust, Go, Python, or Kernel Module) and add it to Yocto")
    parser.add_argument("name", help="Name of the new project")
    parser.add_argument("--layer", default=None, help="Target Yocto layer (default: auto-detect)")
    parser.add_argument("--recipe-dir", default="core", help="Recipe subdirectory (default: core)")
    parser.add_argument("--type", choices=["cpp", "cmake", "module", "rust", "go", "python"], default="cpp", help="Project type (default: cpp)")
    parser.add_argument("--library", action="store_true", help="Create a library instead of an executable")
    args = parser.parse_args()

    # ANSI Colors
    BOLD = '\033[1m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    NC = '\033[0m'

    print(f"{BOLD}{CYAN}=================================================={NC}")
    print(f"{BOLD}{CYAN}   Scaffolding New Project ({args.type}){NC}")
    print(f"{BOLD}{CYAN}=================================================={NC}")

    workspace_root = Path(__file__).resolve().parent.parent
    
    # Map project type to directory
    type_to_dir = {
        "cpp": "cpp",
        "cmake": "cpp",
        "module": "module",
        "rust": "rust",
        "go": "go",
        "python": "python"
    }
    
    lang_dir = type_to_dir.get(args.type, "cpp")
    sw_dir = workspace_root / "sw" / lang_dir / args.name
    project_name = args.name

    if sw_dir.exists():
        print(f"Error: Project directory {sw_dir} already exists.")
        sys.exit(1)

    # Auto-detect layer if not specified
    layer_name = args.layer
    if layer_name is None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from yocto_utils import get_all_custom_layers, get_cached_layer, select_layer_interactive
        
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

    print(f"  Project Name : {BOLD}{project_name}{NC}")
    print(f"  Target Layer : {BOLD}meta-{layer_name if not layer_name.startswith('meta-') else layer_name}{NC}")
    print(f"  Type         : {BOLD}{args.type}{NC}")
    
    sw_dir.mkdir(parents=True)

    if args.type in ["cpp", "cmake"]:
        if args.library:
            # Create library header
            header_file = sw_dir / f"{project_name}.h"
            with open(header_file, "w") as f:
                f.write(f"""#ifndef {project_name.upper()}_H
#define {project_name.upper()}_H

namespace {project_name} {{
    void hello();
}}

#endif // {project_name.upper()}_H
""")
            
            # Create library source
            source_file = sw_dir / f"{project_name}.cpp"
            with open(source_file, "w") as f:
                f.write(f"""#include "{project_name}.h"
#include <iostream>

namespace {project_name} {{
    void hello() {{
        std::cout << "Hello from {project_name} library!" << std::endl;
    }}
}}
""")
            
            # Create CMakeLists.txt for library
            cmake_lists = sw_dir / "CMakeLists.txt"
            with open(cmake_lists, "w") as f:
                f.write(f"""cmake_minimum_required(VERSION 3.10)
project({project_name} VERSION 1.0)

add_library({project_name} SHARED {project_name}.cpp)

install(TARGETS {project_name} DESTINATION lib)
install(FILES {project_name}.h DESTINATION include)
""")
        else:
            # Create executable (original code)
            main_cpp = sw_dir / "main.cpp"
            with open(main_cpp, "w") as f:
                f.write(f"""#include <iostream>

int main() {{
    std::cout << "Hello from {project_name}!" << std::endl;
    return 0;
}}
""")

            # Create CMakeLists.txt for executable
            cmake_lists = sw_dir / "CMakeLists.txt"
            with open(cmake_lists, "w") as f:
                f.write(f"""cmake_minimum_required(VERSION 3.10)
project({project_name} VERSION 1.0)

add_executable({project_name} main.cpp)

install(TARGETS {project_name} DESTINATION bin)
""")

    elif args.type == "module":
        # Create hello.c (kernel module)
        hello_c = sw_dir / f"{project_name}.c"
        with open(hello_c, "w") as f:
            f.write(f"""#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yocto Workspace");
MODULE_DESCRIPTION("A simple {project_name} kernel module");

static int __init {project_name}_init(void)
{{
    printk(KERN_INFO "Hello from {project_name} module!\\n");
    return 0;
}}

static void __exit {project_name}_cleanup(void)
{{
    printk(KERN_INFO "Goodbye from {project_name} module!\\n");
}}

module_init({project_name}_init);
module_exit({project_name}_cleanup);
""")

        # Create Makefile
        makefile = sw_dir / "Makefile"
        with open(makefile, "w") as f:
            f.write(f"""obj-m += {project_name}.o

SRC := $(shell pwd)

all:
	$(MAKE) -C $(KERNEL_SRC) M=$(SRC) modules

modules_install:
	$(MAKE) -C $(KERNEL_SRC) M=$(SRC) modules_install

clean:
	rm -f *.o *~ core .depend .*.cmd *.ko *.mod.c
	rm -f Module.markers Module.symvers modules.order
	rm -rf .tmp_versions Modules.symvers
""")

    elif args.type == "rust":
        # Create Cargo.toml
        cargo_toml = sw_dir / "Cargo.toml"
        with open(cargo_toml, "w") as f:
            if args.library:
                f.write(f"""[package]
name = "{project_name}"
version = "1.0.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
""")
            else:
                f.write(f"""[package]
name = "{project_name}"
version = "1.0.0"
edition = "2021"

[dependencies]
""")

        # Create src directory
        src_dir = sw_dir / "src"
        src_dir.mkdir(parents=True)
        
        if args.library:
            # Create lib.rs for library
            lib_rs = src_dir / "lib.rs"
            with open(lib_rs, "w") as f:
                f.write(f"""pub fn hello() {{
    println!("Hello from {project_name} library!");
}}

#[cfg(test)]
mod tests {{
    use super::*;

    #[test]
    fn it_works() {{
        hello();
    }}
}}
""")
        else:
            # Create main.rs for binary
            main_rs = src_dir / "main.rs"
            with open(main_rs, "w") as f:
                f.write(f"""fn main() {{
    println!("Hello from {project_name}!");
}}
""")

    elif args.type == "go":
        # Create go.mod
        go_mod = sw_dir / "go.mod"
        with open(go_mod, "w") as f:
            f.write(f"""module {project_name}

go 1.21
""")

        if args.library:
            # Create library package file
            lib_go = sw_dir / f"{project_name}.go"
            with open(lib_go, "w") as f:
                f.write(f"""package {project_name}

import "fmt"

// Hello prints a greeting message
func Hello() {{
    fmt.Println("Hello from {project_name} library!")
}}
""")
        else:
            # Create main.go for executable
            main_go = sw_dir / "main.go"
            with open(main_go, "w") as f:
                f.write(f"""package main

import "fmt"

func main() {{
    fmt.Println("Hello from {project_name}!")
}}
""")

    elif args.type == "python":
        # Create setup.py
        setup_py = sw_dir / "setup.py"
        with open(setup_py, "w") as f:
            if args.library:
                # Library - no console scripts
                f.write(f"""from setuptools import setup, find_packages

setup(
    name="{project_name}",
    version="1.0.0",
    packages=find_packages(),
)
""")
            else:
                # Executable - with console scripts
                f.write(f"""from setuptools import setup, find_packages

setup(
    name="{project_name}",
    version="1.0.0",
    packages=find_packages(),
    entry_points={{
        'console_scripts': [
            '{project_name}={project_name}.main:main',
        ],
    }},
)
""")

        # Create package directory
        pkg_dir = sw_dir / project_name
        pkg_dir.mkdir(parents=True)
        
        # Create __init__.py
        init_py = pkg_dir / "__init__.py"
        with open(init_py, "w") as f:
            if args.library:
                f.write(f"""\"\"\"
{project_name} library
\"\"\"

def hello():
    print("Hello from {project_name} library!")
""")
            else:
                f.write("")
        
        if not args.library:
            # Create main.py for executable
            main_py = pkg_dir / "main.py"
            with open(main_py, "w") as f:
                f.write(f"""def main():
    print("Hello from {project_name}!")

if __name__ == "__main__":
    main()
""")


    print(f"  Status       : Created files in {sw_dir}")

    # Call add_package.py
    add_pkg_script = workspace_root / "scripts" / "add_package.py"
    
    try:
        cmd = [sys.executable, str(add_pkg_script), str(sw_dir), "--layer", layer_name, "--recipe-dir", args.recipe_dir, "--type", args.type]
        if args.library:
            cmd.append("--library")
        subprocess.run(cmd, check=True)
        print(f"\n{GREEN}Success! Project '{project_name}' is scaffolded and added to Yocto.{NC}")
    except subprocess.CalledProcessError:
        # add_package.py prints its own errors
        sys.exit(1)
    
    print(f"{BOLD}{CYAN}=================================================={NC}")

if __name__ == "__main__":
    main()
