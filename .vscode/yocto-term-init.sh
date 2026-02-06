#!/bin/bash
# VS Code Terminal Initialization Script

# 1. Source the user's standard bash configuration
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi

# 2. Source the Yocto workspace environment
# We assume we are running from the workspace root
if [ -f scripts/env_init.sh ]; then
    source scripts/env_init.sh
fi
