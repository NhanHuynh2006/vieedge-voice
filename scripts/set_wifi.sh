#!/usr/bin/env bash
# Give the VieEdge Yocto card TWO Wi-Fi networks without re-flashing (nothing else on the card is touched).
# Passwords are read from this laptop's saved NetworkManager profiles, never printed.
#
#   sudo scripts/set_wifi.sh /dev/sdX [ISLAB_C102_5G NhanHuynh]      # first = preferred when both are in range
#
# Plug the card into the laptop first (the card reader shows 0B when empty). The wpa_supplicant network blocks accept both
# WPA2 (WPA-PSK) and WPA3 (SAE) for each SSID, so ISLAB_C102_5G (WPA3-SAE) and the phone hotspot both work.
set -euo pipefail
DEV="${1:?usage: sudo $0 /dev/sdX [preferred-ssid other-ssid ...]}"; shift || true
SSIDS=("${@:-ISLAB_C102_5G NhanHuynh}")
[[ ${#SSIDS[@]} -eq 1 ]] && read -r -a SSIDS <<<"${SSIDS[0]}"
[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
[[ -b $DEV && $(lsblk -dno RM "$DEV" | tr -d ' ') == 1 ]] || { echo "$DEV is not a removable block device"; exit 1; }
ROOTDEV=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" | head -1)
[[ $DEV == "/dev/$ROOTDEV" ]] && { echo "that is the system disk"; exit 1; }
PART2=$(lsblk -lno PATH "$DEV" | sed -n 3p)
[[ -n $PART2 ]] || { echo "no second partition on $DEV (is the VieEdge card in?)"; exit 1; }

conf=$(mktemp)
{
  echo "ctrl_interface=/var/run/wpa_supplicant"
  echo "update_config=0"
  echo "country=VN"
  echo "sae_pwe=2"
  prio=$(( ${#SSIDS[@]} * 10 ))
  for ssid in "${SSIDS[@]}"; do
    psk=$(nmcli -s -g 802-11-wireless-security.psk connection show "$ssid" 2>/dev/null || true)
    [[ -n $psk ]] || { echo "no saved password for '$ssid' on this laptop" >&2; exit 1; }
    cat <<NET
network={
    ssid="$ssid"
    psk="$psk"
    key_mgmt=WPA-PSK SAE
    ieee80211w=1
    scan_ssid=1
    priority=$prio
}
NET
    prio=$(( prio - 10 ))
  done
} > "$conf"

MNT=$(mktemp -d)
trap 'umount "$MNT" 2>/dev/null; rmdir "$MNT"; rm -f "$conf"' EXIT
mount "$PART2" "$MNT"
[[ -d $MNT/etc/wpa_supplicant ]] || { echo "not a VieEdge Yocto rootfs (no /etc/wpa_supplicant)"; exit 1; }
install -m 600 "$conf" "$MNT/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"
sync
echo "Wi-Fi on the card: ${SSIDS[*]} (preferred: ${SSIDS[0]}). Put it back in the Pi."
