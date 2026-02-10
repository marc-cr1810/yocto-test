# Tooling Guide

The workspace provides a suite of tools (aliased to `yocto-*`) to simplify Yocto development tasks.

## Environment Initialization

To enable these tools, you must source the environment script from the root of the workspace:
```bash
source scripts/env_init.sh
```

## Primary Tools

### `yocto-menu` (or `makemenu`)
A text-based menu interface for managing the entire workspace. Provides a centralized way to access all other tools.
- **Usage**: `yocto-menu` or `makemenu`
- **Navigation**: Arrow keys to move, Enter to select, Esc to go back.

### `yocto-new <name>`
Scaffolds a new project from scratch in `sw/<name>` and automatically creates a corresponding Yocto recipe.

**Examples:**
```bash
# Create C++/CMake project
yocto-new my-app --type cmake --layer falcon

# Create kernel module
yocto-new my-driver --type module --layer falcon
```

**Options:**
- `--type <type>`: Project type (`cmake` or `module`, default: `cmake`)
- `--layer <name>`: Target layer (default: auto-detect)
- `--recipe-dir <dir>`: Recipe subdirectory (default: `sw`)

> **Auto-Detection**: Automatically selects the layer if only one exists, or uses the last-used layer.

### `yocto-add <name>`
Adds an existing project to a Yocto layer by creating a recipe. Supports both local directories and git repositories (added as submodules).

**From Git Repository:**
```bash
# Add as submodule (auto-detect type and layer)
yocto-add my-library --url https://github.com/user/my-library.git

# Specify project type
yocto-add rtl8812au --url https://github.com/aircrack-ng/rtl8812au.git --type module
```

**From Local Directory:**
```bash
# Add existing local project
yocto-add /path/to/my-project
```

**Options:**
- `--url <git-url>`: Add from git repository as submodule (stored in `submodules/`)
- `--type <type>`: Project type (`cmake`, `module`, `autotools`, `makefile`, or `auto`)
- `--layer <name>`: Target layer (default: auto-detect)
- `--recipe-dir <dir>`: Recipe subdirectory (default: `sw`)
- `--pv <version>`: Package version (default: `1.0`)

> **Auto-Detection**: Automatically selects the layer and detects project type from build files.

### `yocto-image`
Scans the workspace for all local projects and updates the image recipe to include them.
### `yocto-image`
Refresh the image recipe or manage its packages.
- **Refresh**: `yocto-image refresh` (or just `yocto-image`) - Updates image with workspace projects.
- **List**: `yocto-image list` - Lists currently installed packages.
- **Available**: `yocto-image available [filter]` - Lists all available recipes in active layers.
- **Create**: `yocto-image create [name]` - Creates a new image recipe (auto-detects layer).
- **Add**: `yocto-image add <package>` - Adds a package to the image (persists).
- **Remove**: `yocto-image remove <package>` - Removes a package from the image.
- **Options**:
  - `--interactive`: Force interactive selection
  - `--layer <name>`: Target specific layer


### `yocto-build [name]`
Builds a Yocto recipe or image. Auto-detects the most recent image when no target is specified.

**Examples:**
```bash
# Auto-detect and build most recent image
yocto-build

# Build specific recipe or image
yocto-build example
yocto-build core-image-falcon

# Clean before building
yocto-build --clean
yocto-build example --cleansstate
```

**Options:**
- `--clean`: Clean before building
- `--cleansstate`: Clean shared state before building

> **Auto-Detection**: Uses last-built image or the only available image recipe when no target specified.

### `yocto-deploy <name>`
Builds and deploys a recipe's artifacts to a local directory or remote target via SSH.

**Local Deployment:**
```bash
# Deploy to default location (./deploy/<recipe>)
yocto-deploy example

# Deploy to custom directory
yocto-deploy example --dest /path/to/rootfs
```

**Remote Deployment:**
```bash
# Deploy to remote target (defaults to root filesystem)
yocto-deploy example --remote root@192.168.7.2

# Deploy to specific remote path
yocto-deploy example --remote root@192.168.7.2:/opt/app

# With SSH options
yocto-deploy example --remote user@target --ssh-opts "-p 2222 -i ~/.ssh/key.pem"

# Skip build, just deploy
yocto-deploy example --remote root@target --no-build
```

**Options:**
- `--dest <path>`: Local destination directory
- `--remote <target>`: Remote target (user@host or user@host:/path)
- `--ssh-opts <opts>`: Additional SSH options
- `--clean`: Clean before building
- `--no-build`: Skip build, deploy existing artifacts

> **Smart Features**: Automatically uses `rsync` for efficiency, falls back to `tar+ssh` when rsync unavailable. Shows actual installation paths when deploying remotely.

### `yocto-run`
Builds and boots an image using QEMU with smart auto-detection.
- **Auto-detect**: `yocto-run` (auto-selects image if only one is built)
- **Explicit Image**: `yocto-run core-image-falcon`
- **Skip Build**: `yocto-run --no-build` (launch existing image)
- **Interactive Selection**: `yocto-run --interactive` (force menu even with one image)
- **Ignore Cache**: `yocto-run --no-cache` (don't use last-used image)

> **Smart Features**: Auto-detects built images, shows interactive menu for multiple images with build times, checks image freshness to avoid unnecessary rebuilds, and remembers your last-used image.

### `yocto-machine`
Manages the target hardware configuration in `local.conf`.
- **List**: `yocto-machine list`
- **Switch**: `yocto-machine switch <name>` (or just `yocto-machine <name>`)
- **Search**: `yocto-machine search <term>` (searches Layer Index)
- **Get**: `yocto-machine get <name> [--branch <branch>]` (fetches and installs machine layer)
- **Scaffold**: `yocto-machine new <name>`

### `yocto-config`
Manages configuration fragments in `toolcfg.conf` (e.g. `machine/qemuarm64`).
- **List**: `yocto-config list`
- **Enable**: `yocto-config enable <fragment>`
- **Disable**: `yocto-config disable <fragment>`

### `yocto-init`
Manages the system init manager configuration (e.g. `systemd`, `sysvinit`).
- **List**: `yocto-init list`
- **Set**: `yocto-init set <name>`
- **Show**: `yocto-init show`


### `yocto-layers`
Synchronizes the BitBake configuration with the local layers or scaffolds new layers.
- **Sync All**: `yocto-layers` (default: sync all layers)
- **Scaffold**: `yocto-layers --new meta-custom`
- **Layer Info**: `yocto-layers --info [layer]` (auto-detect if not specified)
- **List Recipes**: `yocto-layers --recipes [layer]` (auto-detect if not specified)
- **Interactive**: `yocto-layers --info --interactive` (force layer selection)
- **Ignore Cache**: `yocto-layers --info --no-cache` (don't use last-used layer)

> **Smart Features**: New `--info` and `--recipes` commands with auto-detection, interactive selection for multiple layers, and caching of last-used layer.

### `yocto-sdk`
Automates the generation and management of the cross-development SDK (Toolchain).
- **Auto-detect & Build**: `yocto-sdk --build` (auto-selects image)
- **Explicit Image**: `yocto-sdk core-image-falcon --build`
- **List SDKs**: `yocto-sdk --list`
- **Interactive Selection**: `yocto-sdk --build --interactive` (force menu)
- **Ignore Cache**: `yocto-sdk --build --no-cache` (don't use last-used image)

> **Smart Features**: Auto-detects built images, remembers your last-used image, and shows interactive menu for multiple images.

### `yocto-ide`
Probes the build directory for the cross-compiler and target sysroot, then updates `.vscode/cmake-kits.json`.
- **Usage**: `yocto-ide`

### `yocto-sync`
Automatically synchronizes `CMakeLists.txt` dependencies with the corresponding Yocto recipe's `DEPENDS` list.

**Examples:**
```bash
# Auto-detect layer and sync all recipes
yocto-sync

# Sync recipes in specific layer
yocto-sync --layer falcon
```

**Options:**
- `--layer <name>`: Target layer (default: auto-detect)

> **Smart Features**: Automatically converts CMake `find_package()` calls to Yocto recipe dependencies. No hardcoded mappings needed - most packages work automatically (e.g., `spdlog` → `spdlog`).

### `yocto-health`
Provides a health dashboard of the workspace, including disk space, sstate cache status, and environment health.
- **Usage**: `yocto-health`

### `yocto-live <name>`
Enables `devtool modify` for a specific recipe, allowing for live editing and testing within the Yocto environment.
- **Usage**: `yocto-live example`

## Utility Scripts

- **`yocto-query <VAR>`**: Inspect the value of a Yocto variable (e.g., `WORKDIR`, `IMAGE_INSTALL`).
- **`yocto-flash <image>`**: Safely burn a Yocto image to an SD card or USB drive.
- **`yocto-distro {list|set|show}`**: Manage the Yocto Distribution (`DISTRO`).
- **`yocto-deps <name>`**: Visualizes the dependency tree for a given project.
- **`yocto-err`**: Displays the log of the last failed BitBake task.
- **`yocto-clean`**: Performs a safe cleanup of build artifacts.
- **`yocto-check`**: Runs sanity checks on the local layers.

## Smart Image Detection System

The workspace includes an intelligent image detection system that makes working with images faster and more intuitive.

### How It Works

When you run `yocto-run`, `yocto-sdk --build`, or `yocto-image` without specifying an image:

1. **Single Image/Recipe**: Automatically selects it silently
2. **Multiple Images/Recipes**: Shows an interactive menu with metadata
3. **No Images**: Falls back to recipe discovery or prompts to create new recipe

### Smart Layer Detection

The same smart detection applies to layers in `yocto-image` and `yocto-layers`:

**Layer Selection:**
- Single layer → auto-selects silently
- Multiple layers → interactive menu with recipe counts
- Cached layer highlighted with `[last used]`

**New Layer Commands:**
```bash
# Show layer info (auto-detect)
yocto-layers --info

# List recipes in layer (auto-detect)
yocto-layers --recipes

# Force interactive selection
yocto-layers --info --interactive
```

### Interactive Selection

When multiple images are available, you'll see:
```
Multiple images found:
  1. core-image-falcon     (built: 2 hours ago) [last used]
  2. test-image            (built: 1 day ago)
  3. core-image-minimal    (built: 3 days ago)

Select image [1-3] or Enter for #1:
```

When multiple layers are available:
```
Multiple custom layers found:
  1. meta-test        (12 recipes) [last used]
  2. meta-custom      (5 recipes)
  3. meta-drivers     (3 recipes)

Select layer [1-3] or Enter for #1:
```

### Cache System

The system remembers your last-used image and layer in `.yocto-cache/`:
- `last-image` - Last-used image name
- `last-layer` - Last-used layer name
- Highlighted in interactive menus with `[last used]`
- Used as default selection
- Updated after successful operations
- Can be bypassed with `--no-cache` flag

### Freshness Check

`yocto-run` checks if an image was built recently (within 2 hours) and prompts before rebuilding:
```
Image built recently. Rebuild? [y/N]:
```

### Common Flags

All image-related tools support:
- `--interactive`: Force interactive selection even with one image
- `--no-cache`: Ignore cached image preference

Layer-specific tools also support:
- `--layer-interactive`: Force interactive layer selection
- `--layer-no-cache`: Ignore cached layer preference

## Kernel Module Development

The workspace provides streamlined support for developing Linux kernel modules with proper build isolation.

### Creating a Kernel Module

```bash
# Create new module
yocto-new my-driver --type module --layer falcon

# Add existing module from git
yocto-add spdlog --url https://github.com/gabime/spdlog.git --type cmake --library
```

### Managing Auto-Load
To ensure your kernel module loads automatically on boot, use `yocto-service`:
```bash
yocto-service enable gps-sim
```
This adds `KERNEL_MODULE_AUTOLOAD` to the recipe. You can check status with `yocto-service status gps-sim`.

### Build Configuration

Kernel modules use a special build configuration to keep source directories clean:

- **Source Directory**: `sw/<module-name>/` or `submodules/<module-name>/` (stays clean)
- **Build Directory**: `${WORKDIR}/build` (in Yocto's work directory)
- **Build Artifacts**: All `.o`, `.ko`, `.mod.c` files stay in the build directory

The recipe automatically creates symlinks from the build directory to source files, allowing kbuild to find everything while keeping your source tree pristine.

### Key Differences from CMake Projects

- Kernel modules build in a separate directory with symlinks to source
- No separate build directory in the source tree
- Build artifacts are contained in Yocto's work directory
- Uses the `module` bbclass instead of `cmake`

## Configuration Automation

- **`optimize_workspace.py`**: Automatically tunes `local.conf` based on the host system's CPU cores and sets up shared download/sstate directories.

