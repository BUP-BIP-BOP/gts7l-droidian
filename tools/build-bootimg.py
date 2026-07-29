#!/usr/bin/env python3
"""
build-bootimg.py — turn a raw Droidian/CI boot.img into a Samsung-ABL-acceptable,
bootable boot.img for the Galaxy Tab S7 LTE (SM-T875 / gts7l).

Оффсеты и board name сняты из стоковой прошивки этого устройства, а не
унаследованы от соседних портов: ramdisk 0x02000000 и tags 0x01e00000 не
совпадают с дефолтами mkbootimg.

Usage:
  python3 build-bootimg.py <raw_boot.img> <output.img> [--rescue]

  --rescue  use console=null to drop into RNDIS+telnet rescue at 192.168.2.15:23

Requires: avbtool (in PATH or via AVBTOOL=/path/to/avbtool.py) and
testkey_rsa4096.pem next to this script (or via --key).
"""
import struct, sys, subprocess, os, argparse, shutil, re

# avbtool is not packaged on every host (macOS in particular). Allow pointing at
# a checkout of AOSP external/avb: AVBTOOL=/path/to/avbtool.py
AVBTOOL = os.environ.get("AVBTOOL", "avbtool")
AVB_CMD = [sys.executable, AVBTOOL] if AVBTOOL.endswith(".py") else [AVBTOOL]

# --- Samsung Tab S7 LTE constants ---
BOOT_PARTITION_SIZE     = 71303168     # /dev/block/by-name/boot (confirmed from BoardConfig)
RECOVERY_PARTITION_SIZE = 86888448     # /dev/block/by-name/recovery
ROLLBACK_INDEX          = 1900000000
RAMDISK_ADDR = 0x02000000
TAGS_ADDR    = 0x01e00000
OS_VERSION   = 0x16000184  # снято из стокового T875XXS5DXD1: 11.0.0 / 2024-04
BOARD_NAME   = b"SRPTC18C005"  # product из стокового boot.img SM-T875

# Cmdline не задаётся здесь: он приходит из debian/kernel-info.mk вместе с
# образом и содержит параметры, без которых initramfs Droidian не поднимется —
# loop.max_part=7 для монтирования rootfs.img и droidian.lvm.prefer.
# Наследованный от порта T870 хардкод затирал их, и устройство вставало на
# заставке. Здесь только переключается консоль.



def read_cmdline(d):
    return bytes(d[64:64 + 512]).split(b"\x00", 1)[0].decode()


FDT_MAGIC = b"\xd0\x0d\xfe\xed"
SOC_MODEL = re.compile(rb"kona v(\d+)(?:\.(\d+))? SoC")


def split_fdt(blob):
    """Секция dtb — просто склеенные FDT-блобы; режем по totalsize."""
    out, off = [], 0
    while off < len(blob) and blob[off:off + 4] == FDT_MAGIC:
        total = struct.unpack_from(">I", blob, off + 4)[0]
        out.append(blob[off:off + total])
        off += total
    return out if off == len(blob) else None


def sort_dtb(blob):
    """Упорядочить device tree по ревизии SoC: kona v1, v2, v2.1.

    Загрузчик Samsung на kona раздаёт ядру блоб по позиции в секции, а не по
    qcom,msm-id. Сниппет упаковки Droidian склеивает dtb в порядке glob'а
    (v2.1 первым), и ядро получает device tree от чужой ревизии SoC — падает до
    инициализации консоли, поэтому в pstore пусто, а планшет стоит на заставке.
    Рабочий boot.img Ubuntu Touch на этом же устройстве держит порядок по
    возрастанию ревизии.
    """
    parts = split_fdt(blob)
    if not parts:
        return blob                       # не разобрали — не трогаем
    def key(item):
        i, p = item
        m = SOC_MODEL.search(p)
        if not m:
            return (1, i, 0)
        return (0, int(m.group(1)), int(m.group(2) or 0))
    ordered = [p for _, p in sorted(enumerate(parts), key=key)]
    return b"".join(ordered)


def dtb_range(d):
    """Смещение и длина секции dtb в образе boot header v2."""
    page = struct.unpack_from("<I", d, 36)[0]
    if struct.unpack_from("<I", d, 40)[0] < 2:
        return None
    sizes = [struct.unpack_from("<I", d, o)[0] for o in (8, 16, 24, 1632)]
    dtb_size = struct.unpack_from("<I", d, 1648)[0]
    if not dtb_size:
        return None
    pages = lambda n: (n + page - 1) // page
    off = page + sum(pages(s) for s in sizes) * page
    return off, dtb_size


def patch_header(path, rescue):
    with open(path, "rb") as f:
        d = bytearray(f.read())
    assert d[:8] == b"ANDROID!", "not an Android boot.img"

    # console=null — то, что кладёт упаковка; для обычной загрузки нужен tty0,
    # для rescue оставляем как есть (telnet по RNDIS).
    cmdline = read_cmdline(d)
    if not rescue:
        cmdline = cmdline.replace("console=null", "console=tty0")

    # EXTRA_CMDLINE позволяет дописать параметры без пересборки ядра —
    # например datapart=, который руководство Droidian предлагает, если
    # initramfs не находит раздел userdata.
    extra = os.environ.get("EXTRA_CMDLINE", "").strip()
    if extra:
        cmdline = f"{cmdline} {extra}"
    rng = dtb_range(d)
    if rng:
        off, size = rng
        ordered = sort_dtb(bytes(d[off:off + size]))
        assert len(ordered) == size, "порядок dtb изменил размер секции"
        d[off:off + size] = ordered

    struct.pack_into("<I", d, 20, RAMDISK_ADDR)
    struct.pack_into("<I", d, 32, TAGS_ADDR)
    struct.pack_into("<I", d, 44, OS_VERSION)
    d[48:64] = BOARD_NAME.ljust(16, b"\x00")
    cb = cmdline.encode()
    assert len(cb) < 512, "cmdline too long for v2 header"
    for i in range(64, 64 + 512):
        d[i] = 0
    d[64:64 + len(cb)] = cb
    with open(path, "wb") as f:
        f.write(bytes(d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--rescue", action="store_true")
    ap.add_argument("--partition", default="boot", choices=["boot", "recovery"])
    ap.add_argument("--key", default=os.path.join(os.path.dirname(__file__), "..", "testkey_rsa4096.pem"))
    a = ap.parse_args()
    psize = BOOT_PARTITION_SIZE if a.partition == "boot" else RECOVERY_PARTITION_SIZE

    shutil.copy(a.raw, a.out)

    # Samsung ABL ищет метку SEANDROIDENFORCE в самом конце образа. Упаковка
    # ядра дописывает её к секции ядра, и там загрузчик её не видит: рабочий
    # boot.img Ubuntu Touch на этом же устройстве держит метку последними 16
    # байтами. Без неё планшет молча стоит на заставке, ядро не стартует.
    TAIL = b"SEANDROIDENFORCE"
    with open(a.out, "rb") as f:
        blob = f.read()
    if not blob.endswith(TAIL):
        with open(a.out, "ab") as f:
            f.write(TAIL)
    patch_header(a.out, a.rescue)
    subprocess.run(AVB_CMD + ["erase_footer", "--image", a.out],
                   stderr=subprocess.DEVNULL)
    subprocess.run(AVB_CMD + ["add_hash_footer",
                    "--image", a.out,
                    "--partition_size", str(psize),
                    "--partition_name", a.partition,
                    "--algorithm", "SHA256_RSA4096",
                    "--key", a.key,
                    "--rollback_index", str(ROLLBACK_INDEX)], check=True)
    print(f"OK: {a.out}  partition={a.partition} size={psize} "
          f"cmdline={'rescue/console=null' if a.rescue else 'console=tty0'}")


if __name__ == "__main__":
    main()
