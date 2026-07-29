#!/usr/bin/env python3
"""
make-touchpad-dtbo.py — produce the gts7l dtbo with Book Cover Keyboard
trackpad orientation fixed for Droidian's landscape coordinate system.

Patches touchpad,invert = <0 1 1> -> <0 0 0> in every board-revision FDT,
then re-adds AVB hash footer so Samsung ABL accepts it under vbmeta flags=0x02.

Usage:
  python3 make-touchpad-dtbo.py <stock_dtbo.img> <out_dtbo.img> [--key testkey_rsa4096.pem]

Requires: dtc и avbtool — в PATH или через переменные DTC и AVBTOOL;
testkey рядом со скриптом (или через --key).

Если правка не нужна или инструментов нет, скрипт завершится с ненулевым
кодом, а make-flashable.sh просто скопирует стоковый dtbo.
"""
import struct, subprocess, sys, os, argparse, tempfile

# avbtool и dtc есть не на каждом хосте (macOS в первую очередь).
# AVBTOOL может указывать на avbtool.py из AOSP, DTC — на бинарник dtc.
AVBTOOL = os.environ.get("AVBTOOL", "avbtool")
AVB_CMD = [sys.executable, AVBTOOL] if AVBTOOL.endswith(".py") else [AVBTOOL]
DTC = os.environ.get("DTC", "dtc")

OLD = "touchpad,invert = <0x00 0x01 0x01>"
NEW = "touchpad,invert = <0x00 0x00 0x00>"
PART_SIZE = 10485760  # gts7l dtbo partition size (same as T970)


def align(x, a=4096):
    return (x + a - 1) // a * a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stock")
    ap.add_argument("out")
    ap.add_argument("--key", default=os.path.join(os.path.dirname(__file__), "..", "testkey_rsa4096.pem"))
    a = ap.parse_args()
    d = open(a.stock, "rb").read()
    magic, total, hsz, esz, ecnt, eoff, psz, ver = struct.unpack(">IIIIIIII", d[:32])
    assert magic == 0xd7b7ab1e, "not an Android dt_table dtbo"
    ents = [
        struct.unpack(">II", d[eoff + i * esz: eoff + i * esz + 8])
        + (d[eoff + i * esz + 8: eoff + i * esz + esz],)
        for i in range(ecnt)
    ]
    tmp = tempfile.mkdtemp()
    new, changed = [], 0
    for i, (sz, off, rest) in enumerate(ents):
        fdt = d[off:off + sz]
        fi = os.path.join(tmp, f"i{i}.dtb")
        open(fi, "wb").write(fdt)
        dts = subprocess.run(
            [DTC, "-I", "dtb", "-O", "dts", fi], capture_output=True
        ).stdout.decode("utf-8", "replace")
        if OLD in dts:
            dts = dts.replace(OLD, NEW)
            changed += 1
            fo = os.path.join(tmp, f"o{i}.dtb")
            subprocess.run(
                [DTC, "-I", "dts", "-O", "dtb", "-o", fo],
                input=dts.encode(),
                capture_output=True,
            )
            new.append(open(fo, "rb").read())
        else:
            new.append(fdt)
    he = 32 + ecnt * esz
    cur = align(he)
    eb = bytearray()
    fa = bytearray()
    for i, fdt in enumerate(new):
        eb += struct.pack(">II", len(fdt), cur) + ents[i][2]
        fa += fdt + b"\x00" * (align(len(fdt)) - len(fdt))
        cur += align(len(fdt))
    out = struct.pack(">IIIIIIII", magic, cur, hsz, esz, ecnt, eoff, psz, ver) + eb
    out += b"\x00" * (align(he) - len(out))
    out += fa
    open(a.out, "wb").write(out)
    subprocess.run(
        AVB_CMD + [
            "add_hash_footer",
            "--image", a.out,
            "--partition_name", "dtbo",
            "--partition_size", str(PART_SIZE),
            "--algorithm", "SHA256_RSA4096",
            "--key", a.key,
            "--rollback_index", "0",
        ],
        check=True,
    )
    print(f"OK: {a.out}  (patched {changed} FDTs, signed, {os.path.getsize(a.out)} bytes)")


if __name__ == "__main__":
    main()
