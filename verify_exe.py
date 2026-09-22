# -*- coding: utf-8 -*-
"""验证打包出的 exe 能否正常启动（启动 5 秒后自动关闭）。"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "DNSChecker.exe")
CRASH = os.path.join(os.path.expanduser("~"), ".dnschecker", "crash.log")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

if not os.path.exists(EXE):
    print(f"找不到 {EXE}")
    sys.exit(1)

print(f"exe 大小：{os.path.getsize(EXE) / 1024 / 1024:.1f} MB")

before = os.path.getmtime(CRASH) if os.path.exists(CRASH) else None

print("启动 exe，等 5 秒观察是否稳定驻留…")
p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
time.sleep(5)

rc = p.poll()
if rc is None:
    print("✅ exe 正常运行中，未崩溃。正在关闭…")
    p.terminate()
    try:
        p.wait(timeout=6)
    except Exception:
        p.kill()
    time.sleep(0.5)
else:
    print(f"❌ exe 提前退出，返回码 {rc}")

if os.path.exists(CRASH):
    after = os.path.getmtime(CRASH)
    if before is None or after != before:
        print("\n!! 产生了新的崩溃日志，末尾 40 行：")
        with open(CRASH, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-40:]:
                print("   " + line.rstrip())
        sys.exit(1)
    else:
        print("（crash.log 存在但没有新增内容，是历史记录）")
else:
    print("（没有 crash.log，正常）")

print("\n验证通过。")
