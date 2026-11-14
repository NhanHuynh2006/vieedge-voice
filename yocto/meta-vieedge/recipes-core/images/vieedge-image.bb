SUMMARY = "VieEdge-Voice: offline Vietnamese voice Q&A on Raspberry Pi 5 + Hailo-8L"
LICENSE = "MIT"

require recipes-core/images/core-image-minimal.bb

IMAGE_FEATURES += "ssh-server-openssh"

IMAGE_INSTALL:append = " \
    packagegroup-vieedge \
    ${@'vieedge-models' if d.getVar('VIEEDGE_BUNDLE_MODELS') == '1' else ''} \
"

# root password "vieedge" (change it: passwd). Generated with: openssl passwd -6 -salt vieedgesalt vieedge
inherit extrausers
EXTRA_USERS_PARAMS = "usermod -p '\$6\$vieedgesalt\$jojEMlyrBmYD9cU9XJnam5BAAsk/8ITWrruNNUE4WWQrXb541VRYghdN45qFgeeVBZQkNIEWWqXqkNbhEz616/' root;"

# Allow root ssh login with password on this lab device
ROOTFS_POSTPROCESS_COMMAND += "vieedge_sshd_root;"
vieedge_sshd_root() {
    if [ -f ${IMAGE_ROOTFS}${sysconfdir}/ssh/sshd_config ]; then
        sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' ${IMAGE_ROOTFS}${sysconfdir}/ssh/sshd_config
    fi
}
