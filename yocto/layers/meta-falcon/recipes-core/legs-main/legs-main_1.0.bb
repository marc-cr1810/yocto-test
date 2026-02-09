SUMMARY = "legs_main application"
LICENSE = "CLOSED"
PN = "legs-main"
PV = "1.0"

inherit cmake

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${THISDIR}/../../../../../sw/cpp/legs-main"
EXTERNALSRC_BUILD = "${WORKDIR}/build"


