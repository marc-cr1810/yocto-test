#!/bin/bash
# Wrapper for the Python QEMU runner
SCRIPT_DIR=$(dirname "$0")
python3 "$SCRIPT_DIR/run_qemu.py" "$@"