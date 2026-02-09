SUMMARY = "A custom image: core-image-falcon"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL = "    ${CORE_IMAGE_EXTRA_INSTALL} \
    axi_dma \
    legs_main \
    packagegroup-core-boot \
    tailscale \
    vim \
"

IMAGE_LINGUAS = " "


