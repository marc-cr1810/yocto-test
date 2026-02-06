SUMMARY = "example application"
LICENSE = "CLOSED"

DEPENDS = "spdlog"

inherit cmake

# Use local source code directly
inherit externalsrc
EXTERNALSRC = "${THISDIR}/../../../../../sw/cpp/example"
EXTERNALSRC_BUILD = "${WORKDIR}/build"


