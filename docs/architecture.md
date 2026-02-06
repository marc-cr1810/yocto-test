# Architecture & Integration

This document describes how the workspace integrates local software with the Yocto build system.

## External Source (`externalsrc`)

The workspace uses the `externalsrc` BitBake class to bridge the gap between `sw/` and the Yocto recipes.

### How it works
When you create a project using `yocto-new`, it generates a recipe with the following logic:
```bitbake
inherit cmake externalsrc
EXTERNALSRC = "${TOPDIR}/../../../sw/my-project"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
```

- **`EXTERNALSRC`**: Points BitBake to the local directory in the workspace root instead of downloading from a URI.
- **`EXTERNALSRC_BUILD`**: Directs build artifacts to the Yocto `WORKDIR` instead of polluting the source directory.

### Benefits
- **Zero-Commit Workflow**: You can build and test changes instantly without needing to commit them.
- **Source-Centric**: The source code remains in `sw/`, where it can be easily managed by Git and edited in your IDE.

## Layer Structure

### `meta-test`
This is a custom layer located in `yocto/layers/meta-test`. It is designed to house the recipes for all local projects.

- **`recipes-sw/`**: Contains the recipes generated for your projects in `sw/`.
- **`recipes-images/`**: Contains the `test-image.bb` recipe, which serves as the root for your custom Linux distribution.

## Build Directory Layout

The workspace keeps the build environment separate from the source code to maintain cleanliness:
- `bitbake-builds/poky-master/build`: This is the standard Yocto `TOPDIR`. All BitBake commands are executed from here (managed by the `scripts/` suite).
