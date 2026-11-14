#!/usr/bin/env bash
# Build the VieEdge Yocto image inside kas-container (works on any recent host, incl. Ubuntu 26.04).
#   ./yocto/build.sh            -> O2  image (standard kernel)        build dir: yocto/build
#   ./yocto/build.sh rt         -> O3/O4 image (PREEMPT_RT, isolcpus)  build dir: yocto/build-rt
#   ./yocto/build.sh rt shell   -> interactive bitbake shell
#   ./yocto/build.sh "" bitbake <targets...>   -> build specific recipes
# Downloads + sstate are shared between both builds (~/yocto-cache) so the RT build only rebuilds the kernel.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VARIANT="${1:-}"; shift || true

KAS_FILE="yocto/kas.yml"; BUILD_SUBDIR="build"
if [[ "$VARIANT" == "rt" ]]; then KAS_FILE="yocto/kas-rt.yml"; BUILD_SUBDIR="build-rt"; fi

export KAS_WORK_DIR="$REPO/yocto"
export KAS_BUILD_DIR="$REPO/yocto/$BUILD_SUBDIR"
export DL_DIR="${DL_DIR:-$HOME/yocto-cache/downloads}"
export SSTATE_DIR="${SSTATE_DIR:-$HOME/yocto-cache/sstate}"
mkdir -p "$DL_DIR" "$SSTATE_DIR" "$KAS_BUILD_DIR"

KAS=kas-container
command -v kas-container >/dev/null || KAS="$HOME/.local/bin/kas-container"
# Cap the build container so a heavy C++ link can never OOM the whole desktop (14 GB laptop)
MEM="${YOCTO_MEM:-7g}"
RT_ARGS=(--runtime-args "--memory=$MEM --memory-swap=$((${MEM%g} + 3))g")

cd "$REPO"
# copy the finished image out of tmp/ (tmp/ can then be deleted to save ~10 GB; sstate makes rebuilds fast)
publish() {
  local n=o2; [[ "$VARIANT" == "rt" ]] && n=rt
  local d="$KAS_BUILD_DIR/tmp/deploy/images/raspberrypi5"
  [[ -e "$d/vieedge-image-raspberrypi5.rootfs.wic.bz2" ]] || return 0
  mkdir -p "$REPO/images/$n"
  cp -L "$d/vieedge-image-raspberrypi5.rootfs.wic.bz2" "$REPO/images/$n/vieedge-image-$n.wic.bz2"
  cp -L "$d/vieedge-image-raspberrypi5.rootfs.wic.bmap" "$REPO/images/$n/vieedge-image-$n.wic.bmap"
  cp -L "$d/vieedge-image-raspberrypi5.rootfs.manifest" "$REPO/images/$n/vieedge-image-$n.manifest"
  echo "image -> images/$n/vieedge-image-$n.wic.bz2"
}

case "${1:-build}" in
  build)  "$KAS" "${RT_ARGS[@]}" build "$KAS_FILE" && publish ;;
  shell)  exec "$KAS" "${RT_ARGS[@]}" shell "$KAS_FILE" ;;
  bitbake) shift; "$KAS" "${RT_ARGS[@]}" shell "$KAS_FILE" -c "bitbake -k $*" && publish ;;
  *) echo "unknown command $1"; exit 2 ;;
esac
