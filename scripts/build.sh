#!/bin/bash
scripts_dir=$(dirname "$(readlink -f "$0")")
python3 "$scripts_dir/build_recipe.py" core-image-falcon "$@"
