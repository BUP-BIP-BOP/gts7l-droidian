#!/bin/bash
# Собирает комплект для прошивки Droidian на SM-T875 в out/.
#
#   tools/make-flashable.sh [путь-к-kernel.deb]
#
# Без аргумента забирает свежий артефакт сборки ядра из форка на GitHub.
# Rootfs скачивается отдельно с images.droidian.org и распаковывается в raw —
# см. README.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

KERNEL_REPO="${KERNEL_REPO:-BUP-BIP-BOP/kernel_samsung_sm8250}"
OUT="$HERE/out"
WORK="$OUT/.work"

info() { printf '\033[36m==> %s\033[0m\n' "$*"; }
red()  { printf '\033[31m%s\033[0m\n' "$*"; }

mkdir -p "$OUT" "$WORK"

DEB="${1:-}"

if [ -z "$DEB" ]; then
    command -v gh >/dev/null || { red "нужен gh или путь к .deb аргументом"; exit 1; }
    info "ищу свежую сборку ядра в $KERNEL_REPO"
    RUN=$(gh run list --repo "$KERNEL_REPO" --branch droidian --status success \
          --limit 1 --json databaseId --jq '.[0].databaseId')
    [ -n "$RUN" ] || { red "нет успешных сборок на ветке droidian"; exit 1; }

    info "скачиваю артефакт прогона $RUN"
    rm -rf "$WORK/deb" && mkdir -p "$WORK/deb"
    gh run download "$RUN" --repo "$KERNEL_REPO" -D "$WORK/deb"
    DEB=$(find "$WORK/deb" -name "linux-bootimage-*.deb" | head -n1)
    [ -n "$DEB" ] || { red "в артефакте нет linux-bootimage-*.deb"; exit 1; }
fi

info "распаковываю $(basename "$DEB")"
rm -rf "$WORK/x" && mkdir -p "$WORK/x"
( cd "$WORK/x" && ar x "$DEB" && tar xf data.tar.* )

RAW_BOOT=$(find "$WORK/x" -name "boot.img-*" | head -n1)
RAW_DTBO=$(find "$WORK/x" -name "dtbo.img-*" | head -n1)
[ -n "$RAW_BOOT" ] || { red "boot.img в пакете не найден"; exit 1; }

AVBTOOL="${AVBTOOL:-$("$HERE/tools/get-avbtool.sh")}"
export AVBTOOL

info "собираю boot.img под Samsung ABL"
python3 tools/build-bootimg.py "$RAW_BOOT" "$OUT/boot.img"

info "собираю rescue-образ (console=null, telnet по RNDIS)"
python3 tools/build-bootimg.py "$RAW_BOOT" "$OUT/boot-rescue.img" --rescue

if [ -n "$RAW_DTBO" ]; then
    info "патчу dtbo под тачпад Book Cover"
    python3 tools/make-touchpad-dtbo.py "$RAW_DTBO" "$OUT/dtbo.img" \
        || cp "$RAW_DTBO" "$OUT/dtbo.img"
else
    red "dtbo.img в пакете нет — раздел DTBO останется стоковым"
fi

cp vbmeta-disabled.img "$OUT/vbmeta-disabled.img"

echo
info "готово, комплект в out/"
ls -l "$OUT"/*.img | awk '{printf "  %-24s %s байт\n", $9, $5}'
cat <<'EOF'

Дальше:
  1. rootfs с images.droidian.org -> simg2img -> droidian-rootfs.raw
  2. Download Mode:
       heimdall flash --VBMETA out/vbmeta-disabled.img --BOOT out/boot.img \
                      --DTBO out/dtbo.img --no-reboot
  3. Recovery: залить rootfs на userdata
EOF
