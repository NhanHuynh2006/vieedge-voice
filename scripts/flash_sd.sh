#!/usr/bin/env bash
# Flash the VieEdge Yocto image to an SD card / USB stick, grow the root partition to fill it, and
# pre-configure the Pi to JOIN an existing Wi-Fi network (instead of making its own hotspot).
#
#   sudo WIFI_SSID='NhanHuynh' WIFI_PSK='<password>' scripts/flash_sd.sh /dev/sdX [rt|o2]
#
# ERASES the whole target device. Refuses anything that is not a removable device of 8-512 GB.
set -euo pipefail
DEV="${1:?usage: sudo WIFI_SSID=.. WIFI_PSK=.. $0 /dev/sdX [rt|o2]}"
VAR="${2:-rt}"
: "${WIFI_SSID:?set WIFI_SSID}" "${WIFI_PSK:?set WIFI_PSK}"
[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
cd "$(dirname "$0")/.."
IMG="images/$VAR/vieedge-image-$VAR.wic.bz2"
[[ -f $IMG ]] || { echo "missing $IMG"; exit 1; }

# ---- safety checks
[[ -b $DEV ]] || { echo "$DEV is not a block device"; exit 1; }
RM=$(lsblk -dno RM "$DEV" | tr -d ' ')
SIZE_GB=$(( $(lsblk -dbno SIZE "$DEV") / 1000000000 ))
ROOTDEV=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" | head -1)
[[ "$DEV" == "/dev/$ROOTDEV" ]] && { echo "that is the system disk"; exit 1; }
[[ $RM == 1 ]] || { echo "$DEV is not removable (RM=$RM) - refusing"; exit 1; }
(( SIZE_GB >= 8 && SIZE_GB <= 512 )) || { echo "unexpected size ${SIZE_GB} GB - refusing"; exit 1; }
lsblk -o NAME,SIZE,MODEL,TRAN "$DEV"
read -r -p "ERASE $DEV (${SIZE_GB} GB) and write $IMG ? type YES: " ok
[[ $ok == YES ]] || { echo aborted; exit 1; }

# ---- flash
for p in $(lsblk -lno PATH "$DEV" | tail -n +2); do umount "$p" 2>/dev/null || true; done
bmaptool copy "$IMG" "$DEV"
sync; partprobe "$DEV"; sleep 2
PART2=$(lsblk -lno PATH "$DEV" | sed -n 3p)   # DEV, part1, part2

# ---- grow root partition to the whole card
parted -s "$DEV" resizepart 2 100%
partprobe "$DEV"; sleep 2
e2fsck -fy "$PART2" || true
resize2fs "$PART2"

# ---- Wi-Fi client config inside the rootfs
MNT=$(mktemp -d)
mount "$PART2" "$MNT"
trap 'umount "$MNT" 2>/dev/null; rmdir "$MNT"' EXIT

SYS=lib/systemd/system; [[ -e $MNT/usr/lib/systemd/system/wpa_supplicant@.service ]] && SYS=usr/lib/systemd/system
if [[ ! -e $MNT/$SYS/wpa_supplicant@.service ]]; then
  echo "WARNING: wpa_supplicant@.service not found in the image - Wi-Fi client cannot be enabled"; exit 2
fi

# no own hotspot any more
rm -f "$MNT"/etc/systemd/system/multi-user.target.wants/vieedge-hotspot.service
rm -f "$MNT"/etc/systemd/network/20-wlan0-ap.network

mkdir -p "$MNT/etc/wpa_supplicant" "$MNT/etc/systemd/network" "$MNT/etc/systemd/system/multi-user.target.wants"
cat > "$MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf" <<EOF
ctrl_interface=/var/run/wpa_supplicant
update_config=0
country=VN
network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PSK"
    key_mgmt=WPA-PSK
    scan_ssid=1
}
EOF
chmod 600 "$MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
cat > "$MNT/etc/systemd/network/20-wlan0.network" <<'EOF'
[Match]
Name=wlan0

[Network]
DHCP=yes
EOF
ln -sf "/$SYS/wpa_supplicant@.service" "$MNT/etc/systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service"
sync
echo
echo "DONE. Put the card in the Pi and power it on."
echo "Find its IP on your router (host 'raspberrypi5' / MAC starting d8:3a:dd or 2c:cf:67), or plug in Ethernet."
echo "ssh root@<ip>   password: vieedge  (change it with passwd)   dashboard: http://<ip>:8000"
