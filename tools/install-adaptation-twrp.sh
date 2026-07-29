#!/bin/bash
# Раскладывает пакет адаптации внутрь /data/rootfs.img с устройства в TWRP.
#
#   tools/install-adaptation-twrp.sh
#
# Нужен, пока на планшете нет сети: ставит ровно то же, что
# adaptation-samsung-gts7l-configs.install и postinst, но без dpkg.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
A="$HERE/adaptation"
R=/tmp/rootfs

info() { printf '\033[36m==> %s\033[0m\n' "$*"; }

adb wait-for-device
[ "$(adb get-state)" = "recovery" ] || { echo "устройство не в TWRP"; exit 1; }

info "монтирую rootfs.img"
adb shell "mount /data 2>/dev/null; umount $R 2>/dev/null; mkdir -p $R
L=\$(losetup -f --show /data/rootfs.img) && echo \$L > /tmp/loopdev && mount \$L $R"
adb shell "mountpoint -q $R || grep -q ' $R ' /proc/mounts" \
    || { echo "rootfs.img не смонтировался"; exit 1; }

info "копирую конфиги"
# Соответствует adaptation-samsung-gts7l-configs.install.
push() { adb shell "mkdir -p $R/$2"; adb push -q "$A/$1" "$R/$2" >/dev/null; }
push etc/NetworkManager/conf.d/90-gts7l-unmanaged.conf   etc/NetworkManager/conf.d/
push etc/NetworkManager/dispatcher.d/50-wlan-routes      etc/NetworkManager/dispatcher.d/
push etc/bluetooth/main.conf                             etc/bluetooth/
push etc/environment.d/65-phoc-no-direct-scanout.conf    etc/environment.d/
push etc/libinput/local-overrides.quirks                 etc/libinput/
push etc/ofono/binder.d/qti.conf                         etc/ofono/binder.d/
push etc/ofono/ril_subscription.d/qti.conf               etc/ofono/ril_subscription.d/
push etc/phosh/phoc.ini                                  etc/phosh/
push etc/pulse/arm_droid_card_custom.pa                  etc/pulse/
push usr/lib/adaptation-samsung-gts7l/wlan-routes-fix    usr/lib/adaptation-samsung-gts7l/
push usr/lib/droidian/device/encryption-supported        usr/lib/droidian/device/

adb shell "chmod 755 $R/etc/NetworkManager/dispatcher.d/50-wlan-routes \
                     $R/usr/lib/adaptation-samsung-gts7l/wlan-routes-fix"

# postinst: матрица акселерометра и автозапуск sensorfwd. systemctl здесь
# недоступен, поэтому симлинк в multi-user.target.wants создаётся вручную.
info "правлю sensorfwd (postinst)"
F=etc/sensorfw/sensord-hybris.conf
if adb shell "[ -f $R/$F ]" 2>/dev/null; then
    tmp=$(mktemp)
    adb pull -q "$R/$F" "$tmp" >/dev/null
    python3 - "$tmp" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p).read()
m = '0,-1,0,1,0,0,0,0,1'
def fix(block):
    return re.sub(r'(transformation_matrix\s*=\s*)"[^"]*"', r'\1"%s"' % m, block)
out, cur = [], None
for line in s.splitlines(True):
    if line.startswith('['):
        cur = line.strip()
    out.append(fix(line) if cur == '[accelerometer]' else line)
open(p, 'w').write(''.join(out))
PY
    adb push -q "$tmp" "$R/$F" >/dev/null
    rm -f "$tmp"
else
    echo "   sensord-hybris.conf нет — пропускаю"
fi
adb shell "[ -f $R/lib/systemd/system/sensorfwd.service ] && \
    mkdir -p $R/etc/systemd/system/multi-user.target.wants && \
    ln -sf /lib/systemd/system/sensorfwd.service \
        $R/etc/systemd/system/multi-user.target.wants/sensorfwd.service" || true

info "отмонтирую"
adb shell "sync; umount $R; losetup -d \$(cat /tmp/loopdev) 2>/dev/null; rm -f /tmp/loopdev"
info "готово — перезагружай в систему"
