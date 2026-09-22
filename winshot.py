# -*- coding: utf-8 -*-
"""抓窗口内容 —— 不依赖「窗口可见 / 屏幕没锁 / 鼠标别动」。

为什么不用 `PIL.ImageGrab`：它抓的是**屏幕像素**，于是
  * 机器锁屏时抓到的是锁屏壁纸；
  * 窗口被别的窗口遮住时抓到的是遮挡它的那个；
  * 还得先把窗口 `SetForegroundWindow` + 移动鼠标去点按钮。
上一轮就踩了：锁屏状态下跑截图，把好端端的演示图覆盖成了壁纸，
而且**不报错**，看文件名完全正常。

改用 `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)`：它问 DWM 要窗口自己的
重定向表面，所以窗口被遮挡、甚至在锁屏后面也照样能拿到内容。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Optional

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

PW_RENDERFULLCONTENT = 0x00000002
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG),
                ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def capture(hwnd: int, retries: int = 3) -> Optional["object"]:
    """抓指定窗口的内容，返回 PIL Image（失败返回 None）。

    连续抓几次是因为窗口刚创建时第一次 PrintWindow 常常是空白 ——
    重定向表面还没画上东西。
    """
    from PIL import Image

    r = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None

    hdc_win = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    old = gdi32.SelectObject(hdc_mem, hbmp)

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = w
    info.bmiHeader.biHeight = -h          # 负数 = 自顶向下
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0

    img = None
    try:
        for _ in range(max(1, retries)):
            user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
            buf = ctypes.create_string_buffer(w * h * 4)
            if not gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf,
                                   ctypes.byref(info), DIB_RGB_COLORS):
                continue
            img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA",
                                   0, 1).convert("RGB")
            # 全黑基本就是没画上，再试一次
            if img.getextrema() != ((0, 0), (0, 0), (0, 0)):
                break
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
    return img


def find_window(title_part: str, timeout: float = 40.0) -> Optional[int]:
    """按标题片段找一个可见窗口（含子串匹配兜底）。"""
    import time
    end = time.time() + timeout
    while time.time() < end:
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
        def cb(h, _l):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, buf, 512)
            if title_part in buf.value and user32.IsWindowVisible(h):
                found.append(h)
            return True

        user32.EnumWindows(cb, 0)
        if found:
            return found[0]
        time.sleep(0.4)
    return None


def client_origin(hwnd: int):
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def is_locked() -> bool:
    """当前会话是否锁屏（锁屏时前台窗口是锁屏界面，不是我们的窗口）。"""
    h = user32.GetForegroundWindow()
    if not h:
        return True
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, buf, 512)
    return "锁屏" in buf.value or "Lock" in buf.value


def click(hwnd: int, x: int, y: int) -> None:
    """在窗口客户区坐标 (x, y) 上点一下鼠标。

    注意：这会真的移动用户的鼠标 —— 只在确实需要交互时用。
    """
    import time
    cx, cy = client_origin(hwnd)
    user32.SetCursorPos(int(cx + x), int(cy + y))
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP
