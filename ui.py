# -*- coding: utf-8 -*-
"""主窗口：竖排侧栏导航 + 顶栏参数 + 状态栏。"""
from __future__ import annotations

import csv
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import dnsdata
import hostsmgr
import theme as th

APP_TITLE = "公共 DNS 批量测速 · 污染检测 · hosts 优选"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".dnschecker")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

PAGES = [
    ("speed", "延迟测速", "speed"),
    ("pollute", "污染检测", "shield"),
    ("hosts", "hosts 优选", "hosts"),
    ("log", "运行日志", "log"),
]


def _center(win, parent):
    win.update_idletasks()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    w, h = win.winfo_width(), win.winfo_height()
    win.geometry(f"+{max(0, px + (pw - w) // 2)}+{max(0, py + (ph - h) // 3)}")


class LogTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, background=th.BG_APP)
        self.app = app
        bar = tk.Frame(self, background=th.BG_APP)
        bar.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(bar, text="运行日志", font=th.FONT_TITLE, fg=th.BLUE_800,
                 bg=th.BG_APP).pack(side="left")
        ttk.Button(bar, text="复制全部", command=self._copy).pack(side="right")
        ttk.Button(bar, text="清空", command=self.clear).pack(side="right", padx=6)
        wrap = tk.Frame(self, background=th.BG_CARD, highlightthickness=1,
                        highlightbackground=th.BORDER)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt = tk.Text(wrap, wrap="word", font=th.MONO, background=th.BG_CARD,
                           foreground=th.FG, relief="flat", borderwidth=0,
                           highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set, state="disabled")
        self.txt.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=10)
        sb.pack(side="right", fill="y", pady=10, padx=(0, 12))

    def write(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.txt.configure(state="normal")
        self.txt.insert("end", f"[{ts}] {msg}\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def clear(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    def _copy(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(self.txt.get("1.0", "end"))
        self.write("日志已复制到剪贴板。")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1380x900")
        # 最小宽度按「顶栏装得下」定：顶栏实测需要 1044px，而页面可用宽度
        # ≈ 窗口宽 − 206（侧栏 182 + 左右边距 24）。所以下限取 1260，留十几像素余量。
        self.minsize(1260, 760)
        self.configure(background=th.BG_APP)
        th.setup_style(self)

        cfg = self._load_config()
        self.entries = cfg.get("entries") or [dict(e) for e in dnsdata.DEFAULT_ENTRIES]
        self.domains = cfg.get("domains") or [d["domain"] for d in dnsdata.DEFAULT_DOMAINS]
        self.settings = cfg.get("settings") or {}

        self.speed_results = {}
        self.report = None
        self.cancel_evt = threading.Event()
        self.msg_q = queue.Queue()
        self.worker = None
        self.pollute_worker = None
        self.current_page = None
        self.pages = {}
        self._visual_tick = 0

        from ui_hosts import HostsTab
        from ui_pollute import PolluteTab
        from ui_speed import SpeedTab

        self._build_layout()
        self.tab_speed = SpeedTab(self.page_host, self)
        self.tab_pollute = PolluteTab(self.page_host, self)
        self.tab_hosts = HostsTab(self.page_host, self)
        self.tab_log = LogTab(self.page_host, self)

        for key, obj in (("speed", self.tab_speed), ("pollute", self.tab_pollute),
                         ("hosts", self.tab_hosts), ("log", self.tab_log)):
            obj.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = obj
        self.page_host.rowconfigure(0, weight=1)
        self.page_host.columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_toolbar()
        self._build_statusbar()
        self.show_page("speed")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._poll)
        self.after(120, self.tab_speed.prefill)
        self.after(700, self.tab_hosts.auto_env_check)

        n_eps = len(list(dnsdata.iter_endpoints(self.entries)))
        self.log(f"已加载 {len(self.entries)} 个 DNS 服务，共 {n_eps} 个可测端点。")
        self.log("通道按「地址族 × 传输方式」组合：IPv4/IPv6 决定走哪个地址族，"
                 "UDP/TCP 决定传输层，两者相乘就是实际测的端点。"
                 "同一台服务器 UDP 与 TCP 成绩差得离谱时，多半是 UDP 被限速或阻断了。")
        self.log(f"目标域名 {len(self.domains)} 个。")
        if not hostsmgr.is_admin():
            self.log("提示：当前不是管理员权限，hosts 写入不可用（可用「以管理员重启」）。")

    # ---------------------------------------------------------------- 布局
    def center_window(self, win):
        _center(win, self)

    def _build_layout(self):
        outer = tk.Frame(self, background=th.BG_APP)
        outer.pack(fill="both", expand=True)

        self.side = tk.Frame(outer, background=th.BG_SIDE, width=182)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)

        right = tk.Frame(outer, background=th.BG_APP)
        right.pack(side="left", fill="both", expand=True)

        self.head = tk.Frame(right, background=th.BG_APP)
        self.head.pack(fill="x")
        self.page_host = tk.Frame(right, background=th.BG_APP)
        self.page_host.pack(fill="both", expand=True, padx=10)
        self.foot = tk.Frame(right, background=th.BG_APP)
        self.foot.pack(fill="x", padx=10, pady=(2, 9))

    def _build_sidebar(self):
        logo = tk.Frame(self.side, background=th.BG_SIDE, height=86)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        cv = tk.Canvas(logo, width=34, height=34, background=th.BG_SIDE,
                       highlightthickness=0, bd=0)
        cv.pack(side="left", padx=(16, 10), pady=(20, 0))
        th.draw_icon(cv, "dns", 2, 2, 30, th.BLUE_600, width=2.2)
        txt = tk.Frame(logo, background=th.BG_SIDE)
        txt.pack(side="left", pady=(20, 0))
        tk.Label(txt, text="DNS 工具箱", font=(th.FONT_NAME, 12, "bold"),
                 fg=th.BLUE_800, bg=th.BG_SIDE).pack(anchor="w")
        tk.Label(txt, text="测速 · 污染检测 · 优选", font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_SIDE).pack(anchor="w")

        tk.Frame(self.side, background=th.BORDER_SOFT, height=1).pack(
            fill="x", padx=12, pady=(4, 8))

        self.nav_items = {}
        for key, label, icon in PAGES:
            item = th.NavItem(self.side, key, label, icon, self.show_page)
            item.pack(fill="x", pady=1)
            self.nav_items[key] = item

        bottom = tk.Frame(self.side, background=th.BG_SIDE)
        bottom.pack(side="bottom", fill="x", pady=(0, 14))
        tk.Frame(bottom, background=th.BORDER_SOFT, height=1).pack(
            fill="x", padx=12, pady=(0, 10))
        self.var_side_status = tk.StringVar(value="就绪")
        tk.Label(bottom, textvariable=self.var_side_status, font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_SIDE, wraplength=150,
                 justify="left").pack(anchor="w", padx=16)

    def _build_toolbar(self):
        bar = tk.Frame(self.head, background=th.BG_CARD, highlightthickness=1,
                       highlightbackground=th.BORDER)
        bar.pack(fill="x", pady=(10, 6))
        self.toolbar_bar = bar

        row = tk.Frame(bar, background=th.BG_CARD)
        row.pack(fill="x", padx=12, pady=9)
        self.toolbar_row = row

        tk.Label(row, text="通道", font=th.FONT_BOLD, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(side="left", padx=(0, 6))
        # 地址族（IPv4/IPv6）× 传输方式（UDP/TCP）的 2×2 组合：
        # 真正测哪些端点 = 两者相乘（IPv4+UDP → udp4，IPv6+TCP → tcp6 …）。
        # 分开勾的好处是「只看 TCP 不看 UDP」「只看 IPv4 不看 IPv6」都能一次点到位。
        self.var_v4 = tk.BooleanVar(value=True)
        self.var_v6 = tk.BooleanVar(value=True)
        self.var_udp = tk.BooleanVar(value=True)
        self.var_tcp = tk.BooleanVar(value=True)
        self.var_dot = tk.BooleanVar(value=True)
        self.var_doh = tk.BooleanVar(value=True)
        groups = (((self.var_v4, "IPv4"), (self.var_v6, "IPv6")),
                  ((self.var_udp, "UDP"), (self.var_tcp, "TCP")),
                  ((self.var_dot, "DoT"), (self.var_doh, "DoH")))
        for gi, grp in enumerate(groups):
            if gi:
                tk.Frame(row, background=th.BORDER_SOFT, width=1,
                         height=15).pack(side="left", padx=5)
            for var, txt in grp:
                var.trace_add("write", lambda *_: self._refresh_kind_hint())
                th.checkbutton(row, txt, var, bg=th.BG_CARD).pack(
                    side="left", padx=3)
        self.var_kind_hint = tk.StringVar(value="")
        tk.Label(row, textvariable=self.var_kind_hint, font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_CARD).pack(side="left", padx=(4, 0))

        tk.Frame(row, background=th.BORDER_SOFT, width=1, height=22).pack(
            side="left", padx=7, fill="y")

        tk.Label(row, text="并发", font=th.FONT, fg=th.FG_SUB,
                 bg=th.BG_CARD).pack(side="left")
        self.var_workers = tk.IntVar(value=int(self.settings.get("workers", 128)))
        ttk.Spinbox(row, from_=8, to=512, increment=8, width=5,
                    textvariable=self.var_workers).pack(side="left", padx=(4, 10))
        tk.Label(row, text="采样", font=th.FONT, fg=th.FG_SUB,
                 bg=th.BG_CARD).pack(side="left")
        self.var_samples = tk.IntVar(value=int(self.settings.get("samples", 3)))
        ttk.Spinbox(row, from_=1, to=10, width=4,
                    textvariable=self.var_samples).pack(side="left", padx=4)

        tk.Frame(row, background=th.BORDER_SOFT, width=1, height=22).pack(
            side="left", padx=7, fill="y")

        self.btn_start = th.IconButton(row, "开始测速", "play",
                                       command=self.start_speedtest,
                                       variant="primary", bg=th.BG_CARD)
        self.btn_start.pack(side="left", padx=3)
        self.btn_stop = th.IconButton(row, "停止", "stop", command=self.stop_all,
                                      bg=th.BG_CARD)
        self.btn_stop.pack(side="left", padx=3)
        self.btn_stop.set_state("disabled")
        th.IconButton(row, "导出结果", "export", command=self.export_csv,
                      bg=th.BG_CARD).pack(side="left", padx=3)
        th.IconButton(row, "DNS 清单", "list", command=self.manage_entries,
                      bg=th.BG_CARD).pack(side="left", padx=3)
        self._refresh_kind_hint()

    def _build_statusbar(self):
        wrap = tk.Frame(self.foot, background=th.BG_CARD, highlightthickness=1,
                        highlightbackground=th.BORDER)
        wrap.pack(fill="x")
        inner = tk.Frame(wrap, background=th.BG_CARD)
        inner.pack(fill="x", padx=12, pady=8)
        self.pb = ttk.Progressbar(inner, style="Blue.Horizontal.TProgressbar",
                                  length=260)
        self.pb.pack(side="left")
        self.var_status = tk.StringVar(value="就绪")
        tk.Label(inner, textvariable=self.var_status, font=th.FONT_BOLD,
                 fg=th.BLUE_700, bg=th.BG_CARD).pack(side="left", padx=12)
        self.var_hint = tk.StringVar(value="")
        tk.Label(inner, textvariable=self.var_hint, font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_CARD).pack(side="left")

    def show_page(self, key):
        for k, frame in self.pages.items():
            if k == key:
                frame.grid()
                frame.tkraise()
            else:
                frame.grid_remove()
        for k, item in self.nav_items.items():
            item.set_selected(k == key)
        self.current_page = key

    # ----------------------------------------------------------------
    def log(self, msg):
        self.tab_log.write(msg)

    def status(self, text, done=None, total=None):
        self.var_status.set(text)
        self.var_side_status.set(text)
        if done is not None and total:
            self.pb.configure(maximum=max(1, total), value=done)
        elif total is None:
            self.pb.configure(value=0)

    def selected_kinds(self):
        """把「地址族 × 传输方式」两组勾选框展开成具体的端点类型。

        IPv4/IPv6 与 UDP/TCP 是正交的，所以结果就是两者的笛卡尔积：
            只勾 IPv4 + TCP          -> ['tcp4']
            IPv4/IPv6 + UDP/TCP 全勾 -> ['udp4','udp6','tcp4','tcp6']
        DoT / DoH 自成一个传输方式（自带加密），不受地址族勾选影响。
        """
        fams = [f for f, v in (("4", self.var_v4), ("6", self.var_v6)) if v.get()]
        trans = [t for t, v in (("udp", self.var_udp), ("tcp", self.var_tcp))
                 if v.get()]
        k = [f"{t}{f}" for t in trans for f in fams]
        if self.var_dot.get():
            k.append("dot")
        if self.var_doh.get():
            k.append("doh")
        return k

    def _refresh_kind_hint(self):
        """勾选框右边跟着显示「当前会测多少个端点」，避免勾空了还不知道。"""
        try:
            kinds = self.selected_kinds()
            if not kinds:
                self.var_kind_hint.set("未选通道")
                return
            n = sum(1 for ep in dnsdata.iter_endpoints(self.entries)
                    if ep[1] in kinds)
            self.var_kind_hint.set(f"{n} 端点")
        except Exception:
            pass

    # ---------------------------------------------------------------- 测速
    def start_speedtest(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "测速任务尚未结束。", parent=self)
            return
        kinds = self.selected_kinds()
        if not kinds:
            messagebox.showwarning("未选择通道", "请至少勾选一个测试通道。", parent=self)
            return
        eps = [ep for ep in dnsdata.iter_endpoints(self.entries) if ep[1] in kinds]
        if not eps:
            messagebox.showwarning("无端点", "选中通道下没有可测端点。", parent=self)
            return

        self.cancel_evt.clear()
        self.tab_speed.clear_tested([ep[0] for ep in eps])
        self.btn_start.set_state("disabled")
        self.btn_stop.set_state("normal")
        self.show_page("speed")

        # ★ 所有控件值必须在主线程读出来再传进线程。
        #   IntVar.get() / StringVar.get() 同样要走 Tcl，在后台线程里调用会抛
        #   RuntimeError: main thread is not in main loop —— 而且是整个任务静默失效，
        #   只留下一句日志，非常难查。
        workers = max(1, int(self.var_workers.get()))
        samples = max(1, int(self.var_samples.get()))

        self.status(f"测速中… 0/{len(eps)}", 0, len(eps))
        self.log(f"开始测速：{len(eps)} 个端点，并发 {workers}，"
                 f"采样 {samples} 次取最小值。")

        self.worker = threading.Thread(target=self._speed_work,
                                       args=(eps, workers, samples), daemon=True)
        self.worker.start()

    def _speed_work(self, eps, workers, samples):
        import channels
        t0 = time.time()
        try:
            channels.run_speedtest(
                eps, workers=workers, samples=samples, cancel=self.cancel_evt,
                on_result=lambda r: self.msg_q.put(("speed_result", r)),
                on_progress=lambda d, t: self.msg_q.put(("speed_progress", (d, t))))
        except Exception as e:
            import traceback
            self.msg_q.put(("log", f"测速异常：{type(e).__name__}: {e}"))
            self.msg_q.put(("log", traceback.format_exc().strip()))
        self.msg_q.put(("speed_done", time.time() - t0))

    def stop_all(self):
        self.cancel_evt.set()
        self.status("正在停止…")
        self.log("已请求停止。")

    def export_csv(self):
        if not self.speed_results:
            messagebox.showinfo("无数据", "还没有测速结果。", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv",
            initialfile=f"dns-speed-{time.strftime('%Y%m%d-%H%M%S')}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        rows = sorted(self.speed_results.values(), key=self.tab_speed._key,
                      reverse=self.tab_speed.sort_rev)
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["排名", "服务名", "分类", "通道", "地址", "端口",
                            "可用", "最快ms", "平均ms", "各次采样", "丢包", "状态",
                            "响应码", "解析结果"])
                for i, r in enumerate(rows, 1):
                    w.writerow([i, r.name, r.group, r.kind_label, r.display, r.port,
                                "是" if r.usable else "否",
                                "" if r.best_ms is None else round(r.best_ms, 2),
                                "" if r.avg_ms is None else round(r.avg_ms, 2),
                                "|".join("" if s is None else str(s) for s in r.samples),
                                r.loss, r.status, r.rcode_name,
                                ",".join(r.answers)])
            self.log(f"已导出 {len(rows)} 条结果到 {path}")
            if messagebox.askyesno("导出完成", f"已导出 {len(rows)} 条。\n\n打开所在目录？",
                                   parent=self):
                os.startfile(os.path.dirname(path))
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)

    # ---------------------------------------------------------------- 清单
    def manage_entries(self):
        win = tk.Toplevel(self)
        win.title("DNS 清单管理")
        win.geometry("580x400")
        win.transient(self)
        win.configure(background=th.BG_APP)
        self.center_window(win)
        tk.Label(win, text=f"当前 {len(self.entries)} 个服务，"
                           f"{len(list(dnsdata.iter_endpoints(self.entries)))} 个端点。",
                 font=th.FONT_H2, fg=th.BLUE_700, bg=th.BG_APP).pack(
            anchor="w", padx=14, pady=(14, 4))
        tk.Label(win, text="清单以 JSON 保存，可自行编辑后用「导入」载入；\n"
                           "「恢复内置」会丢弃你的改动，回到两个来源网站的全量清单。",
                 font=th.FONT, fg=th.FG_SUB, bg=th.BG_APP, justify="left"
                 ).pack(anchor="w", padx=14, pady=(0, 10))

        def do_export():
            p = filedialog.asksaveasfilename(parent=win, defaultextension=".json",
                                             initialfile="dnslist.json",
                                             filetypes=[("JSON", "*.json")])
            if not p:
                return
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"entries": self.entries, "domains": self.domains},
                          f, ensure_ascii=False, indent=1)
            self.log(f"清单已导出：{p}")

        def do_import():
            p = filedialog.askopenfilename(parent=win, filetypes=[("JSON", "*.json")])
            if not p:
                return
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                ents = data.get("entries") if isinstance(data, dict) else data
                if not isinstance(ents, list) or not ents:
                    raise ValueError("文件里没有 entries 数组")
                self.entries = ents
                if isinstance(data, dict) and data.get("domains"):
                    self.domains = data["domains"]
                    self.tab_pollute.reload_domains()
                self._save_config()
                n = len(list(dnsdata.iter_endpoints(self.entries)))
                self.log(f"已导入清单：{len(ents)} 个服务 / {n} 个端点。")
                win.destroy()
            except Exception as e:
                messagebox.showerror("导入失败", str(e), parent=win)

        def do_reset():
            if not messagebox.askyesno("确认", "恢复为内置全量清单？当前改动会丢失。",
                                       parent=win):
                return
            self.entries = [dict(e) for e in dnsdata.DEFAULT_ENTRIES]
            self._save_config()
            self.log(f"已恢复内置清单：{len(self.entries)} 个服务。")
            win.destroy()

        box = tk.Frame(win, background=th.BG_APP)
        box.pack(fill="x", padx=14)
        ttk.Button(box, text="导出 JSON", command=do_export).pack(side="left", padx=4)
        ttk.Button(box, text="导入 JSON", command=do_import).pack(side="left", padx=4)
        ttk.Button(box, text="恢复内置全量", command=do_reset).pack(side="left", padx=4)
        ttk.Button(box, text="关闭", command=win.destroy).pack(side="right", padx=4)

    # ---------------------------------------------------------------- 消息泵
    def _poll(self):
        n = 0
        try:
            while n < 300:
                kind, payload = self.msg_q.get_nowait()
                n += 1
                if kind == "speed_result":
                    self.speed_results[payload.key] = payload
                    self.tab_speed.add_result(payload)
                    self._visual_tick += 1
                    if self._visual_tick % 30 == 0:
                        self.tab_speed.update_visuals()
                elif kind == "speed_progress":
                    d, t = payload
                    self.status(f"测速中… {d}/{t}", d, t)
                elif kind == "speed_done":
                    self._on_speed_done(payload)
                elif kind == "pollute_stage":
                    self.tab_pollute.update_stage(*payload)
                elif kind == "pollute_resolve":
                    self.tab_pollute.on_resolve(payload)
                elif kind == "pollute_pairs":
                    self.tab_pollute.on_pairs(payload)
                elif kind == "pollute_probe":
                    self.tab_pollute.on_probe(payload)
                elif kind == "pollute_done":
                    self._on_check_done(payload)
                elif kind == "log":
                    self.log(payload)
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _on_speed_done(self, elapsed):
        tested = [r for r in self.speed_results.values() if r.samples]
        usable = [r for r in tested if r.usable]
        refused = len([r for r in tested if r.rcode == 5])
        failed = len(tested) - len(usable) - refused
        self.tab_speed.cancel_pending_resort()
        self.tab_speed.resort()
        self.tab_speed.refresh()
        self.tab_speed.update_visuals()
        self.btn_start.set_state("normal")
        self.btn_stop.set_state("disabled")
        msg = (f"测速完成：{len(usable)}/{len(tested)} 个可用"
               f"（拒绝 {refused}、失败 {failed}），用时 {elapsed:.1f} 秒")
        self.status(msg)
        self.log(msg + "。「拒绝」等非 0 响应码已按不可用处理，不参与排序与统计。")
        self.tab_pollute.on_speed_done()

    def _on_check_done(self, report):
        self.report = report
        self.tab_pollute.show_report(report)
        self.tab_hosts.on_report(report)
        self.btn_start.set_state("normal")
        self.btn_stop.set_state("disabled")

    def set_busy(self, busy):
        self.btn_start.set_state("disabled" if busy else "normal")
        self.btn_stop.set_state("normal" if busy else "disabled")
        if busy:
            self.show_page("pollute")

    # ---------------------------------------------------------------- 配置
    def _load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "entries": self.entries,
                    "domains": self.domains,
                    "settings": {"workers": int(self.var_workers.get()),
                                 "samples": int(self.var_samples.get())},
                }, f, ensure_ascii=False, indent=1)
        except Exception as e:
            self.log(f"保存配置失败：{e}")

    def _on_close(self):
        self._save_config()
        self.cancel_evt.set()
        self.destroy()


def main():
    app = App()
    app.log("就绪。全部端点已列出，点「开始测速」即可跑一遍。")
    app.mainloop()
