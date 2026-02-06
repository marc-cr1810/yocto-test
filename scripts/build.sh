#!/bin/bash

# ANSI Colors
BOLD='\033[1m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}==================================================${NC}"
echo -e "${BOLD}${CYAN}   Full Image Build Launcher${NC}"
echo -e "${BOLD}${CYAN}==================================================${NC}"

source bitbake-builds/poky-master/build/init-build-env

bitbake core-image-falcon

echo -e "${BOLD}${CYAN}==================================================${NC}"
