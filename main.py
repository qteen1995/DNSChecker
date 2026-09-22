# -*- coding: utf-8 -*-
"""入口。打包后即为此程序的启动点。"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _log_crash():
    try:
        d = os.path.join(os.path.expanduser("~"), ".dnschecker")
        os.makedirs(d, exist_ok=True)
        import time
        with open(os.path.join(d, "crash.log"), "a", encoding="utf-8") as f:
            f.write(f"\n===== {time.ctime()} =====\n")
            f.write(traceback.format_exc())
        return os.path.join(d, "crash.log")
    except Exception:
        return None


def main():
    try:
        import ui
        ui.main()
    except Exception:
        path = _log_crash()
        try:
            import tkinter.messagebox as mb
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            mb.showerror("启动失败",
                         f"程序启动时出错。\n\n详细堆栈已写入：\n{path}")
            r.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
