SUMMARY = "axi_dma kernel module"
LICENSE = "CLOSED"
PN = "axi-dma"
PV = "1.0"

inherit module

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${THISDIR}/../../../../../sw/module/axi-dma"
EXTERNALSRC_BUILD = "${WORKDIR}/build"

# Set up build directory with symlinks to source files
do_configure:prepend() {
    # Create build directory
    mkdir -p ${EXTERNALSRC_BUILD}
    
    # Symlink source files to build directory
    for file in ${EXTERNALSRC}/*; do
        filename=$(basename "$file")
        # Skip symlinks and hidden files
        if [ ! -L "$file" ] && [ "${filename#.}" = "$filename" ]; then
            ln -sf "$file" "${EXTERNALSRC_BUILD}/$filename"
        fi
    done
}



# Kernel modules need to be installed in specific way if strict
