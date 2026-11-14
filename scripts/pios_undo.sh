#!/usr/bin/env bash
# Undo what deploy/scripts/pios_setup.sh --o1 and our benchmarks added to a Raspberry Pi OS card. Run ON THE PI (or with the card mounted: ROOT=/mnt/x).
# It removes only things this project created. It cannot know which apt packages were already installed before, so those are listed, not removed.
set -u
ROOT=${ROOT:-}; H=${HOME_DIR:-/home/raspi}
run() { echo "+ $*"; [[ ${DRY:-1} == 1 ]] || "$@"; }
echo "DRY=${DRY:-1} (DRY=0 to apply)"
for u in vieedge vieedge-tuning; do run rm -f "$ROOT/etc/systemd/system/$u.service" "$ROOT/etc/systemd/system/multi-user.target.wants/$u.service"; done
run rm -rf "$ROOT/etc/vieedge" "$ROOT/usr/local/bin/vieedge-tune" "$ROOT/usr/local/bin/vieedge-osmode" "$ROOT/usr/bin/vieedge-tune"
run rm -rf "$ROOT$H/vieedge" "$ROOT$H/vieedge-src" "$ROOT$H/llama.cpp" "$ROOT$H/setup.log" "$ROOT$H/pibench.sh" "$ROOT$H/rt_compare.sh" "$ROOT$H/compare_pios.log"
# the setup added this line to the boot config
if [[ -f $ROOT/boot/firmware/config.txt ]]; then run sed -i '/^dtparam=pciex1_gen=3$/d' "$ROOT/boot/firmware/config.txt"; fi
echo
echo "NOT undone automatically (check by hand):"
echo " * --o1 disabled these services (re-enable the ones you used): sudo systemctl enable --now bluetooth cups avahi-daemon ModemManager triggerhappy packagekit rpi-connect"
echo " * apt-get installed: python3-venv python3-dev python3-numpy python3-yaml python3-psutil python3-alsaaudio python3-libgpiod libespeak-ng1 espeak-ng-data alsa-utils rt-tests stress-ng git cmake build-essential libgomp1 rsync (+ hailo-all if available). See /var/log/apt/history.log for what was newly installed or upgraded."
