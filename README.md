# Yocto Workspace Automation

This repository provides a streamlined, automation-first workspace for developing and integrating local C++ software with the Yocto Project.

## Quick Start

To get your environment set up and perform your first build:

1.  **Initialize Environment**:
    ```bash
    source scripts/env_init.sh
    ```
2.  **Optimize Workspace**:
    ```bash
    optimize_workspace.py
    ```
3.  **Read the Docs**:
    - [Getting Started](docs/getting-started.md)
    - [Tooling Guide](docs/tooling-guide.md)

## Key Features

-   **Zero-Edit BitBake Config**: Automated management of `local.conf` and `bblayers.conf`.
-   **Local Source Integration**: Seamlessly build local projects from `sw/` using `externalsrc`.
-   **Integrated Toolchain**: One-click IDE sync for full IntelliSense and CMake support.
-   **Unified CLI**: Custom `yocto-*` commands for common development workflows.

## Project Structure

-   `sw/`: Local software source code.
-   `yocto/layers/`: Local Yocto layers (e.g., `meta-test`).
-   `scripts/`: Python automation suite and aliases.
-   `bitbake-builds/`: Yocto build environment and Poky source.
-   `docs/`: Comprehensive technical documentation.

## Documentation Index

-   [**Overview**](docs/overview.md): High-level architecture and concepts.
-   [**Tooling Guide**](docs/tooling-guide.md): Usage manual for the automation scripts.
-   [**Getting Started**](docs/getting-started.md): Installation and first-build steps.
-   [**Architecture**](docs/architecture.md): Technical details on the Yocto integration logic.
-   [**Script Development**](docs/scripts-development.md): Internal guide for extending the automation tools.

---
*For more information, see the [docs/](docs/) directory.*
