# -*- coding: utf-8 -*-
"""污染检测页：实时进度、逐行刷新、图形化统计。"""
from __future__ import annotations

import csv
import threading
import time as _time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import channels
import dnsdata
import pollution
import theme as th

ORDER = {"clean": 0, "mixed": 1, "hijack": 2, "blocked": 3, "bogus": 4,
         "appfail": 5, "dead": 6, "nodata": 7}
MARK = {"clean": "√", "mixed": "!", "hijack": "×", "blocked": "×",
        "bogus": "×", "appfail": "△", "dead": "×", "nodata": "·"}
TAG = {"clean": "ok", "mixed": "warn", "hijack": "bad", "blocked": "bad",
       "bogus": "bad", "appfail": "warn", "dead": "mute", "nodata": "mute"}
BAD_VERDICTS = ("hijack", "blocked", "bogus")

GRADE_SHORT = {"ok": "可用", "unstable": "不稳", "appfail": "打不开",
               "hijack": "劫持", "blocked": "阻断", "bogus": "拦截",
               "dead": "不可达"}
# 详情面板里地址的排列顺序（好的在前）
GRADE_ORDER = {"ok": 0, "unstable": 1, "appfail": 2, "hijack": 3,
               "bogus": 4, "blocked": 5, "dead": 6}


class PolluteTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, background=th.BG_APP)
        self.app = app
        self.report = None
        self._iid_of = {}
        self._row_meta = {}
        self._row_ips = {}
        self._ip_rows = {}
        self._row_stat = {}
        self._domain_rows = {}
        self._build()

    # ----------------------------------------------------------------
    def _build(self):
        bar = tk.Frame(self, background=th.BG_APP)
        bar.pack(fill="x", padx=10, pady=(10, 6))
        self.var_only_tested = tk.BooleanVar(value=True)
        th.checkbutton_with_icon(bar, "只测已通过测速的 DNS", self.var_only_tested,
                                 "filter", bg=th.BG_APP,
                                 command=self._update_scope).pack(side="left")
        self.var_ref = tk.BooleanVar(value=True)
        th.checkbutton_with_icon(bar, "海外 DoH/DoT 基准", self.var_ref,
                                 "globe", bg=th.BG_APP).pack(side="left", padx=12)
        self.var_aaaa = tk.BooleanVar(value=False)
        th.checkbutton_with_icon(bar, "同时查 AAAA（IPv6）", self.var_aaaa,
                                 "layers", bg=th.BG_APP).pack(side="left", padx=12)
        self.btn_check = th.IconButton(bar, "开始污染检测", "play",
                                       command=self.start_check,
                                       variant="primary", bg=th.BG_APP)
        self.btn_check.pack(side="left", padx=8)
        th.IconButton(bar, "目标域名…", "list", command=self.edit_domains,
                      bg=th.BG_APP).pack(side="left")
        th.IconButton(bar, "导出报告", "export", command=self.export_report,
                      bg=th.BG_APP).pack(side="left", padx=6)
        tk.Label(bar, text="右键可复制", font=th.FONT_SM, fg=th.FG_MUTE,
                 bg=th.BG_APP).pack(side="right")

        cards = tk.Frame(self, background=th.BG_APP)
        cards.pack(fill="x", padx=10, pady=(0, 6))
        self.cards = {}
        for key, label, accent in (
                ("domains", "目标域名", th.BLUE_600),
                ("clean", "真正能访问", th.OK),
                ("appfail", "握得上打不开", th.WARN),
                ("dirty", "疑似污染", th.BAD),
                ("dead", "完全连不上", th.BLUE_400)):
            c = th.StatCard(cards, label, "—", accent)
            c.pack(side="left", fill="both", expand=True, padx=(0, 8))
            self.cards[key] = c

        prog = tk.Frame(self, background=th.BG_CARD, highlightthickness=1,
                        highlightbackground=th.BORDER)
        prog.pack(fill="x", padx=10, pady=(0, 6))
        line = tk.Frame(prog, background=th.BG_CARD)
        line.pack(fill="x", padx=12, pady=(9, 4))
        self.var_stage = tk.StringVar(value="就绪 — 点「开始污染检测」")
        tk.Label(line, textvariable=self.var_stage, font=th.FONT_BOLD,
                 fg=th.BLUE_700, bg=th.BG_CARD).pack(side="left")
        self.var_count = tk.StringVar(value="")
        tk.Label(line, textvariable=self.var_count, font=th.FONT_SM,
                 fg=th.FG_SUB, bg=th.BG_CARD).pack(side="right")
        self.pb = ttk.Progressbar(prog, style="Blue.Horizontal.TProgressbar",
                                  mode="determinate")
        self.pb.pack(fill="x", padx=12, pady=(0, 6))
        self.var_scope = tk.StringVar(value="")
        tk.Label(prog, textvariable=self.var_scope, font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_CARD).pack(anchor="w", padx=12, pady=(0, 9))

        health = tk.Frame(self, background=th.BG_CARD, highlightthickness=1,
                          highlightbackground=th.BORDER)
        health.pack(fill="x", padx=10, pady=(0, 6))
        hh = tk.Frame(health, background=th.BG_CARD)
        hh.pack(fill="x", padx=12, pady=(9, 2))
        tk.Label(hh, text="总体判定分布", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(side="left")
        self.var_health = tk.StringVar(value="")
        tk.Label(hh, textvariable=self.var_health, font=th.FONT_SM, fg=th.FG_SUB,
                 bg=th.BG_CARD).pack(side="right")
        self.stack = th.StackBar(health, height=24)
        self.stack.pack(fill="x", padx=12, pady=(2, 10))

        split = ttk.PanedWindow(self, orient="vertical")
        split.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        wrap = tk.Frame(split, background=th.BG_APP)
        self.tree = ttk.Treeview(wrap, columns=("verdict", "detail", "extra"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="域名 / DNS 服务")
        self.tree.heading("verdict", text="判定")
        self.tree.heading("detail", text="说明")
        self.tree.heading("extra", text="解析返回")
        self.tree.column("#0", width=350, anchor="w")
        self.tree.column("verdict", width=118, anchor="center")
        self.tree.column("detail", width=400, anchor="w")
        self.tree.column("extra", width=290, anchor="w")
        for tag, color in (("ok", th.OK), ("warn", th.WARN), ("bad", th.BAD),
                           ("mute", th.MUTE)):
            self.tree.tag_configure(tag, foreground=color)
        self.tree.tag_configure("group", font=th.FONT_BOLD, foreground=th.BLUE_700)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        split.add(wrap, weight=3)

        dwrap = tk.Frame(split, background=th.BG_APP)
        head = tk.Frame(dwrap, background=th.BG_APP)
        head.pack(fill="x", pady=(4, 2))
        tk.Label(head, text="选中项详情", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_APP).pack(side="left")
        tk.Label(head, text="（可选中文本后 Ctrl+C，或右键复制）", font=th.FONT_SM,
                 fg=th.FG_MUTE, bg=th.BG_APP).pack(side="left", padx=8)
        self.detail = tk.Text(dwrap, wrap="word", font=th.MONO, height=11,
                              background=th.BG_CARD, foreground=th.FG,
                              relief="solid", borderwidth=1)
        dsb = ttk.Scrollbar(dwrap, orient="vertical", command=self.detail.yview)
        self.detail.configure(yscrollcommand=dsb.set, state="disabled")
        self.detail.pack(side="left", fill="both", expand=True)
        dsb.pack(side="right", fill="y")
        split.add(dwrap, weight=2)

        th.attach_copy_menu(self.tree, self._ctx_info)

    # ----------------------------------------------------------------
    def _iid(self, domain, dns_key):
        return self._iid_of.get((domain, dns_key))

    def _ensure_group(self, domain):
        iid = self._domain_rows.get(domain)
        if iid is None:
            iid = f"d:{domain}"
            try:
                self.tree.insert("", "end", iid=iid, text=domain, open=True,
                                 tags=("group",),
                                 values=("检测中…", "", ""))
            except tk.TclError:
                return None
            self._domain_rows[domain] = iid
        return iid

    def _ensure_row(self, domain, dns_key, name, server, kind):
        iid = self._iid(domain, dns_key)
        if iid is not None:
            return iid
        parent = self._ensure_group(domain)
        if parent is None:
            return None
        iid = f"r{len(self._row_meta)}"
        try:
            self.tree.insert(parent, "end", iid=iid,
                             text=f"   · {name}  ({server})",
                             tags=("mute",),
                             values=("等待中…", "", ""))
        except tk.TclError:
            return None
        self._iid_of[(domain, dns_key)] = iid
        self._row_meta[iid] = (domain, dns_key)
        return iid

    # ---------------------------------------------------------------- 实时
    def on_resolve(self, a):
        iid = self._ensure_row(a.domain, a.dns_key, a.dns_name, a.server, a.kind)
        if iid is None or not self.tree.exists(iid):
            return
        if not a.ok:
            self.tree.item(iid, values=("解析失败", a.error or "-", "-"),
                           tags=("mute",))
            return
        self._row_ips[iid] = list(a.ips)
        for ip in a.ips:
            self._ip_rows.setdefault((a.domain, ip), set()).add(iid)
        if not a.ips:
            self.tree.item(iid, values=("无地址", pollution.P.rcode_cn(a.rcode), "-"),
                           tags=("mute",))
            return
        ms = f"{a.ms:.0f} ms" if a.ms else ""
        self.tree.item(iid, values=(
            f"已解析 {len(a.ips)} 个",
            f"解析耗时 {ms}",
            ", ".join(a.ips[:3]) + ("…" if len(a.ips) > 3 else "")))

    def on_probe(self, pr):
        for iid in self._ip_rows.get((pr.domain, pr.ip), ()):
            st = self._row_stat.setdefault(iid, {})
            st[pr.grade] = st.get(pr.grade, 0) + 1
            self._render_live(iid)

    def _render_live(self, iid):
        st = self._row_stat.get(iid)
        if not st or not self.tree.exists(iid):
            return
        parts = [f"{GRADE_SHORT.get(g, g)}×{n}"
                 for g, n in sorted(st.items(), key=lambda kv: kv[0])
                 if n]
        good = st.get("ok", 0) + st.get("unstable", 0)
        if good and not (st.get("hijack") or st.get("bogus")):
            main, tag = ("完全可用" if st.get("ok") == good else "可用(不稳)"), "ok"
        elif good:
            main, tag = "部分可用", "warn"
        elif st.get("hijack"):
            main, tag = "疑似劫持", "bad"
        elif st.get("bogus"):
            main, tag = "明确拦截", "bad"
        elif st.get("blocked"):
            main, tag = "疑似阻断", "warn"
        else:
            main, tag = "不可达", "mute"
        vals = list(self.tree.item(iid, "values"))
        vals[0] = f"● {main}"
        vals[1] = "，".join(parts)
        self.tree.item(iid, values=vals, tags=(tag,))

    def on_pairs(self, pairs):
        self.var_scope.set(self.var_scope.get().split("　|　")[0]
                           + f"　|　待探测地址组合 {len(pairs)} 个")

    # ---------------------------------------------------------------- 控制
    def reload_domains(self):
        self._update_scope()

    def on_speed_done(self):
        self._update_scope()

    def _targets(self):
        out, seen = [], set()
        if self.var_only_tested.get() and self.app.speed_results:
            for r in sorted(self.app.speed_results.values(), key=lambda x: x.sort_key()):
                # 只挑「可用」的（响应码 0）。拒绝/故障的服务器拿不到解析结果，
                # 让它们参与污染检测只会白跑一轮，结果全是「解析失败」。
                if not r.usable or r.name in seen:
                    continue
                seen.add(r.name)
                out.append({"key": r.key, "kind": r.kind,
                            "payload": {"name": r.name, "group": r.group,
                                        "server": r.server, "port": r.port,
                                        "display": r.display}})
            return out
        by_name = {}
        for key, kind, payload in dnsdata.iter_endpoints(self.app.entries):
            by_name.setdefault(payload["name"], []).append((key, kind, payload))
        for _name, lst in by_name.items():
            for pref in ("udp4", "udp6", "tcp4", "tcp6", "dot", "doh"):
                hit = next((it for it in lst if it[1] == pref), None)
                if hit:
                    out.append({"key": hit[0], "kind": hit[1], "payload": hit[2]})
                    break
        return out

    def _update_scope(self):
        n = len(self._targets())
        d = len(self.app.domains)
        mode = "已测速的 DNS" if (self.var_only_tested.get() and self.app.speed_results) \
            else "全部 DNS（每服务取 1 个端点）"
        warn = "　（行数较多，插入会分批进行）" if n * d > 700 else ""
        self.var_scope.set(f"范围：{mode} × {n} 个 DNS × {d} 个域名"
                           f"，最多 {n * d} 次解析{warn}")

    def start_check(self):
        worker = getattr(self.app, "pollute_worker", None)
        if worker and worker.is_alive():
            messagebox.showinfo("正在运行", "污染检测尚未结束。", parent=self.app)
            return
        targets = self._targets()
        if not targets:
            messagebox.showwarning("无目标", "没有可用于解析的 DNS，请先跑一次测速。",
                                   parent=self.app)
            return
        if not self.app.domains:
            messagebox.showwarning("无域名", "请先添加至少一个目标域名。", parent=self.app)
            return

        qtypes = [pollution.P.QTYPE_A]
        if self.var_aaaa.get():
            qtypes.append(pollution.P.QTYPE_AAAA)

        # ★ 控件值必须在主线程读好再传进去：后台线程调 var.get() 会走 Tcl，
        #   直接抛 "main thread is not in main loop"。
        use_ref = bool(self.var_ref.get())
        domains = list(self.app.domains)

        self.app.cancel_evt.clear()
        self.app.set_busy(True)
        self.tree.delete(*self.tree.get_children(""))
        self._iid_of.clear()
        self._row_meta.clear()
        self._row_ips.clear()
        self._ip_rows.clear()
        self._row_stat.clear()
        self._domain_rows.clear()
        self._set_detail("")
        self.report = None
        self.stack.set_segments([])
        self.var_health.set("")
        for key in self.cards:
            self.cards[key].set("—", "")
        self.app.log(f"开始污染检测：{len(targets)} 个 DNS × {len(domains)} 个域名。")

        self.app.pollute_worker = threading.Thread(
            target=self._work, args=(targets, qtypes, use_ref, domains), daemon=True)
        self.app.pollute_worker.start()

    def _work(self, targets, qtypes, use_ref, domains):
        q = self.app.msg_q
        try:
            report = pollution.run_check(
                targets, domains,
                cancel=self.app.cancel_evt,
                use_reference=use_ref,
                qtypes=qtypes,
                stage_cb=lambda name, d, t: q.put(("pollute_stage", (name, d, t))),
                on_resolve=lambda a: q.put(("pollute_resolve", a)),
                on_pairs=lambda p: q.put(("pollute_pairs", p)),
                on_probe=lambda p: q.put(("pollute_probe", p)))
            ref_ok = sum(1 for v in report.reference.values() if v)
            if ref_ok:
                q.put(("log", f"基准参照：{ref_ok}/{len(domains)} 个域名"
                              f"取到海外解析结果。"))
            else:
                q.put(("log", "基准参照不可用（海外 DoH 在国内链路直连不通），"
                              "已自动退回「本地共识 IP」判定 —— 被多个不同 DNS "
                              "共同返回的地址依然可信。"))
            q.put(("log", f"落地探测：{len(report.probes)} 个 (IP, 域名) 组合，"
                          "每个都走 TCP → TLS 握手 → HTTP 请求 三级，"
                          "失败自动重试一次。"))
            n_ok = len([p for p in report.probes.values()
                        if p.grade == pollution.GRADE_OK])
            n_app = len([p for p in report.probes.values()
                         if p.grade == pollution.GRADE_APPFAIL])
            n_flaky = len([p for p in report.probes.values() if p.flaky])
            q.put(("log", f"三级全通（真正能访问）{n_ok} 个；"
                          f"其中 {n_flaky} 个是重试后才通的。"))
            if n_app:
                q.put(("log", f"另有 {n_app} 个地址 TLS 握手正常、"
                              "但 HTTP 层拿不到响应 —— 这类「握得上打不开」的地址"
                              "已单列，不会被推荐。"))
            q.put(("pollute_done", report))
        except Exception as e:
            import traceback
            q.put(("log", f"污染检测异常：{type(e).__name__}: {e}"))
            q.put(("log", traceback.format_exc().strip()))
            q.put(("pollute_done", None))

    # ---------------------------------------------------------------- 收尾
    def show_report(self, report):
        self.app.set_busy(False)
        if report is None:
            self.var_stage.set("检测未完成")
            self.pb.configure(value=0)
            return
        self.report = report

        by_domain = {}
        for v in report.verdicts:
            by_domain.setdefault(v.domain, []).append(v)

        counts = {}
        for v in report.verdicts:
            counts[v.verdict] = counts.get(v.verdict, 0) + 1

        for domain in self.app.domains:
            vs = by_domain.get(domain, [])
            if not vs:
                continue
            clean = len([v for v in vs if v.verdict == "clean"])
            mixed = len([v for v in vs if v.verdict == "mixed"])
            bad = len([v for v in vs if v.verdict in BAD_VERDICTS])
            dead = len([v for v in vs if v.verdict == "dead"])
            nodata = len([v for v in vs if v.verdict == "nodata"])

            bar = _mini_bar([(clean, th.OK), (mixed, th.WARN), (bad, th.BAD),
                             (dead + nodata, th.MUTE)], width=18)
            ref = report.reference.get(domain) or set()
            ref_txt = f"参考 {len(ref)} 个 IP" if ref else "无基准参照"
            group = self._ensure_group(domain)
            if group and self.tree.exists(group):
                self.tree.item(group, open=(bad + dead > 0), values=(
                    f"{clean + mixed}/{len(vs)} 有效",
                    f"{bar}  污染 {bad} · 不可达 {dead} · 无结果 {nodata}　|　{ref_txt}",
                    ""))

            for v in sorted(vs, key=lambda x: (ORDER.get(x.verdict, 9),
                                               x.ms if x.ms else 9e9, x.dns_name)):
                iid = self._ensure_row(v.domain, v.dns_key, v.dns_name,
                                       v.server, v.kind)
                if iid is None or not self.tree.exists(iid):
                    continue
                ips = ", ".join(v.ips[:3]) + ("…" if len(v.ips) > 3 else "")
                lat = f"{v.ms:.0f} ms" if v.ms else ""
                self.tree.item(
                    iid,
                    text=f"   {MARK.get(v.verdict, '·')} {v.dns_name}  ({v.server})",
                    tags=(TAG.get(v.verdict, "mute"),),
                    values=(f"{MARK.get(v.verdict, '·')} {v.verdict_label}",
                            f"{v.detail}　{lat}",
                            ips or "-"))

        total_v = len(report.verdicts)
        clean_n = counts.get("clean", 0) + counts.get("mixed", 0)
        app_n = counts.get("appfail", 0)
        dirty_n = sum(counts.get(k, 0) for k in BAD_VERDICTS)
        dead_n = counts.get("dead", 0) + counts.get("nodata", 0)

        self.cards["domains"].set(len(self.app.domains),
                                  f"{total_v} 条判定")
        self.cards["clean"].set(clean_n, f"占 {_pct(clean_n, total_v)}")
        self.cards["appfail"].set(app_n,
                                  "TLS 通但 HTTP 无响应" if app_n else "未发现")
        self.cards["dirty"].set(dirty_n, "疑似污染/拦截" if dirty_n else "未发现")
        self.cards["dead"].set(dead_n, "连不上或未返回")

        self.stack.set_segments([
            (counts.get("clean", 0), th.OK, "解析有效"),
            (counts.get("mixed", 0), th.BLUE_300, "部分有效"),
            (counts.get("appfail", 0), "#D9A441", "握得上打不开"),
            (counts.get("hijack", 0), th.BAD, "疑似污染"),
            (counts.get("bogus", 0), "#8F2A2A", "明确拦截"),
            (counts.get("blocked", 0), th.WARN, "疑似阻断"),
            (counts.get("dead", 0) + counts.get("nodata", 0), th.MUTE, "不可达"),
        ])
        self.var_health.set(f"能访问 {clean_n} · 打不开 {app_n} · "
                            f"污染 {dirty_n} · 不可达 {dead_n}")

        self.var_stage.set("检测完成")
        self.pb.configure(value=self.pb["maximum"] or 1)
        self.app.status(f"污染检测完成：{clean_n} 条真正能访问，"
                        f"打不开 {app_n} 条，异常 {dirty_n + dead_n} 条")
        self.app.log(f"污染检测完成：{total_v} 条判定 —— 真正能访问 {clean_n}，"
                     f"握得上打不开 {app_n}，污染 {dirty_n}，不可达 {dead_n}。")
        if report.best_ips:
            self.app.log(f"已为 {len(report.best_ips)} 个域名挑出**三级全通**的 IP"
                         f"（附 HTTP 状态码），可在「hosts 优选」查看并写入。")
        else:
            self.app.log("没有挑出可写 hosts 的地址：需要「TCP + TLS 严格验证 + "
                         "HTTP 响应」三级全通才会被推荐。")

    def update_stage(self, name, done, total):
        self.var_stage.set(name)
        self.pb.configure(maximum=max(1, total), value=done)
        self.var_count.set(f"{done} / {total}")

    # ----------------------------------------------------------------
    def _ctx_info(self):
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        text = self.tree.item(iid, "text").strip()
        if iid.startswith("d:"):
            return (text, ["项目", "判定", "说明", "解析返回"],
                    list(self.tree.item(iid, "values")))
        meta = self._row_meta.get(iid)
        if not meta:
            return None
        domain, dns_key = meta
        v = None
        if self.report:
            v = next((x for x in self.report.verdicts
                      if x.domain == domain and x.dns_key == dns_key), None)
        cols = ["判定", "说明", "解析返回"]
        vals = list(self.tree.item(iid, "values"))
        if v and v.ips:
            cols = cols + ["解析地址"]
            vals = vals + [", ".join(v.ips)]
        return (f"{domain} ← {text}", cols, vals)

    def _on_select(self, _e):
        sel = self.tree.selection()
        if not sel or self.report is None:
            return
        iid = sel[0]
        meta = self._row_meta.get(iid)
        if not meta:
            return
        domain, dns_key = meta
        cand = [v for v in self.report.verdicts
                if v.domain == domain and v.dns_key == dns_key]
        if cand:
            self._set_detail(self._format(cand[0]))

    def _format(self, v):
        L = []
        add = L.append
        add(f"域名        : {v.domain}")
        add(f"DNS 服务    : {v.dns_name}   [{v.dns_group}]")
        add(f"通道        : {v.kind}   地址: {v.server}")
        add(f"查询类型    : {v.qtype_label}")
        add(f"判定        : {v.verdict_label}")
        add(f"说明        : {v.detail}")
        add(f"解析耗时    : {f'{v.ms:.1f} ms' if v.ms else '-'}")
        add("")
        add(f"解析返回地址（{len(v.ips)} 个）")
        add("-" * 74)
        for ip in v.ips:
            add("  " + ip)
        add("")
        add("地址落地探测 — 三级：TCP:443 → TLS 握手 → HTTP 请求")
        add("（只有三级全通才算「真正能访问」；失败会自动重试一次）")
        add("-" * 74)
        if not v.probes:
            add("  （无）")
        for p in sorted(v.probes, key=lambda x: (GRADE_ORDER.get(x.grade, 9), x.ip)):
            line = f"  {p.ip:<42s} {p.grade_label}"
            if p.bogus_reason:
                line += f"  ← {p.bogus_reason}"
            add(line)
            if p.tcp_ms is not None:
                add(f"        TCP 握手  {p.tcp_ms:.0f} ms")
            if p.tls_ms is not None:
                add(f"        TLS 握手  {p.tls_ms:.0f} ms"
                    + ("   （证书链 + SAN 严格验证通过）" if p.verified else ""))
            if p.http_ms is not None:
                code = f"HTTP {p.http_code}" if p.http_code else "拿不到响应"
                add(f"        HTTP 请求 {p.http_ms:.0f} ms  →  {code}")
            elif p.tls_ok and p.http_error:
                add(f"        HTTP 请求失败：{p.http_error}")
            if p.rounds > 1:
                add(f"        探测轮次  {p.rounds} 轮"
                    + ("（重试后才通，链路在抖）" if p.flaky else "（仍未通）"))
            if p.cert_cn or p.cert_sans:
                add(f"        对端证书 CN : {p.cert_cn}")
                if p.cert_sans:
                    shown = p.cert_sans[:6]
                    add(f"        证书 SAN    : {', '.join(shown)}"
                        + (" …" if len(p.cert_sans) > 6 else ""))
                add(f"        SAN 覆盖该域名 : {'是' if p.cert_covers else '否'}")
            if p.error:
                add(f"        错误        : {p.error}")
            add("")
        return "\n".join(L)

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    # ----------------------------------------------------------------
    def edit_domains(self):
        win = tk.Toplevel(self.app)
        win.title("目标域名")
        win.geometry("460x440")
        win.transient(self.app)
        win.configure(background=th.BG_APP)
        self.app.center_window(win)
        tk.Label(win, text="每行一个域名。将对这些域名做解析与落地探测。",
                 font=th.FONT, fg=th.FG_SUB, bg=th.BG_APP).pack(anchor="w",
                                                               padx=14, pady=(14, 6))
        txt = tk.Text(win, font=th.MONO, height=15, relief="solid", borderwidth=1)
        txt.pack(fill="both", expand=True, padx=14)
        txt.insert("1.0", "\n".join(self.app.domains))

        def ok():
            items = [ln.strip().lower() for ln in txt.get("1.0", "end").splitlines()]
            items = [i for i in items if i]
            if not items:
                messagebox.showwarning("空", "至少要有一个域名。", parent=win)
                return
            self.app.domains = items
            self.app._save_config()
            self._update_scope()
            self.app.log(f"目标域名已更新为 {len(items)} 个。")
            win.destroy()

        box = tk.Frame(win, background=th.BG_APP)
        box.pack(fill="x", padx=14, pady=12)
        ttk.Button(box, text="保存", style="Primary.TButton", command=ok
                   ).pack(side="right", padx=4)
        ttk.Button(box, text="取消", command=win.destroy).pack(side="right")
        ttk.Button(box, text="恢复默认", command=lambda: (
            txt.delete("1.0", "end"),
            txt.insert("1.0", "\n".join(d["domain"] for d in dnsdata.DEFAULT_DOMAINS)))
        ).pack(side="left")

    def export_report(self):
        report = self.report
        if report is None:
            messagebox.showinfo("无数据", "还没有污染检测结果。", parent=self.app)
            return
        path = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".csv",
            initialfile=f"dns-pollution-{_time.strftime('%Y%m%d-%H%M%S')}.csv",
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["域名", "DNS服务", "分类", "通道", "解析服务器",
                            "判定", "说明", "解析耗时ms", "返回地址", "地址明细"])
                for v in sorted(report.verdicts, key=lambda x: (x.domain, x.dns_name)):
                    det = "; ".join(
                        f"{p.ip}={p.grade_label}"
                        + (f"(CN={p.cert_cn})" if p.cert_cn else "")
                        for p in v.probes)
                    w.writerow([v.domain, v.dns_name, v.dns_group,
                                channels.KIND_LABEL.get(v.kind, v.kind),
                                v.server,
                                v.verdict_label, v.detail,
                                "" if v.ms is None else round(v.ms, 1),
                                ",".join(v.ips), det])
            self.app.log(f"污染报告已导出：{path}")
            messagebox.showinfo("导出完成", f"已导出 {len(report.verdicts)} 条判定。",
                                parent=self.app)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self.app)


def _pct(a, b):
    return f"{a / b * 100:.0f}%" if b else "—"


def _mini_bar(segs, width=18):
    """用方块字符画一条迷你占比条。"""
    total = sum(v for v, _c in segs) or 1
    chars = []
    used = 0
    for i, (val, _c) in enumerate(segs):
        n = max(0, round(val / total * width))
        if i == len(segs) - 1:
            n = max(0, width - used)
        used += n
        chars.append("█" * n)
    txt = "".join(chars)
    return "[" + txt.ljust(width, "·")[:width] + "]"
