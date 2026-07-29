#!/bin/sh
# Печатает путь к avbtool.py, скачивая AOSP external/avb при необходимости.
# Нужен там, где avbtool не установлен пакетом — например, на macOS.
set -eu
WORK="${AVB_DIR:-${TMPDIR:-/tmp}/avb-gts7l}"
[ -f "$WORK/avb/avbtool.py" ] || git clone -q --depth=1 \
    https://android.googlesource.com/platform/external/avb "$WORK/avb"
echo "$WORK/avb/avbtool.py"
