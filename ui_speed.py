# -*- coding: utf-8 -*-
"""延迟测速页：统计卡片 + Top-N 条形图 + 全量端点表格。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import channels
import dnsdata
import theme as th


def _pct(a, b):
    return f"{a / b * 100:.0f}%" if b else "—"


class SpeedTab(tk.Frame):
    COLS = [
        ("rank", "#", 42, "center"),
        ("name", "服务名", 185, "w"),
        ("group", "分类", 58, "center"),
        ("kind", "通道", 82, "center"),
        ("server", "地址", 240, "w"),
        ("best", "最快 (ms)", 82, "e"),
        ("avg", "平均 (ms)", 82, "e"),
        ("loss", "丢包", 52, "center"),
        ("status", "状态", 104, "w"),
        ("sample", "解析示例", 260, "w"),
    ]

    def __init__(self, master, app):
        super().__init__(master, background=th.BG_APP)
        self.app = app
        self.rows = {}
        self.sort_col = "best"
        self.sort_rev = False
        self._resort_after = None
        self._prefill_queue = None
        self._chart_open = True
        self._toast = None
        self._build()
        # 右键单击 = 直接复制该行 DNS 地址（一步到位，不弹子菜单）；
        # 想按列复制或复制整行时按住 Ctrl 再右键，弹完整菜单。
        self.tree.bind("<Button-3>", self._on_right_click)
        self._copy_menu = th.attach_copy_menu(self.tree, self._ctx_info,
                                              trigger="<Control-Button-3>")

    # ----------------------------------------------------------------
    def _build(self):
        cards = tk.Frame(self, background=th.BG_APP)
        cards.pack(fill="x", padx=10, pady=(10, 6))
        self.cards = {}
        for key, label, accent in (
                ("total", "可测端点", th.BLUE_600),
                ("ok", "可用", th.OK),
                ("fast", "最快", th.BLUE_500),
                ("med", "中位延迟", th.BLUE_400),
                ("bad", "不可用", th.BAD)):
            c = th.StatCard(cards, label, "—", accent)
            c.pack(side="left", fill="both", expand=True, padx=(0, 8))
            self.cards[key] = c

        self.chart_box = tk.Frame(self, background=th.BG_CARD,
                                  highlightthickness=1,
                                  highlightbackground=th.BORDER)
        self.chart_box.pack(fill="x", padx=10, pady=(0, 6))
        head = tk.Frame(self.chart_box, background=th.BG_CARD)
        head.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(head, text="最快 10 名", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(side="left")
        self.var_chart_hint = tk.StringVar(value="")
        tk.Label(head, textvariable=self.var_chart_hint, font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_CARD).pack(side="left", padx=10)
        self.btn_chart = th.IconButton(head, "收起", "chevron_up",
                                       command=self._toggle_chart,
                                       variant="ghost", bg=th.BG_CARD)
        self.btn_chart.pack(side="right")
        self.chart = th.BarChart(self.chart_box, height=190)
        self.chart.pack(fill="x", padx=12, pady=(4, 10))

        bar = tk.Frame(self, background=th.BG_APP)
        bar.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(bar, text="搜索", font=th.FONT, fg=th.FG_SUB,
                 bg=th.BG_APP).pack(side="left")
        self.var_q = tk.StringVar()
        self.var_q.trace_add("write", lambda *_: self._debounce_filter())
        ttk.Entry(bar, textvariable=self.var_q, width=20).pack(side="left", padx=(6, 12))
        tk.Label(bar, text="分类", font=th.FONT, fg=th.FG_SUB,
                 bg=th.BG_APP).pack(side="left")
        self.var_group = tk.StringVar(value="全部")
        cb = ttk.Combobox(bar, textvariable=self.var_group, width=9,
                          state="readonly", values=["全部"] + dnsdata.GROUPS)
        cb.pack(side="left", padx=(6, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        tk.Label(bar, text="通道", font=th.FONT, fg=th.FG_SUB,
                 bg=th.BG_APP).pack(side="left")
        self.var_kind = tk.StringVar(value="全部")
        cb2 = ttk.Combobox(bar, textvariable=self.var_kind, width=12,
                           state="readonly",
                           values=["全部"] + [channels.KIND_LABEL[k]
                                              for k in channels.KIND_ORDER])
        cb2.pack(side="left", padx=(6, 12))
        cb2.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.var_only_ok = tk.BooleanVar(value=False)
        th.checkbutton_with_icon(bar, "只看可用", self.var_only_ok, "filter",
                                 bg=th.BG_APP,
                                 command=self.refresh).pack(side="left", padx=(0, 12))
        self.var_sortlive = tk.BooleanVar(value=True)
        th.checkbutton_with_icon(bar, "实时排序", self.var_sortlive, "clock",
                                 bg=th.BG_APP).pack(side="left")
        tk.Label(bar, text="右键单击行＝复制地址（Ctrl+右键＝更多）",
                 font=th.FONT_SM, fg=th.FG_MUTE,
                 bg=th.BG_APP).pack(side="right")

        wrap = tk.Frame(self, background=th.BG_APP)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in self.COLS],
                                 show="headings", selectmode="browse")
        for key, title, width, anchor in self.COLS:
            self.tree.heading(key, text=title, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key in ("server", "sample")))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        for tag, color in (("ok", th.OK), ("fast", th.BLUE_700),
                           ("warn", th.WARN), ("bad", th.BAD),
                           ("mute", th.MUTE)):
            self.tree.tag_configure(tag, foreground=color)
        self._filter_after = None
        self.tree.bind("<Double-1>", self._on_double)

    def _toggle_chart(self):
        if self._chart_open:
            self.chart.pack_forget()
            self.btn_chart.set_text("展开")
            self.btn_chart.set_icon("chevron_down")
        else:
            self.chart.pack(fill="x", padx=12, pady=(4, 10))
            self.btn_chart.set_text("收起")
            self.btn_chart.set_icon("chevron_up")
        self._chart_open = not self._chart_open

    # ---------------------------------------------------------------- 预填充
    def prefill(self):
        """打开软件就把所有端点铺进表格，未测的显示灰色「待测」。"""
        if self._prefill_queue is not None:
            return
        self._prefill_queue = list(dnsdata.iter_endpoints(self.app.entries))
        self._prefill_step()

    def _prefill_step(self, batch=110):
        n = 0
        while self._prefill_queue and n < batch:
            key, kind, payload = self._prefill_queue.pop(0)
            r = channels.SpeedResult(
                key=key, kind=kind, name=payload.get("name", "?"),
                group=payload.get("group", "未分类"),
                server=payload.get("server", "?"),
                port=payload.get("port", 53),
                display=payload.get("display", payload.get("server", "?")))
            self.app.speed_results[key] = r
            self._insert(r)
            n += 1
        self._update_cards()
        if self._prefill_queue:
            self.after(25, self._prefill_step)
        else:
            self._prefill_queue = None
            self.resort()
            self._update_chart()
            self.app.log(f"已载入 {len(self.rows)} 个端点，等待测速。")

    # ---------------------------------------------------------------- 表格
    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        self.resort()
        self.refresh()

    def _key(self, r):
        """排序键。分三档：可用 → 有响应但不可用 → 待测。

        「有响应但不可用」单独一档而不是混进失败档，是因为它和超时不是一回事：
        服务器活着、只是不肯给你解析。放在失败档的顶部更符合直觉。
        """
        tested = bool(r.samples)
        if self.sort_col == "best":
            return (0 if r.usable else (1 if tested else 2),
                    r.best_ms if r.best_ms is not None else 9e9, r.name)
        if self.sort_col == "avg":
            return (0 if r.usable else (1 if tested else 2),
                    r.avg_ms if r.avg_ms is not None else 9e9, r.name)
        if self.sort_col == "name":
            return (r.name,)
        if self.sort_col == "group":
            return (dnsdata.GROUPS.index(r.group) if r.group in dnsdata.GROUPS else 99,
                    r.name)
        if self.sort_col == "kind":
            return (r.kind, r.best_ms if r.best_ms is not None else 9e9)
        if self.sort_col == "server":
            return (r.server,)
        if self.sort_col == "status":
            return (r.status, r.best_ms if r.best_ms is not None else 9e9)
        return (r.name,)

    def resort(self):
        if not self.rows:
            return
        ordered = sorted(self.app.speed_results.values(), key=self._key,
                         reverse=self.sort_rev)
        for i, r in enumerate(ordered):
            iid = self.rows.get(r.key)
            if iid and self.tree.exists(iid):
                try:
                    self.tree.move(iid, "", i)
                except Exception:
                    pass
        self._renumber()

    def schedule_resort(self, delay=350):
        """节流合并重排请求。

        每个结果都触发一次全表 move 是 O(n²)：400+ 端点跑完就是十几万次
        tree.move，界面必然卡死。
        """
        if self._resort_after is not None:
            return
        self._resort_after = self.after(delay, self._flush_resort)

    def _flush_resort(self):
        self._resort_after = None
        self.resort()

    def cancel_pending_resort(self):
        if self._resort_after is not None:
            try:
                self.after_cancel(self._resort_after)
            except Exception:
                pass
            self._resort_after = None

    def _renumber(self):
        for i, iid in enumerate(self.tree.get_children("")):
            vals = list(self.tree.item(iid, "values"))
            if vals:
                vals[0] = str(i + 1)
                self.tree.item(iid, values=vals)

    def _insert(self, r):
        iid = r.key
        self.rows[r.key] = iid
        try:
            self.tree.insert("", "end", iid=iid, values=self._values(r, len(self.rows)),
                             tags=(self._tag(r),))
        except Exception:
            self.rows.pop(r.key, None)

    def add_result(self, r):
        iid = self.rows.get(r.key)
        if iid and self.tree.exists(iid):
            self.tree.item(iid, values=self._values(r, self.tree.index(iid) + 1))
        else:
            self._insert(r)
            iid = self.rows.get(r.key)
        if iid:
            self.tree.item(iid, tags=(self._tag(r),))
        if self.var_sortlive.get():
            self.schedule_resort(280)
        elif not self._visible(r) and iid:
            try:
                self.tree.detach(iid)
            except Exception:
                pass

    def _tag(self, r):
        if not r.samples and not r.ok:
            return "mute"                     # 待测
        if not r.usable:
            # 有响应但没给出解析结果（拒绝 / 服务器故障…）用暖色，
            # 纯粹连不上用灰/红。两者都不能算成绩。
            if r.error and r.error != "Timeout":
                return "bad"
            return "warn" if r.ok else "mute"
        if (r.best_ms or 999) < 30:
            return "fast"
        return "ok" if (r.best_ms or 999) < 150 else "warn"

    @staticmethod
    def _status_text(r):
        """状态列：● 可用 / ✕ 有响应但不可用 / ○ 无响应。"""
        if r.usable:
            return "● " + r.status
        if r.ok:
            return "✕ " + r.status              # 「拒绝」「服务器故障」…
        return "○ " + r.status

    def _values(self, r, rank):
        if not r.samples and not r.ok:
            status = "待测"
            sample = "—"
        else:
            status = self._status_text(r)
            sample = ", ".join(r.answers[:2]) if r.answers else (r.error or "-")
        return (
            str(rank), r.name, r.group, r.kind_label, r.display,
            f"{r.best_ms:.1f}" if r.best_ms is not None else "—",
            f"{r.avg_ms:.1f}" if r.avg_ms is not None else "—",
            r.loss if r.samples else "—",
            status, sample,
        )

    def _visible(self, r):
        q = self.var_q.get().strip().lower()
        if q and q not in r.name.lower() and q not in r.server.lower() \
                and q not in r.display.lower():
            return False
        g = self.var_group.get()
        if g != "全部" and r.group != g:
            return False
        k = self.var_kind.get()
        if k != "全部" and r.kind_label != k:
            return False
        if self.var_only_ok.get() and not r.usable:
            return False
        return True

    def _debounce_filter(self, delay=220):
        if self._filter_after is not None:
            try:
                self.after_cancel(self._filter_after)
            except Exception:
                pass
        self._filter_after = self.after(delay, self._do_filter)

    def _do_filter(self):
        self._filter_after = None
        self.refresh()

    def refresh(self):
        order = 0
        for r in sorted(self.app.speed_results.values(), key=self._key,
                        reverse=self.sort_rev):
            iid = self.rows.get(r.key)
            if not iid or not self.tree.exists(iid):
                continue
            try:
                self.tree.detach(iid)
            except Exception:
                pass
            if self._visible(r):
                try:
                    self.tree.move(iid, "", order)
                    order += 1
                except Exception:
                    pass
        self._renumber()

    def clear_tested(self, keys):
        """开始新一轮测速前，把本轮要测的端点重置回「待测」。"""
        for k in keys:
            r = self.app.speed_results.get(k)
            if r is None:
                continue
            r.ok = False
            r.best_ms = None
            r.samples = []
            r.rcode = None
            r.answers = []
            r.error = None
        self.resort()
        self.refresh()
        self._update_cards()

    # ---------------------------------------------------------------- 图形
    def update_visuals(self):
        self._update_cards()
        self._update_chart()

    def _update_cards(self):
        allr = list(self.app.speed_results.values())
        tested = [r for r in allr if r.samples]
        # 「可用」必须是拿到了解析结果的（响应码 0）。「有响应」不等于可用 ——
        # 拒绝/服务器故障这类服务器延迟很漂亮，但一个域名都解析不了。
        usable = [r for r in tested if r.usable and r.best_ms is not None]
        bad = [r for r in tested if not r.usable]
        pending = len(allr) - len(tested)
        refused = len([r for r in tested if r.rcode == 5])
        self.cards["total"].set(len(allr), f"待测 {pending}" if pending else "已全部测过")
        sub = f"占已测 {_pct(len(usable), len(tested))}"
        if refused:
            sub += f" · 拒绝 {refused}"
        self.cards["ok"].set(len(usable), sub)
        if usable:
            fast = min(usable, key=lambda r: r.best_ms)
            self.cards["fast"].set(f"{fast.best_ms:.1f} ms", fast.name)
            lat = sorted(r.best_ms for r in usable)
            self.cards["med"].set(f"{lat[len(lat) // 2]:.1f} ms",
                                  f"共 {len(usable)} 个可用")
        else:
            self.cards["fast"].set("—", "尚未测速")
            self.cards["med"].set("—", "尚未测速")
        self.cards["bad"].set(len(bad),
                              "超时 / 失败 / 拒绝" if bad else "—")

    def _update_chart(self):
        done = sorted((r for r in self.app.speed_results.values()
                       if r.usable and r.best_ms is not None),
                      key=lambda r: r.best_ms)
        items = []
        for r in done[:10]:
            # 用蓝色深浅表达快慢，只有明显偏慢的才用暖色提示，整体保持蓝白调
            if r.best_ms < 50:
                color = th.BLUE_700
            elif r.best_ms < 150:
                color = th.BLUE_400
            elif r.best_ms < 300:
                color = th.BLUE_200
            else:
                color = th.WARN
            items.append((f"{r.name} · {r.kind_label}", r.best_ms, color))
        self.chart.set_items(items, empty="暂无数据 — 点「开始测速」")
        n_bad = len([r for r in self.app.speed_results.values()
                     if r.samples and not r.usable])
        hint = f"共 {len(done)} 个可用端点" if done else ""
        if hint and n_bad:
            hint += f"　|　已排除 {n_bad} 个不可用（拒绝 / 故障 / 超时）"
        self.var_chart_hint.set(hint)

    # ---------------------------------------------------------------- 交互
    # ---------------------------------------------------------------- 右键复制
    def _on_right_click(self, event):
        """右键单击一次 = 复制该行 DNS 地址，不弹子菜单。"""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        r = self.app.speed_results.get(iid)
        if r is None:
            return
        addr = str(r.display)
        try:
            self.clipboard_clear()
            self.clipboard_append(addr)
        except Exception:
            pass
        self.app.status(f"已复制到剪贴板：{addr}")
        self._show_toast(f"已复制  {th._ellipsis(addr, 56)}",
                         event.x_root, event.y_root)

    def _show_toast(self, text, x_root, y_root):
        """在光标旁边冒一个小提示，1 秒后自动消失。

        右键复制如果没有任何视觉反馈，用户会怀疑到底复制上没有。
        整个函数包在 try 里 —— 提示失败绝不能影响复制本身。
        """
        try:
            if self._toast is not None:
                self._toast.destroy()
        except Exception:
            pass
        self._toast = None
        try:
            top = tk.Toplevel(self)
            top.overrideredirect(True)
            try:
                top.attributes("-topmost", True)
            except Exception:
                pass
            tk.Label(top, text=text, font=th.FONT, fg="#FFFFFF",
                     bg=th.BLUE_700, padx=10, pady=4).pack()
            top.update_idletasks()
            top.geometry(f"+{x_root + 14}+{y_root + 14}")
            self._toast = top
            top.after(1000, lambda: self._kill_toast(top))
        except Exception:
            self._toast = None

    def _kill_toast(self, top):
        try:
            top.destroy()
        except Exception:
            pass
        if self._toast is top:
            self._toast = None

    def _ctx_info(self):
        sel = self.tree.selection()
        if not sel:
            return None
        r = self.app.speed_results.get(sel[0])
        if not r:
            return None
        vals = list(self.tree.item(sel[0], "values"))
        cols = [c[1] for c in self.COLS]
        title = f"{r.name} · {r.kind_label}"
        return (title, cols, vals)

    def _on_double(self, _e):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.app.speed_results.get(sel[0])
        if not r:
            return
        rc = "—" if r.rcode is None else f"{r.rcode_cn}（{r.rcode_name}）"
        tip = ""
        if r.rcode == 5:
            tip = ("\n注意        : 服务器收到了查询但拒绝为你解析 —— 通常是来源限制"
                   "（只对特定网段开放）。\n              它的延迟成绩是「假的好成绩」，"
                   "不能用来挑 DNS。")
        elif r.rcode not in (None, 0):
            tip = "\n注意        : 这个响应码说明本次解析没拿到结果，延迟仅供参考。"
        messagebox.showinfo(
            f"{r.name} · {r.kind_label}",
            f"地址        : {r.display}\n端口        : {r.port}\n"
            f"最快        : {f'{r.best_ms:.1f} ms' if r.best_ms is not None else '—'}\n"
            f"平均        : {f'{r.avg_ms:.1f} ms' if r.avg_ms is not None else '—'}\n"
            f"各次采样    : {r.samples or '（尚未测试）'}\n"
            f"响应码      : {rc}\n"
            f"错误        : {r.error or '无'}\n"
            f"解析结果    : {', '.join(r.answers) if r.answers else '无'}{tip}",
            parent=self.app)
