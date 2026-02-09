SUMMARY = "A custom image: core-image-falcon"
LICENSE = "MIT"

inherit core-image

IMAGE_INSTALL = "    ${CORE_IMAGE_EXTRA_INSTALL} \
    axi-dma \
    legs-main \
    packagegroup-core-boot \
    vim \
"

IMAGE_LINGUAS = " "
