#!/bin/bash
# Расширяет /data/rootfs.img на устройстве в TWRP.
#
#   tools/grow-rootfs.sh [размер]        # по умолчанию 16G
#
# Образ с images.droidian.org приезжает заполненным под завязку (свободно ~16 МБ).
# Ветка LVM тут не работает: раздел userdata отформатирован в ext4, тома
# "droidian" нет, initramfs откатывается на файл /data/rootfs.img и не растит его.
# Итог — система грузится, но Android-init падает на SetupMountNamespaces с
# ENOSPC, journald не открывает журнал, графики нет.
set -euo pipefail

SIZE="${1:-16G}"
adb wait-for-device

adb shell "set -e
mount /data 2>/dev/null || true
[ -f /data/rootfs.img ] || { echo 'нет /data/rootfs.img — устройство не в TWRP или образ не залит'; exit 1; }
truncate -s $SIZE /data/rootfs.img
L=\$(losetup -f --show /data/rootfs.img)
e2fsck -fy \$L | tail -3
resize2fs \$L
mkdir -p /tmp/r && mount -o ro \$L /tmp/r && df -h /tmp/r
umount /tmp/r; losetup -d \$L 2>/dev/null || true"
