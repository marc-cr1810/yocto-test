SUMMARY = "A custom image: core-image-falcon"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL = "    ${CORE_IMAGE_EXTRA_INSTALL} \
    gps-sim \
    legs-main \
    packagegroup-core-boot \
    pps-sim \
"

IMAGE_FEATURES += "ssh-server-openssh"

IMAGE_LINGUAS = " "

