# -*- coding: utf-8 -*-
"""蓝白主题：配色、字体、ttk 样式、矢量小图标、统计卡片、条形图。

所有颜色集中在这里，其他模块只引用常量，不要再写死十六进制。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ------------------------------------------------------------------ 配色
BLUE_900 = "#0B2E5C"
BLUE_800 = "#0C447C"
BLUE_700 = "#12508F"
BLUE_600 = "#185FA5"      # 主色
BLUE_500 = "#2C7BC4"
BLUE_400 = "#378ADD"
BLUE_300 = "#5B9FE0"
BLUE_200 = "#85B7EB"
BLUE_100 = "#B5D4F4"
BLUE_50 = "#E6F1FB"
BLUE_25 = "#F3F8FD"

BG_APP = "#F4F8FC"        # 应用底
BG_CARD = "#FFFFFF"       # 卡片
BG_SIDE = "#FFFFFF"       # 侧栏
BG_HOVER = "#EAF3FC"
BG_SEL = "#D6E8FA"
BG_INPUT = "#FFFFFF"

FG = "#12304F"            # 主文字
FG_SUB = "#5A7796"
FG_MUTE = "#93A9BF"
FG_ON_BLUE = "#FFFFFF"

BORDER = "#D3E2F0"
BORDER_SOFT = "#E7F0F8"

OK = "#1B8A50"
OK_BG = "#E4F4EB"
WARN = "#C77A0A"
WARN_BG = "#FBF0DC"
BAD = "#C93B3B"
BAD_BG = "#FBE9E9"
MUTE = "#8FA6BC"
MUTE_BG = "#EEF3F8"

# ------------------------------------------------------------------ 字体
FONT_NAME = "Microsoft YaHei UI"
FONT = (FONT_NAME, 9)
FONT_SM = (FONT_NAME, 8)
FONT_BOLD = (FONT_NAME, 9, "bold")
FONT_H2 = (FONT_NAME, 11, "bold")
FONT_TITLE = (FONT_NAME, 14, "bold")
FONT_STAT = (FONT_NAME, 19, "bold")
MONO = ("Consolas", 9)
MONO_SM = ("Consolas", 8)

GRADE_COLOR = {"ok": OK, "unstable": WARN, "hijack": BAD, "blocked": WARN,
               "dead": MUTE, "bogus": BAD, "unknown": MUTE}
VERDICT_COLOR = {"clean": OK, "mixed": WARN, "hijack": BAD, "blocked": WARN,
                 "bogus": BAD, "dead": MUTE, "nodata": MUTE}


def setup_style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure(".", font=FONT, background=BG_APP, foreground=FG)

    st.configure("TFrame", background=BG_APP)
    st.configure("Card.TFrame", background=BG_CARD)
    st.configure("Side.TFrame", background=BG_SIDE)

    st.configure("TLabel", background=BG_APP, foreground=FG)
    st.configure("Card.TLabel", background=BG_CARD, foreground=FG)
    st.configure("Sub.TLabel", background=BG_CARD, foreground=FG_SUB, font=FONT_SM)
    st.configure("Muted.TLabel", background=BG_APP, foreground=FG_MUTE, font=FONT_SM)
    st.configure("Title.TLabel", background=BG_APP, foreground=BLUE_800,
                 font=FONT_TITLE)
    st.configure("H2.TLabel", background=BG_APP, foreground=BLUE_700, font=FONT_H2)
    st.configure("CardH2.TLabel", background=BG_CARD, foreground=BLUE_700,
                 font=FONT_H2)

    st.configure("TButton", padding=(10, 5), background=BG_CARD, foreground=FG,
                 borderwidth=1, focusthickness=0, relief="flat")
    st.map("TButton",
           background=[("active", BG_HOVER), ("pressed", BG_SEL),
                       ("disabled", MUTE_BG)],
           foreground=[("disabled", FG_MUTE)],
           bordercolor=[("active", BLUE_300)])

    st.configure("Primary.TButton", background=BLUE_600, foreground=FG_ON_BLUE,
                 borderwidth=0, padding=(15, 6), font=FONT_BOLD)
    st.map("Primary.TButton",
           background=[("active", BLUE_700), ("pressed", BLUE_800),
                       ("disabled", BLUE_200)],
           foreground=[("disabled", "#FFFFFF")])

    st.configure("Ghost.TButton", background=BG_APP, foreground=BLUE_700,
                 borderwidth=0, padding=(8, 5))
    st.map("Ghost.TButton", background=[("active", BLUE_50),
                                        ("disabled", BG_APP)],
           foreground=[("disabled", FG_MUTE)])

    st.configure("CardGhost.TButton", background=BG_CARD, foreground=BLUE_700,
                 borderwidth=0, padding=(8, 5))
    st.map("CardGhost.TButton", background=[("active", BLUE_50)])

    st.configure("Warn.TButton", background=WARN, foreground="#FFFFFF",
                 borderwidth=0, padding=(13, 6), font=FONT_BOLD)
    st.map("Warn.TButton", background=[("active", "#A86508"),
                                       ("disabled", WARN_BG)],
           foreground=[("disabled", "#FFFFFF")])

    st.configure("TEntry", fieldbackground=BG_INPUT, bordercolor=BORDER,
                 lightcolor=BORDER, darkcolor=BORDER, padding=3)
    st.map("TEntry", bordercolor=[("focus", BLUE_400)])

    st.configure("TCombobox", fieldbackground=BG_INPUT, background=BG_INPUT,
                 bordercolor=BORDER, arrowcolor=BLUE_600, padding=3)
    st.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)],
           bordercolor=[("focus", BLUE_400)])

    st.configure("TSpinbox", fieldbackground=BG_INPUT, bordercolor=BORDER,
                 arrowcolor=BLUE_600, padding=3)

    st.configure("TCheckbutton", background=BG_APP, foreground=FG)
    st.map("TCheckbutton", background=[("active", BG_APP)])
    st.configure("Card.TCheckbutton", background=BG_CARD, foreground=FG)
    st.map("Card.TCheckbutton", background=[("active", BG_CARD)])

    st.configure("Blue.Horizontal.TProgressbar", troughcolor=BLUE_50,
                 background=BLUE_500, bordercolor=BLUE_50,
                 lightcolor=BLUE_500, darkcolor=BLUE_500, thickness=15)

    st.configure("Treeview", background=BG_CARD, fieldbackground=BG_CARD,
                 foreground=FG, rowheight=24, bordercolor=BORDER,
                 lightcolor=BORDER, darkcolor=BORDER)
    st.map("Treeview", background=[("selected", BG_SEL)],
           foreground=[("selected", FG)])
    st.configure("Treeview.Heading", background=BLUE_50, foreground=BLUE_800,
                 font=FONT_BOLD, relief="flat", padding=(6, 6))
    st.map("Treeview.Heading", background=[("active", BLUE_100)])

    st.configure("TLabelframe", background=BG_APP, bordercolor=BORDER,
                 relief="solid")
    st.configure("TLabelframe.Label", background=BG_APP, foreground=BLUE_700,
                 font=FONT_BOLD)
    st.configure("Card.TLabelframe", background=BG_CARD, bordercolor=BORDER)
    st.configure("Card.TLabelframe.Label", background=BG_CARD,
                 foreground=BLUE_700, font=FONT_BOLD)

    st.configure("TScrollbar", background=BLUE_100, troughcolor=BG_APP,
                 bordercolor=BG_APP, arrowcolor=BLUE_600, relief="flat")
    st.map("TScrollbar", background=[("active", BLUE_300)])

    st.configure("TPanedwindow", background=BG_APP)
    st.configure("Sash", background=BORDER)

    st.configure("TSeparator", background=BORDER)


# ------------------------------------------------------------------ 矢量图标
def checkbutton(parent, text, variable, bg=BG_CARD, command=None):
    """原生 Checkbutton。

    ttk 在 clam 主题下把指示器画成一个纯色块（蓝=选中 / 白=未选），**没有对勾**，
    用户很容易理解成"禁用/错误标记"。原生控件虽然朴素，但一眼就懂。
    """
    return tk.Checkbutton(
        parent, text=text, variable=variable, command=command,
        background=bg, activebackground=bg,
        foreground=FG, activeforeground=FG,
        selectcolor=BG_CARD, disabledforeground=FG_MUTE,
        font=FONT, relief="flat", bd=0, highlightthickness=0,
        anchor="w", padx=0, pady=0)


def checkbutton_with_icon(parent, text, variable, icon, bg=BG_CARD,
                          command=None, icon_color=BLUE_600, size=15):
    """带矢量图标的勾选框。

    `tk.Checkbutton` 里塞不下 Canvas，所以外面套一层 Frame：左图标、右文字。
    返回的是那个 Frame；需要禁用/改状态时用 `box.check` 拿到里面真正的控件。
    """
    box = tk.Frame(parent, background=bg)
    cv = tk.Canvas(box, width=size, height=size, background=bg,
                   highlightthickness=0, bd=0)
    cv.pack(side="left", padx=(0, 5))
    draw_icon(cv, icon, 0, 0, size, icon_color, width=1.7)
    cb = checkbutton(box, text, variable, bg=bg, command=command)
    cb.pack(side="left")
    box.check = cb
    box.icon = cv
    return box


# 画不出来的图标名会记在这里（测试断言它必须是空的）。
# 见 draw_icon 末尾的 else 分支说明。
UNKNOWN_ICON_KEYS: set = set()


def draw_icon(cv, key, x, y, size, color, width=1.7):
    """在 Canvas 的 (x, y) 处画一个 size×size 的矢量小图标。"""
    s = float(size)
    w = max(1.2, width)

    if key == "speed":
        for i, h in enumerate((0.45, 0.72, 1.0)):
            bx = x + s * (0.15 + i * 0.33)
            cv.create_line(bx, y + s * 0.95, bx, y + s * (0.95 - h * 0.85),
                           fill=color, width=max(2.2, s * 0.16),
                           capstyle="round")

    elif key == "shield":
        cv.create_polygon(
            x + s * 0.5, y + s * 0.04, x + s * 0.94, y + s * 0.24,
            x + s * 0.84, y + s * 0.76, x + s * 0.5, y + s * 0.97,
            x + s * 0.16, y + s * 0.76, x + s * 0.06, y + s * 0.24,
            outline=color, fill="", width=w, joinstyle="round")
        cv.create_line(x + s * 0.32, y + s * 0.47, x + s * 0.45, y + s * 0.62,
                       x + s * 0.70, y + s * 0.32, fill=color, width=w,
                       capstyle="round", joinstyle="round")

    elif key == "hosts":
        cv.create_polygon(
            x + s * 0.14, y + s * 0.04, x + s * 0.64, y + s * 0.04,
            x + s * 0.87, y + s * 0.26, x + s * 0.87, y + s * 0.96,
            x + s * 0.14, y + s * 0.96,
            outline=color, fill="", width=w, joinstyle="round")
        cv.create_line(x + s * 0.64, y + s * 0.04, x + s * 0.64, y + s * 0.26,
                       x + s * 0.87, y + s * 0.26, fill=color, width=w * 0.8)
        for i in range(2):
            ly = y + s * (0.50 + i * 0.18)
            cv.create_line(x + s * 0.30, ly, x + s * 0.71, ly,
                           fill=color, width=1.3, capstyle="round")

    elif key == "log":
        for i in range(4):
            ly = y + s * (0.13 + i * 0.25)
            ln = 0.92 if i % 2 == 0 else 0.58
            cv.create_line(x + s * 0.06, ly, x + s * (0.06 + ln), ly,
                           fill=color, width=w, capstyle="round")

    elif key == "dns":
        cv.create_oval(x + s * 0.08, y + s * 0.08, x + s * 0.92, y + s * 0.92,
                       outline=color, fill="", width=w)
        cv.create_oval(x + s * 0.36, y + s * 0.36, x + s * 0.64, y + s * 0.64,
                       outline=color, fill="", width=w * 0.85)

    elif key == "filter":
        cv.create_polygon(
            x + s * 0.08, y + s * 0.16, x + s * 0.92, y + s * 0.16,
            x + s * 0.62, y + s * 0.50, x + s * 0.62, y + s * 0.92,
            x + s * 0.38, y + s * 0.92, x + s * 0.38, y + s * 0.50,
            outline=color, fill="", width=w, joinstyle="round")

    elif key == "globe":
        cv.create_oval(x + s * 0.08, y + s * 0.08, x + s * 0.92, y + s * 0.92,
                       outline=color, fill="", width=w)
        cv.create_oval(x + s * 0.34, y + s * 0.08, x + s * 0.66, y + s * 0.92,
                       outline=color, fill="", width=w * 0.75)
        cv.create_line(x + s * 0.08, y + s * 0.5, x + s * 0.92, y + s * 0.5,
                       fill=color, width=w * 0.75)

    elif key == "layers":
        cv.create_polygon(x + s * 0.5, y + s * 0.08, x + s * 0.94, y + s * 0.33,
                          x + s * 0.5, y + s * 0.58, x + s * 0.06, y + s * 0.33,
                          outline=color, fill="", width=w, joinstyle="round")
        cv.create_polygon(x + s * 0.5, y + s * 0.42, x + s * 0.94, y + s * 0.67,
                          x + s * 0.5, y + s * 0.92, x + s * 0.06, y + s * 0.67,
                          outline=color, fill="", width=w, joinstyle="round")

    elif key == "target":
        cv.create_oval(x + s * 0.06, y + s * 0.06, x + s * 0.94, y + s * 0.94,
                       outline=color, fill="", width=w)
        cv.create_oval(x + s * 0.32, y + s * 0.32, x + s * 0.68, y + s * 0.68,
                       outline=color, fill="", width=w * 0.8)
        cv.create_oval(x + s * 0.45, y + s * 0.45, x + s * 0.55, y + s * 0.55,
                       outline=color, fill=color, width=0)

    elif key == "export":
        cv.create_line(x + s * 0.5, y + s * 0.08, x + s * 0.5, y + s * 0.62,
                       fill=color, width=w * 1.1, capstyle="round")
        cv.create_polygon(x + s * 0.30, y + s * 0.46, x + s * 0.5, y + s * 0.68,
                          x + s * 0.70, y + s * 0.46,
                          outline=color, fill="", width=w, joinstyle="round")
        cv.create_line(x + s * 0.14, y + s * 0.88, x + s * 0.86, y + s * 0.88,
                       fill=color, width=w * 1.1, capstyle="round")

    elif key == "clock":
        cv.create_oval(x + s * 0.08, y + s * 0.08, x + s * 0.92, y + s * 0.92,
                       outline=color, fill="", width=w)
        cv.create_line(x + s * 0.5, y + s * 0.28, x + s * 0.5, y + s * 0.52,
                       x + s * 0.68, y + s * 0.64, fill=color, width=w * 0.9,
                       capstyle="round", joinstyle="round")

    elif key == "play":
        cv.create_polygon(x + s * 0.26, y + s * 0.10, x + s * 0.86, y + s * 0.5,
                          x + s * 0.26, y + s * 0.90,
                          outline=color, fill=color, width=w, joinstyle="round")

    elif key == "stop":
        cv.create_rectangle(x + s * 0.20, y + s * 0.20, x + s * 0.80, y + s * 0.80,
                            outline=color, fill=color, width=w)

    elif key == "list":
        for i in range(3):
            ly = y + s * (0.20 + i * 0.30)
            cv.create_oval(x + s * 0.06, ly - s * 0.06, x + s * 0.18, ly + s * 0.06,
                           outline=color, fill=color, width=0)
            cv.create_line(x + s * 0.32, ly, x + s * 0.94, ly,
                           fill=color, width=w, capstyle="round")

    elif key == "chevron_down" or key == "chevron_up":
        up = key == "chevron_up"
        ya, yb = (0.66, 0.34) if up else (0.36, 0.66)
        cv.create_line(x + s * 0.18, y + s * ya, x + s * 0.5, y + s * yb,
                       x + s * 0.82, y + s * ya, fill=color, width=w * 1.15,
                       capstyle="round", joinstyle="round")

    elif key == "tcp":
        # 两条竖线（协议栈两层）+ 双向箭头，表示「有连接、要握手」
        cv.create_line(x + s * 0.12, y + s * 0.10, x + s * 0.12, y + s * 0.90,
                       fill=color, width=w, capstyle="round")
        cv.create_line(x + s * 0.88, y + s * 0.10, x + s * 0.88, y + s * 0.90,
                       fill=color, width=w, capstyle="round")
        cv.create_line(x + s * 0.28, y + s * 0.34, x + s * 0.72, y + s * 0.34,
                       fill=color, width=w * 0.9)
        cv.create_line(x + s * 0.28, y + s * 0.66, x + s * 0.72, y + s * 0.66,
                       fill=color, width=w * 0.9)
        cv.create_polygon(x + s * 0.40, y + s * 0.22, x + s * 0.60, y + s * 0.34,
                          x + s * 0.40, y + s * 0.46, outline=color, fill=color,
                          width=w * 0.7, joinstyle="round")
        cv.create_polygon(x + s * 0.60, y + s * 0.56, x + s * 0.40, y + s * 0.68,
                          x + s * 0.60, y + s * 0.80, outline=color, fill=color,
                          width=w * 0.7, joinstyle="round")

    else:
        # 未知图标名：画个实心方块顶上，并记进 UNKNOWN_ICON_KEYS。
        #
        # 静默「什么都不画」是最糟的失败模式 —— 界面上少一个图标，代码里不留
        # 任何痕迹，谁也发现不了。侧栏「污染检测」就这么白了两轮：NavItem 拿
        # **页面 key**（"pollute"）当图标名用，而 draw_icon 里只有 "shield"、
        # 没有 "pollute"，于是那一格的画布全空且无人报错。另外三项的页面 key
        # 恰好等于图标名，蒙对了，所以只有污染检测露馅。
        UNKNOWN_ICON_KEYS.add(str(key))
        cv.create_rectangle(x + s * 0.18, y + s * 0.18,
                            x + s * 0.82, y + s * 0.82,
                            outline=color, fill=color, width=w)


ICON_KEYS = ("speed", "shield", "hosts", "log", "dns", "filter", "globe",
             "layers", "target", "export", "clock", "play", "stop", "list",
             "chevron_up", "chevron_down", "tcp")


# ------------------------------------------------------------------ 小组件
class IconButton(tk.Frame):
    """带矢量图标的按钮（自绘：左图标 + 右文字）。

    ttk.Button 里塞不进 Canvas，而把 `▶` `◎` `↓` 这类字符当图标，在微软雅黑下
    又歪又糊、字重也对不上。所以干脆自己画，三态（悬停 / 按下 / 禁用）都管。

    图标保持**细线轮廓**风格：和侧栏导航、勾选框上的图标是同一套线条，
    整体才统一。（试过给图标垫一块圆角色块，看着很块状、反而更丑，已回退。）

    variant:
        primary —— 蓝底白字，页面主操作用（开始测速、开始检测）
        default —— 白底描边，次级操作用
        ghost   —— 无边框，卡片里的收起 / 展开用
    """

    def __init__(self, master, text, icon, command=None, variant="default",
                 bg=BG_APP, size=15, hpad=(11, 13), vpad=5):
        super().__init__(master, background=bg)
        self._cmd = command
        self._icon = icon
        self._size = size
        self._variant = variant
        self._outer = bg
        self._enabled = True
        self._hover = False
        self._pressed = False

        self.body = tk.Frame(self, highlightthickness=1, bd=0)
        self.body.pack()
        self.cv = tk.Canvas(self.body, width=size, height=size, bd=0,
                            highlightthickness=0)
        self.cv.pack(side="left", padx=(hpad[0], 7), pady=vpad)
        self.lbl = tk.Label(self.body, text=text, anchor="w",
                            font=FONT_BOLD if variant == "primary" else FONT)
        self.lbl.pack(side="left", padx=(0, hpad[1]), pady=vpad)

        for w in (self, self.body, self.cv, self.lbl):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._press)
            w.bind("<ButtonRelease-1>", self._release)
        self._paint()

    # ----------------------------------------------------------------
    def _enter(self, _e=None):
        self._hover = True
        self._paint()

    def _leave(self, _e=None):
        self._hover = self._pressed = False
        self._paint()

    def _press(self, _e=None):
        if self._enabled:
            self._pressed = True
            self._paint()

    def _release(self, _e=None):
        if not self._enabled:
            return
        fire = self._pressed
        self._pressed = False
        self._paint()
        if fire and self._cmd:
            self._cmd()

    def set_state(self, state):
        """'normal' / 'disabled'，沿用 ttk 的叫法。"""
        self._enabled = (state != "disabled")
        self._paint()

    def set_text(self, text):
        self.lbl.configure(text=text)

    def set_icon(self, icon):
        self._icon = icon
        self._paint()

    # ----------------------------------------------------------------
    def _palette(self):
        """-> (底色, 文字色, 图标色, 边框色)"""
        v = self._variant
        if not self._enabled:
            return MUTE_BG, FG_MUTE, MUTE, BORDER
        if v == "primary":
            if self._pressed:
                return BLUE_800, FG_ON_BLUE, FG_ON_BLUE, BLUE_800
            if self._hover:
                return BLUE_700, FG_ON_BLUE, FG_ON_BLUE, BLUE_700
            return BLUE_600, FG_ON_BLUE, FG_ON_BLUE, BLUE_600
        if v == "ghost":
            fill = BG_SEL if self._pressed else (
                BLUE_50 if self._hover else self._outer)
            return fill, BLUE_700, BLUE_600, fill
        fill = BG_SEL if self._pressed else (
            BG_HOVER if self._hover else BG_CARD)
        return fill, FG, BLUE_600, (BLUE_300 if self._hover else BORDER)

    def _paint(self):
        fill, fg, ic, border = self._palette()
        self.configure(background=self._outer)
        self.body.configure(background=fill, highlightbackground=border,
                            highlightcolor=border)
        self.cv.configure(background=fill)
        self.lbl.configure(background=fill, foreground=fg)
        cur = "hand2" if self._enabled else "arrow"
        for w in (self, self.body, self.cv, self.lbl):
            try:
                w.configure(cursor=cur)
            except Exception:
                pass
        self.cv.delete("all")
        draw_icon(self.cv, self._icon, 0, 0, self._size, ic, width=1.7)


class StatCard(tk.Frame):
    """统计卡片：顶部一条彩色横条 + 标签 + 大数字 + 说明。"""

    def __init__(self, master, label, value="—", accent=BLUE_600, sub="",
                 width=150):
        super().__init__(master, background=BG_CARD, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=BORDER)
        self.bar = tk.Frame(self, background=accent, height=3)
        self.bar.pack(fill="x")
        inner = tk.Frame(self, background=BG_CARD)
        inner.pack(fill="both", expand=True, padx=12, pady=(7, 9))
        tk.Label(inner, text=label, font=FONT_SM, fg=FG_SUB, bg=BG_CARD,
                 anchor="w").pack(anchor="w", fill="x")
        self.val = tk.Label(inner, text=value, font=FONT_STAT, fg=accent,
                            bg=BG_CARD, anchor="w")
        self.val.pack(anchor="w", fill="x")
        self.sub = tk.Label(inner, text=sub or " ", font=FONT_SM, fg=FG_MUTE,
                            bg=BG_CARD, anchor="w")
        self.sub.pack(anchor="w", fill="x")

    def set(self, value, sub=None, accent=None):
        self.val.configure(text=str(value))
        if accent:
            self.val.configure(fg=accent)
            self.bar.configure(background=accent)
        if sub is not None:
            self.sub.configure(text=sub or " ")


class BarChart(tk.Canvas):
    """横向条形图：适合展示 Top-N 延迟排行。"""

    def __init__(self, master, height=150, label_w=170, value_w=80, **kw):
        super().__init__(master, height=height, background=BG_CARD,
                         highlightthickness=0, bd=0, **kw)
        self.items = []
        self.label_w = label_w
        self.value_w = value_w
        self._empty = "暂无数据 — 点「开始测速」"
        self.bind("<Configure>", lambda e: self.redraw())

    def set_items(self, items, empty=None):
        self.items = list(items)
        if empty is not None:
            self._empty = empty
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 80:
            return
        if not self.items:
            self.create_text(w // 2, h // 2, text=self._empty,
                             fill=FG_MUTE, font=FONT)
            return

        n = len(self.items)
        pad_t = 4
        row_h = max(13.0, min(26.0, (h - pad_t * 2) / max(1, n)))
        vmax = max((it[1] for it in self.items), default=1) or 1
        bar_x = self.label_w
        # 给右侧数值留足余量，否则贴到窗口边缘会被裁掉
        bar_w = max(30, w - self.label_w - self.value_w - 16)

        for i, (label, value, color) in enumerate(self.items):
            cy = pad_t + row_h * i + row_h / 2
            self.create_text(6, cy, text=_ellipsis(label, 22), anchor="w",
                             fill=FG, font=FONT)
            frac = max(0.012, min(1.0, value / vmax))
            self.create_rectangle(bar_x, cy - row_h * 0.28,
                                  bar_x + bar_w, cy + row_h * 0.28,
                                  fill=BLUE_50, outline="")
            self.create_rectangle(bar_x, cy - row_h * 0.28,
                                  bar_x + bar_w * frac, cy + row_h * 0.28,
                                  fill=color, outline="")
            self.create_text(w - 10, cy, text=f"{value:.1f} ms", anchor="e",
                             fill=FG_SUB, font=FONT_SM)


class StackBar(tk.Canvas):
    """堆叠比例条：一眼看出「有效 / 异常 / 不可达」各自占多少。"""

    def __init__(self, master, height=22, **kw):
        super().__init__(master, height=height, background=BG_CARD,
                         highlightthickness=0, bd=0, **kw)
        self.segments = []          # [(value, color, label)]
        self.bind("<Configure>", lambda e: self.redraw())

    def set_segments(self, segments):
        self.segments = [s for s in segments if s[0] > 0]
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 40:
            return
        total = sum(s[0] for s in self.segments)
        r = h / 2
        if total <= 0:
            self.create_rectangle(0, 2, w, h - 2, fill=MUTE_BG, outline="")
            self.create_text(w // 2, h // 2, text="无数据", fill=FG_MUTE,
                             font=FONT_SM)
            return
        x = 0.0
        for i, (val, color, _label) in enumerate(self.segments):
            seg = w * val / total
            if i == len(self.segments) - 1:
                seg = w - x
            _rounded_bar(self, x, 2, x + seg, h - 2, color, r)
            x += seg


def _rounded_bar(cv, x0, y0, x1, y1, color, r):
    """画一条可选圆角的横条（只在最左/最右圆角）。"""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    if x1 - x0 < 2:
        return
    cv.create_rectangle(x0 + (r if r > 0 else 0), y0, x1, y1,
                        fill=color, outline="")
    if r > 0:
        cv.create_oval(x0, y0, x0 + 2 * r, y1, fill=color, outline="")


def _ellipsis(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


class NavItem(tk.Frame):
    """侧栏导航条目：自绘 hover / 选中态，左侧一条高亮指示条。"""

    def __init__(self, master, key, text, icon, on_click, width=172):
        super().__init__(master, background=BG_SIDE, height=44,
                         highlightthickness=0)
        self.pack_propagate(False)
        self.configure(width=width)
        self.key = key
        self.icon_key = icon          # ★ 图标名，和页面 key 不是一回事
        self.on_click = on_click
        self.selected = False
        self._hover = False

        self.indicator = tk.Frame(self, background=BG_SIDE, width=3)
        self.indicator.pack(side="left", fill="y")

        body = tk.Frame(self, background=BG_SIDE)
        body.pack(side="left", fill="both", expand=True)

        self.icon = tk.Canvas(body, width=20, height=20, background=BG_SIDE,
                              highlightthickness=0, bd=0)
        self.icon.pack(side="left", padx=(12, 9))
        self.text = tk.Label(body, text=text, font=FONT, fg=FG_SUB,
                             bg=BG_SIDE, anchor="w")
        self.text.pack(side="left", fill="x", expand=True)

        for wdg in (self, body, self.icon, self.text):
            wdg.bind("<Enter>", self._enter)
            wdg.bind("<Leave>", self._leave)
            wdg.bind("<Button-1>", self._click)
            try:
                wdg.configure(cursor="hand2")
            except Exception:
                pass
        self._paint()

    def _enter(self, _e=None):
        self._hover = True
        self._paint()

    def _leave(self, _e=None):
        self._hover = False
        self._paint()

    def _click(self, _e=None):
        if self.on_click:
            self.on_click(self.key)

    def set_selected(self, flag):
        self.selected = flag
        self._paint()

    def _paint(self):
        if self.selected:
            bg, fg, ic = BG_SEL, BLUE_800, BLUE_600
        elif self._hover:
            bg, fg, ic = BG_HOVER, BLUE_700, BLUE_500
        else:
            bg, fg, ic = BG_SIDE, FG_SUB, BLUE_400
        for wdg in (self, ):
            wdg.configure(background=bg)
        for wdg in self.winfo_children():
            wdg.configure(background=bg)
            for sub in wdg.winfo_children():
                try:
                    sub.configure(background=bg)
                except Exception:
                    pass
        self.indicator.configure(background=BLUE_600 if self.selected else bg)
        self.icon.configure(background=bg)
        self.text.configure(background=bg, fg=fg,
                            font=FONT_BOLD if self.selected else FONT)
        self.icon.delete("all")
        draw_icon(self.icon, self.icon_key, 1, 1, 18, ic, width=1.8)


def attach_copy_menu(widget, rows_provider, extra=None, trigger="<Button-3>"):
    """给 Treeview 挂右键菜单：复制当前行各列 + 自定义项。

    rows_provider() -> (title, columns, values) 或 None
    trigger: 触发事件。默认右键；如果所在表格自己要用右键做「一步复制」，
             可以改成 "<Control-Button-3>"，把完整菜单挪到 Ctrl+右键。
    """
    menu = tk.Menu(widget, tearoff=0, font=FONT)

    def do_copy(text):
        widget.clipboard_clear()
        widget.clipboard_append(text)
        try:
            widget.event_generate("<<CopyDone>>")
        except Exception:
            pass

    def popup(event):
        iid = widget.identify_row(event.y)
        if iid:
            widget.selection_set(iid)
            widget.focus(iid)
        info = rows_provider()
        menu.delete(0, "end")
        if not info:
            menu.add_command(label="（未选中内容）", state="disabled")
        else:
            title, columns, values = info
            menu.add_command(label=f"复制：{title}", state="disabled")
            menu.add_separator()
            for col, val in zip(columns, values):
                if not val or val == "-":
                    continue
                menu.add_command(
                    label=f"复制 {col}：{_ellipsis(val, 42)}",
                    command=lambda v=val: do_copy(v))
            menu.add_separator()
            menu.add_command(label="复制整行（制表符分隔）",
                             command=lambda: do_copy("\t".join(str(v) for v in values)))
            only = [v for v in values if v and v != "-"]
            if only:
                menu.add_command(label="复制整行（空格分隔）",
                                 command=lambda: do_copy(" ".join(str(v) for v in only)))
        if extra:
            items = extra()
            if items:
                menu.add_separator()
                for label, fn in items:
                    menu.add_command(label=label, command=fn)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind(trigger, popup)
    return menu
