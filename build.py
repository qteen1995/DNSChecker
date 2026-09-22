# -*- coding: utf-8 -*-
"""打包成单文件 exe。

用法：
    pip install pyinstaller
    python build.py

产出：
    dist/DNSChecker.exe      （单文件，双击即用，无需 Python 环境）
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "DNSChecker"
ICON = os.path.join(HERE, "app.ico")


def make_icon(path=ICON, size=64):
    """纯 Python 画一个图标：深蓝圆角底 + 三根上升的信号柱。"""
    S = size
    BG_TOP = (0xB7, 0x4A, 0x53, 0xFF)     # BGRA —— 蓝
    BG_BOT = (0x9C, 0x2B, 0x21, 0xFF)     # 深一点的蓝
    FG = (0xFF, 0xFF, 0xFF, 0xFF)
    r = S * 0.22

    def in_body(x, y):
        cx = min(max(x, r), (S - 1) - r)
        cy = min(max(y, r), (S - 1) - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    bars = []
    bw = S * 0.15
    for i, (cxr, top) in enumerate(((0.28, 0.52), (0.50, 0.38), (0.72, 0.24))):
        bars.append((S * cxr - bw / 2, S * cxr + bw / 2, S * top, S * 0.80))

    px = [[(0, 0, 0, 0)] * S for _ in range(S)]
    for y in range(S):
        blend = y / max(1, S - 1)
        bg = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * blend) for i in range(4))
        for x in range(S):
            if not in_body(x, y):
                continue
            col = bg
            for x0, x1, y0, y1 in bars:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    col = FG
                    break
            px[y][x] = col

    xor = bytearray()
    for y in range(S - 1, -1, -1):        # BMP 是自底向上
        for x in range(S):
            b, g, rr, a = px[y][x]
            xor += bytes((b, g, rr, a))
    rowbytes = ((S + 31) // 32) * 4
    andmask = b"\x00" * (rowbytes * S)

    hdr = struct.pack("<IiiHHIIiiII", 40, S, S * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    blob = hdr + bytes(xor) + andmask
    icondir = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", S % 256, S % 256, 0, 0, 1, 32, len(blob), 22)
    with open(path, "wb") as f:
        f.write(icondir + entry + blob)
    return path


def build():
    if not os.path.exists(ICON):
        make_icon()
        print(f"已生成图标：{ICON}")

    args = [
        sys.executable, "-m", "PyInstaller",
        os.path.join(HERE, "main.py"),
        "--name", NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", ICON,
        "--paths", HERE,
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PIL",
        "--exclude-module", "PyInstaller",
    ]
    print("运行：\n  " + " \\\n  ".join(args) + "\n")
    rc = subprocess.run(args, cwd=HERE).returncode
    if rc != 0:
        print(f"\n打包失败，返回码 {rc}")
        return rc
    out = os.path.join(HERE, "dist", NAME + ".exe")
    if os.path.exists(out):
        size = os.path.getsize(out) / 1024 / 1024
        print(f"\n✅ 打包成功：{out}  ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
