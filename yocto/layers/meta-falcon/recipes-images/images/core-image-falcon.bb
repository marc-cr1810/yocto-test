SUMMARY = "Custom minimal image core-image-falcon"
LICENSE = "MIT"

inherit core-image

# Minimal image configuration (like core-image-minimal)
IMAGE_INSTALL = "    packagegroup-core-boot \
    vim \
    example \
"

# Add SSH server
IMAGE_FEATURES += "ssh-server-dropbear"

# Keep image minimal
IMAGE_LINGUAS = ""
