# Getting Started

Follow these steps to set up the workspace and perform your first build.

## Prerequisites

- A Linux host with Yocto Project dependencies installed.
- VS Code (recommended).

## 1. Initialize the Environment

Run the initialization script to set up your shell environment and aliases:
```bash
source scripts/env_init.sh
```

## 2. Optimize the Workspace

Run the optimization tool to configure your build for the host system:
```bash
optimize_workspace.py
```
This will set your thread counts and shared cache paths in `bitbake-builds/poky-master/build/conf/local.conf`.

## 3. Register Layers

Ensure your local layers are registered with BitBake:
```bash
yocto-layers
```

## 4. Create a New Project

Scaffold a test project:
```bash
yocto-new hello-world
```

## 5. Update the Image

Add your new project to the image package list:
```bash
yocto-image
```

## 6. Build and Run

Start the full build and run it in QEMU:
```bash
yocto-run
```

## 7. IDE Setup (Optional)

If using VS Code, run the IDE setup tool to enable IntelliSense:
```bash
yocto-ide
```
Then select the "Yocto Toolchain" kit in the CMake extension.
