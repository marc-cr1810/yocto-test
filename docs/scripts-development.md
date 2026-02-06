# Script Development & Internals

This document provides technical details for developers maintaining or extending the workspace automation scripts located in the `scripts/` directory.

## Core Design Patterns

Most scripts in this workspace follow a consistent implementation pattern to ensure portability and reliability.

### 1. Finding Workspace Root
Scripts should not rely on the current working directory. Instead, they should determine the workspace root relative to their own location:
```python
from pathlib import Path
workspace_root = Path(__file__).resolve().parent.parent
```

### 2. Subprocess Management
Interactions with BitBake and other shell tools should be handled via `subprocess.run`. Use `check=True` to ensure failures are caught early:
```python
import subprocess
result = subprocess.run(["bitbake", "recipe-name"], check=True, capture_output=True, text=True)
```

### 3. BitBake Environment Integration
The `env_init.sh` script is the gatekeeper for the build environment. It:
1. Sources the standard Yocto `init-build-env`.
2. Exports the `scripts/` directory to the `PATH`.
3. Defines aliases for common Python scripts to provide a unified `yocto-*` CLI.

## Script Deep Dives

### `manage_layers.py` (`yocto-layers`)
- **Role**: Synchronizes `bblayers.conf`.
- **Logic**: Scans `yocto/layers/` for `meta-*` directories and uses `bitbake-layers add-layer` to register them.
- **Dependency**: Requires the BitBake environment to be sourced (checked via the presence of `BBPATH`).

### `optimize_workspace.py`
- **Role**: Tunes `local.conf` for the host system.
- **Logic**: Uses `multiprocessing.cpu_count()` to determine optimal thread counts. It parses `local.conf` and injects/updates `DL_DIR`, `SSTATE_DIR`, `BB_NUMBER_THREADS`, and `PARALLEL_MAKE`.

### `setup_ide.py` (`yocto-ide`)
- **Role**: Links Yocto's cross-tools with VS Code.
- **Logic**: Scans `tmp/sysroots-components` to find the GCC cross-compiler and a representative target sysroot. It then generates or updates `.vscode/cmake-kits.json`.

## Extending the Tooling

### Adding a New Tool
1. Create a new Python script in `scripts/`.
2. Ensure it is executable (`chmod +x`).
3. Add a corresponding alias in `scripts/env_init.sh`.
4. Update `docs/tooling-guide.md` with usage instructions.

## Maintenance & Troubleshooting

- **Environment Mismatch**: If scripts fail with "BitBake not found", ensure `env_init.sh` was sourced in the current shell.
- **Path Issues**: The scripts use relative paths from the script location. If you move the scripts, you must update the `workspace_root` logic.

## Recent Enhancements

### Git Submodule Support
`add_package.py` now supports adding external repositories as git submodules via the `--url` argument. When used, the script:
1. Clones the repository to `submodules/<name>`
2. Auto-detects the project type
3. Creates a recipe with `inherit externalsrc` pointing to the submodule

### Multi-Image Support
`update_image.py` accepts an `--image` argument to manage multiple image recipes. If the specified image doesn't exist, it will be scaffolded automatically.

### Kernel Module Support
Both `new_cpp_project.py` and `add_package.py` support Linux kernel modules via `--type module`, generating appropriate `.c` files, Makefiles, and recipes with `inherit module`.
