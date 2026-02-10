SUMMARY = "legs-main application"
LICENSE = "CLOSED"

inherit cmake

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${THISDIR}/../../../../../sw/cpp/legs-main"
EXTERNALSRC_BUILD = "${WORKDIR}/build"


