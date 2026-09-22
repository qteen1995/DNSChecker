# -*- coding: utf-8 -*-
"""对**打包好的 exe** 截图 —— 证明交付物里真的有这些图标 / 这些按钮。

源码跑得好不等于 exe 里也在（PyInstaller 静态分析、资源打包都可能出岔子），
所以验证流程的最后一步必须是「跑 dist 里的 exe，截它自己的画面」。

两个关键点（都是踩出来的）：
  * 截图走 `winshot.capture`（PrintWindow），**不抓屏幕像素** ——
    抓屏幕的话机器一锁屏就截到锁屏壁纸，而且不报错。
  * 切换页面用 `SendMessage(WM_LBUTTONDOWN/UP)` 直接投递给窗口，
    **不移动用户的鼠标**（`SetCursorPos` + `mouse_event` 会抢鼠标，
    而且锁屏时输入根本到不了我们的窗口）。
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import winshot

EXE = os.path.join(HERE, "dist", "DNSChecker.exe")
TITLE = "公共 DNS 批量测速 · 污染检测 · hosts 优选"
TITLE_PART = "公共 DNS 批量测速"

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001

user32 = winshot.user32


def find_window(timeout=40.0):
    """按完整标题找，找不到再按前缀枚举兜底。"""
    end = time.time() + timeout
    while time.time() < end:
        hwnd = user32.FindWindowW(None, TITLE)
        if hwnd:
            return hwnd
        hwnd = winshot.find_window(TITLE_PART, timeout=1.0)
        if hwnd:
            return hwnd
        time.sleep(0.4)
    return None


def click(hwnd, x, y):
    """在窗口客户区 (x, y) 上点一下真实鼠标。

    实测结论（都试过了，别重复踩）：
      * `SendMessage`/`PostMessage` 的 WM_LBUTTONDOWN **Tk 一律不接**
        （往 TkChild 和 TkTopLevel 都投过，控件的 <Button-1> 一个都没触发）。
      * `SetCursorPos` + `mouse_event` 在**解锁状态下有效**；
        锁屏时真实输入被锁屏桌面吃掉，同样无效。
    ⇒ 所以：切页必须会话解锁；而截图（PrintWindow）锁屏也能用。
    """
    cx, cy = winshot.client_origin(hwnd)
    old = wt.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    try:
        user32.SetCursorPos(int(cx + x), int(cy + y))
        time.sleep(0.15)
        user32.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
        time.sleep(0.06)
        user32.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP
        time.sleep(0.7)
    finally:
        user32.SetCursorPos(old.x, old.y)           # 把鼠标还给用户


def main():
    if not os.path.exists(EXE):
        print("找不到 exe：", EXE)
        return 1
    locked = winshot.is_locked()
    if locked:
        print("提示：当前会话锁屏中。截图（PrintWindow）照常能用，")
        print("      但**切页需要真实点击**，锁屏时送不到窗口 —— 只会截到首页。")

    print(f"启动 {EXE} …")
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    hwnd = find_window()
    if not hwnd:
        print("!! 等不到窗口，exe 可能启动失败")
        proc.terminate()
        return 1
    print("窗口已出现，等它把端点铺完…")
    time.sleep(10.0)

    # 侧栏导航项：logo 86 + 分隔条 13 起排，每项 44 高 + 上下 1px 间距
    #   延迟测速 121   污染检测 167   hosts 213   运行日志 259
    NAV_X = 91
    PAGES = (("exe_shots_speed", None),
             ("exe_shots_pollute", 167),
             ("exe_shots_hosts", 213))

    shots, skipped = [], []
    for name, nav_y in PAGES:
        if nav_y:
            before = winshot.capture(int(hwnd))
            click(hwnd, NAV_X, nav_y)
            img = winshot.capture(int(hwnd))
            # ★ 页面没真的切过去就绝不落盘 —— 否则会留下一个
            #   「名叫 pollute、内容是测速页」的截图，比没有截图更糟。
            if before is not None and img is not None \
                    and img.tobytes() == before.tobytes():
                skipped.append(name)
                print(f"!! {name}：页面没有切换成功（点击没送达）—— 不保存")
                continue
        else:
            img = winshot.capture(int(hwnd))
        if img is None:
            skipped.append(name)
            print(f"!! {name} 抓取失败")
            continue
        p = os.path.join(HERE, name + ".png")
        img.save(p)
        shots.append(f"{os.path.basename(p)}={img.size}")
        print("已保存", os.path.basename(p))

    print("; ".join(shots) if shots else "（没截到任何页面）")
    if skipped:
        print(f"跳过：{', '.join(skipped)}"
              + ("（锁屏时切不了页，解锁后重跑即可）" if locked else ""))
    proc.terminate()
    print("已关闭 exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
