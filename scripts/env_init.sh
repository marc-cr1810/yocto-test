#!/bin/bash

# This script should be sourced: source scripts/env_init.sh

# Dynamically find workspace root (absolute path to the directory containing the scripts folder)
if [ -n "${BASH_SOURCE[0]}" ]; then
    # BASH_SOURCE is available - use it to find the script location
    SCRIPT_PATH="${BASH_SOURCE[0]}"
    # Convert to absolute path if relative
    if [[ "$SCRIPT_PATH" != /* ]]; then
        SCRIPT_PATH="$PWD/$SCRIPT_PATH"
    fi
    SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
    WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
else
    # Fallback: assume we're being sourced from workspace root or scripts dir
    if [ -d "scripts" ] && [ -f "scripts/env_init.sh" ]; then
        WORKSPACE_ROOT=$(pwd)
    elif [ -f "env_init.sh" ] && [ "$(basename $(pwd))" = "scripts" ]; then
        WORKSPACE_ROOT=$(cd .. && pwd)
    else
        echo "Error: Cannot determine workspace root. Please source from workspace root or scripts directory."
        return 1
    fi
fi
# Find BitBake/Yocto distribution directory dynamically
BITBAKE_YOCTO_DIR=$(find "${WORKSPACE_ROOT}/bitbake-builds" -maxdepth 1 \( -name "poky-*" -o -name "oe-*" \) -type d | head -n 1)
if [ -z "$BITBAKE_YOCTO_DIR" ]; then
    BITBAKE_YOCTO_DIR="${WORKSPACE_ROOT}/bitbake-builds/poky-master"
fi
BUILD_DIR="${BITBAKE_YOCTO_DIR}/build"

# 1. Source the standard Yocto environment
OE_INIT="${BITBAKE_YOCTO_DIR}/layers/openembedded-core/oe-init-build-env"
ORIG_PWD=$(pwd)
if [ -f "$OE_INIT" ]; then
    # We use the standard launcher
    source "$OE_INIT" "${BUILD_DIR}" > /dev/null
elif [ -f "${BITBAKE_YOCTO_DIR}/oe-init-build-env" ]; then
    source "${BITBAKE_YOCTO_DIR}/oe-init-build-env" "${BUILD_DIR}" > /dev/null
else
    echo "Warning: Standard Yocto init script not found. Skipping auto-source."
fi
cd "$ORIG_PWD"
unset ORIG_PWD

# 2. Add our scripts to PATH
export PATH="${WORKSPACE_ROOT}/scripts:${PATH}"

# 3. Custom Functions for our Tooling Suite (using functions instead of aliases for reliability)
yocto-layers() { layer_manager.py "$@"; }
yocto-machine() { machine_manager.py "$@"; }
yocto-sdk() { manage_sdk.py "$@"; }
yocto-new() { new_project.py "$@"; }
yocto-add() { add_package.py "$@"; }
yocto-build() { build_recipe.py "$@"; }
yocto-deploy() { deploy_recipe.py "$@"; }
yocto-image() { update_image.py "$@"; }
yocto-run() { run_qemu.py "$@"; }
yocto-check() { check_layer.py "$@"; }
yocto-deps() { view_deps.py "$@"; }
yocto-err() { last_error.py "$@"; }
yocto-clean() { safe_cleanup.py "$@"; }
yocto-live() { live_edit.py "$@"; }
yocto-ide() { setup_ide.py "$@"; }
yocto-sync() { sync_deps.py "$@"; }
yocto-health() { check_health.py "$@"; }
yocto-config() { config_manager.py "$@"; }
yocto-get() { yocto_get.py "$@"; }
yocto-search() { yocto_search.py "$@"; }
yocto-menu() { yocto_menu.py "$@"; }
yocto-query() { yocto_query.py "$@"; }
yocto-flash() { yocto_flash.py "$@"; }
yocto-distro() { yocto_distro.py "$@"; }
yocto-init() { yocto_init_manager.py "$@"; }

# Alias for familiarity with kernel workflow
alias makemenu="yocto-menu"
# Define colors
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "\n${BOLD}${CYAN}# Yocto Automation Environment Initialized${NC}"
echo -e "  Root: ${WORKSPACE_ROOT}"
echo -e "  Dist: ${BITBAKE_YOCTO_DIR}"
echo -e "  Menu: ${GREEN}yocto-menu${NC} (or ${GREEN}makemenu${NC}) : Interactive workspace manager"

echo -e "\n  ${BOLD}Projects:${NC}"
echo -e "    ${GREEN}yocto-new${NC} <name>    : Scaffold new project"
echo -e "    ${GREEN}yocto-add${NC} <name>    : Add package from git or local dir"
echo -e "    ${GREEN}yocto-sync${NC}          : Sync CMake deps with recipes"
echo -e "    ${GREEN}yocto-image${NC}         : Refresh image recipe"

echo -e "  ${BOLD}Build & Run:${NC}"
echo -e "    ${GREEN}yocto-build${NC} [name]  : Build recipe or image"
echo -e "    ${GREEN}yocto-deploy${NC} <name> : Build and deploy to target"
echo -e "    ${GREEN}yocto-run${NC}           : Build and boot in QEMU"
echo -e "    ${GREEN}yocto-sdk${NC}           : Manage toolchain SDKs"
echo -e "    ${GREEN}yocto-flash${NC}         : Burn image to SD card"
echo -e "    ${GREEN}yocto-live${NC} <name>   : Enable devtool edit mode"

echo -e "  ${BOLD}Analysis:${NC}"
echo -e "    ${GREEN}yocto-err${NC}           : Show latest build error"
echo -e "    ${GREEN}yocto-health${NC}        : Workspace health dashboard"
echo -e "    ${GREEN}yocto-search${NC} <term> : Search for recipes"
echo -e "    ${GREEN}yocto-get${NC} <name>    : Fetch and install recipe"
echo -e "    ${GREEN}yocto-query${NC} <VAR>   : Inspect Yocto variable"

echo -e "  ${BOLD}System:${NC}"
echo -e "    ${GREEN}yocto-machine${NC}       : Manage target machines"
echo -e "    ${GREEN}yocto-distro${NC}        : Manage distribution (poky, etc)"
echo -e "    ${GREEN}yocto-init${NC}          : Manage init system (systemd, etc)"
echo -e "    ${GREEN}yocto-layers${NC}        : Manage custom layers"
echo -e "    ${GREEN}yocto-ide${NC}           : Refresh IDE logic"

echo -e ""
