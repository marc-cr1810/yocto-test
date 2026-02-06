# Workspace Overview

This repository is a structured Yocto development workspace designed to automate the integration of local C++ software projects into a Yocto-based Linux image.

## Directory Structure

- **`sw/`**: Contains the source code for local software projects (C++, etc.). These are treated as `externalsrc` by Yocto.
- **`yocto/layers/`**: Houses local Yocto layers.
    - `meta-test`: The primary development layer for this workspace.
- **`scripts/`**: Automation tools and utility scripts for managing the build environment.
- **`bitbake-builds/`**: The Yocto build environment.
    - `poky-master`: The Poky (Yocto reference) source.
    - `shared/`: Shared `downloads` and `sstate-cache` to speed up builds across different project configurations.
- **`docs/`**: Documentation for the workspace and tools.

## Key Concepts

### Automation-First
The workspace is designed to minimize manual edits to BitBake configuration files. Tools like `yocto-layers` and `optimize_workspace.py` handle the configuration of `bblayers.conf` and `local.conf`.

### External Source Integration
Local projects in `sw/` are automatically mapped to Yocto recipes using the `externalsrc` class. This allows for rapid development cycles without needing to commit changes or update URIs in recipes.

### IDE Integration
The workspace includes tools to synchronize the Yocto toolchain and sysroots with VS Code, providing full IntelliSense and CMake support for local projects.
