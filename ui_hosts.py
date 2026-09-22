# -*- coding: utf-8 -*-
"""hosts 优选页：把验证过的正确 IP 写进 hosts，并提供体检与一键还原。"""
from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import messagebox, ttk

import hostsmgr
import theme as th

CHECKED = "[√]"
UNCHECKED = "[  ]"


class HostsTab(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, background=th.BG_APP)
        self.app = app
        self.best = {}
        self.checked = {}
        self.row_of = {}
        self._build()

    # ----------------------------------------------------------------
    def _build(self):
        bar = tk.Frame(self, background=th.BG_APP)
        bar.pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(bar, text="全选", command=lambda: self._check_all(True)
                   ).pack(side="left")
        ttk.Button(bar, text="全不选", command=lambda: self._check_all(False)
                   ).pack(side="left", padx=4)
        tk.Label(bar, text="仅采用三级全通（TCP + TLS 严格验证 + HTTP 有响应）的地址",
                 font=th.FONT_SM, fg=th.FG_MUTE, bg=th.BG_APP).pack(side="left", padx=10)
        self.btn_elev = ttk.Button(bar, text="以管理员重启", command=self.relaunch)
        self.btn_elev.pack(side="right")
        # 写入/还原后会自动刷新；这个按钮是给手工改过 hosts 的人准备的
        self.btn_flush = ttk.Button(bar, text="刷新 DNS 缓存",
                                    command=self.flush_cache)
        self.btn_flush.pack(side="right", padx=6)

        cards = tk.Frame(self, background=th.BG_APP)
        cards.pack(fill="x", padx=10, pady=(0, 6))
        self.cards = {}
        for key, label, accent in (
                ("rec", "推荐条目", th.BLUE_600),
                ("conflict", "hosts 冲突", th.WARN),
                ("written", "已由本工具写入", th.OK)):
            c = th.StatCard(cards, label, "—", accent)
            c.pack(side="left", fill="both", expand=True, padx=(0, 8))
            self.cards[key] = c

        body = ttk.PanedWindow(self, orient="vertical")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        top = tk.Frame(body, background=th.BG_APP)
        env_card = tk.Frame(top, background=th.BG_CARD, highlightthickness=1,
                            highlightbackground=th.BORDER)
        env_card.pack(fill="x", pady=(0, 6))
        eh = tk.Frame(env_card, background=th.BG_CARD)
        eh.pack(fill="x", padx=12, pady=(9, 2))
        tk.Label(eh, text="环境体检", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(side="left")
        ttk.Button(eh, text="重新检测", style="CardGhost.TButton",
                   command=self._refresh_env).pack(side="right")
        self.env_text = tk.Text(env_card, height=6, wrap="char", font=th.FONT,
                                background=th.BG_CARD, foreground=th.FG,
                                relief="flat", borderwidth=0, highlightthickness=0)
        self.env_text.pack(fill="x", padx=12, pady=(0, 10))
        self.env_text.configure(state="disabled")
        self.env_text.tag_configure("ok", foreground=th.OK)
        self.env_text.tag_configure("warn", foreground=th.WARN)
        self.env_text.tag_configure("bad", foreground=th.BAD)
        self.env_text.tag_configure("mute", foreground=th.FG_SUB)

        rec_card = tk.Frame(top, background=th.BG_CARD, highlightthickness=1,
                            highlightbackground=th.BORDER)
        rec_card.pack(fill="both", expand=True)
        rh = tk.Frame(rec_card, background=th.BG_CARD)
        rh.pack(fill="x", padx=12, pady=(9, 4))
        tk.Label(rh, text="推荐映射", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(side="left")
        tk.Label(rh, text="双击切换勾选 · 右键可复制 · 只有勾选的会被写入 · "
                          "「三级验证」= 实际拿到的 HTTP 状态码",
                 font=th.FONT_SM, fg=th.FG_MUTE, bg=th.BG_CARD).pack(side="left", padx=10)

        tw = tk.Frame(rec_card, background=th.BG_CARD)
        tw.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.tree = ttk.Treeview(tw,
                                 columns=("ip", "http", "lat", "votes", "src"),
                                 show="tree headings", selectmode="browse", height=7)
        self.tree.heading("#0", text="域名")
        self.tree.heading("ip", text="推荐 IP")
        self.tree.heading("http", text="三级验证")
        self.tree.heading("lat", text="延迟")
        self.tree.heading("votes", text="票数")
        self.tree.heading("src", text="返回该 IP 的 DNS（部分）")
        self.tree.column("#0", width=200, anchor="w")
        self.tree.column("ip", width=190, anchor="w")
        self.tree.column("http", width=90, anchor="center")
        self.tree.column("lat", width=72, anchor="e")
        self.tree.column("votes", width=52, anchor="center")
        self.tree.column("src", width=320, anchor="w")
        self.tree.tag_configure("none", foreground=th.MUTE)
        vs = ttk.Scrollbar(tw, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        tw.rowconfigure(0, weight=1)
        tw.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._toggle)
        th.attach_copy_menu(self.tree, self._ctx_info)
        body.add(top, weight=3)

        bot = tk.Frame(body, background=th.BG_APP)
        act = tk.Frame(bot, background=th.BG_APP)
        act.pack(fill="x", pady=(4, 6))
        ttk.Button(act, text="预览将要写入的内容", command=self.preview).pack(side="left")
        self.btn_write = ttk.Button(act, text="⚠  写入 hosts", style="Warn.TButton",
                                    command=self.write_hosts)
        self.btn_write.pack(side="left", padx=6)
        ttk.Button(act, text="还原 hosts", command=self.restore_hosts).pack(side="left")
        ttk.Button(act, text="打开 hosts 所在目录", command=self.open_dir
                   ).pack(side="left", padx=6)
        ttk.Button(act, text="从备份恢复…", command=self.restore_from_backup
                   ).pack(side="left")

        prev_card = tk.Frame(bot, background=th.BG_CARD, highlightthickness=1,
                             highlightbackground=th.BORDER)
        prev_card.pack(fill="both", expand=True)
        tk.Label(prev_card, text="hosts 现状 / 预览", font=th.FONT_H2, fg=th.BLUE_700,
                 bg=th.BG_CARD).pack(anchor="w", padx=12, pady=(9, 2))
        self.prev = tk.Text(prev_card, height=8, wrap="none", font=th.MONO,
                            background=th.BG_CARD, foreground=th.FG,
                            relief="flat", borderwidth=0, highlightthickness=0)
        psb = ttk.Scrollbar(prev_card, orient="vertical", command=self.prev.yview)
        self.prev.configure(yscrollcommand=psb.set, state="disabled")
        self.prev.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 10))
        psb.pack(side="right", fill="y", pady=(0, 10), padx=(0, 12))
        body.add(bot, weight=2)

    # ----------------------------------------------------------------
    def auto_env_check(self):
        self._refresh_env()

    def _refresh_env(self):
        if not hostsmgr.is_admin():
            self.btn_write.configure(state="disabled")
            self.btn_elev.configure(state="normal")
        else:
            self.btn_write.configure(state="normal")
            self.btn_elev.configure(state="disabled")

        self.env_text.configure(state="normal")
        self.env_text.delete("1.0", "end")

        def put(text, tag="mute"):
            self.env_text.insert("end", text + "\n", tag)

        put(f"hosts 路径：{hostsmgr.HOSTS_PATH}", "mute")
        if hostsmgr.is_admin():
            put("● 管理员权限：已具备，可以写入 hosts", "ok")
        else:
            put("● 管理员权限：没有 —— 写入已禁用，点右下角「以管理员重启」", "warn")

        ports = hostsmgr.detect_local_proxies()
        if ports:
            put(f"● 检测到本地代理/加速器端口：{ports}。若它开了 TUN / 全局模式，"
                f"下面的连通性结果会经过它，不代表直连情况。", "warn")
        else:
            put("● 未检测到本地代理端口。", "ok")

        env = hostsmgr.proxy_env()
        if env:
            put(f"● 代理环境变量：{', '.join(env.keys())}"
                f"（本工具的测速与探测已强制绕过）", "mute")

        conflicts = [e for e in hostsmgr.scan_conflicts(self.app.domains)
                     if e.active and not e.in_block]
        if conflicts:
            put(f"● hosts 中有 {len(conflicts)} 条既有条目会影响目标域名：", "bad")
            put("　 " + "、".join(f"{e.domain}→{e.ip}" for e in conflicts), "warn")
            put("　 写入时它们会被自动注释（可一键还原），否则新映射不会生效。", "warn")
        else:
            put("● hosts 中没有影响目标域名的既有条目。", "ok")

        block = hostsmgr.current_block()
        if block:
            put(f"● 当前已由本工具写入 {len(block)} 条映射。", "ok")
        else:
            put("● 当前 hosts 中没有本工具写入的区块。", "mute")

        self.env_text.configure(state="disabled")

        self.cards["conflict"].set(len(conflicts), "影响目标域名" if conflicts else "无冲突")
        self.cards["written"].set(len(block), "条映射" if block else "尚未写入")
        self.cards["rec"].set(len([d for d in self.best if self.checked.get(d)]),
                              f"共 {len(self.best)} 个域名有推荐")
        self._refresh_preview_text()

    def _refresh_preview_text(self):
        lines = ["— 当前 hosts 中与目标域名相关的条目 " + "—" * 26]
        entries = hostsmgr.scan_conflicts(self.app.domains)
        if not entries:
            lines.append("（无）")
        for e in entries:
            flag = "已注释" if e.disabled else ("本工具" if e.in_block else "生效中")
            lines.append(f"  [{flag}] {e.ip:<38s} {e.domain}")
        lines.append("")
        lines.append("— 本工具的标记区块 " + "—" * 34)
        block = hostsmgr.current_block()
        if not block:
            lines.append("（空）")
        for d, ip in sorted(block.items()):
            lines.append(f"  {ip:<38s} {d}")
        self.prev.configure(state="normal")
        self.prev.delete("1.0", "end")
        self.prev.insert("1.0", "\n".join(lines))
        self.prev.configure(state="disabled")

    # ----------------------------------------------------------------
    def on_report(self, report):
        self.best = {b.domain: b for b in (report.best_ips if report else [])}
        self._fill()
        self._refresh_env()

    def _fill(self):
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        self.row_of.clear()
        for dom in self.app.domains:
            b = self.best.get(dom)
            if not b:
                self.checked[dom] = False
                iid = self.tree.insert(
                    "", "end", text=f"{UNCHECKED} {dom}",
                    values=("— 没有三级全通（TCP+TLS+HTTP）的地址 —",
                            "", "", "", ""),
                    tags=("none",))
                self.row_of[iid] = dom
                continue
            if dom not in self.checked:
                self.checked[dom] = True
            mark = CHECKED if self.checked[dom] else UNCHECKED
            http = f"HTTP {b.http_code}" if b.http_code else "已连通"
            if b.flaky:
                http += " ⚠"           # 重试才通的，提醒一下
            iid = self.tree.insert(
                "", "end", text=f"{mark} {dom}",
                values=(b.ip, http,
                        f"{b.latency_ms:.0f} ms" if b.latency_ms else "—",
                        str(b.votes),
                        ", ".join(b.sources)))
            self.row_of[iid] = dom
        self.cards["rec"].set(len(self._mapping()), f"共 {len(self.best)} 个域名有推荐")

    def _check_all(self, value):
        for dom in self.row_of.values():
            if dom in self.best:
                self.checked[dom] = value
        self._fill()

    def _toggle(self, event):
        iid = self.tree.identify_row(event.y)
        dom = self.row_of.get(iid)
        if not dom or dom not in self.best:
            return
        self.checked[dom] = not self.checked.get(dom, False)
        self.tree.item(iid, text=f"{CHECKED if self.checked[dom] else UNCHECKED} {dom}")
        self.cards["rec"].set(len(self._mapping()), f"共 {len(self.best)} 个域名有推荐")

    def _mapping(self):
        return {dom: b.ip for dom, b in self.best.items() if self.checked.get(dom)}

    def _ctx_info(self):
        sel = self.tree.selection()
        if not sel:
            return None
        dom = self.row_of.get(sel[0])
        b = self.best.get(dom)
        cols = ["域名", "推荐 IP", "三级验证", "延迟", "票数", "来源 DNS"]
        vals = [dom] + list(self.tree.item(sel[0], "values"))
        return (dom or "条目", cols, vals)

    # ----------------------------------------------------------------
    def preview(self):
        m = self._mapping()
        if not m:
            messagebox.showinfo("无内容",
                                "没有勾选任何条目。先去「污染检测」跑一遍，"
                                "或勾选已有推荐。", parent=self.app)
            return
        win = tk.Toplevel(self.app)
        win.title("将要写入 hosts 的内容预览")
        win.geometry("660x440")
        win.transient(self.app)
        win.configure(background=th.BG_APP)
        self.app.center_window(win)
        tk.Label(win, text="以下内容会作为一个带标记的区块追加到 hosts 末尾。\n"
                           "目标域名下已存在的旧条目会被注释掉（不是删除），可一键还原。",
                 font=th.FONT, fg=th.FG_SUB, bg=th.BG_APP, justify="left"
                 ).pack(anchor="w", padx=14, pady=(14, 6))
        txt = tk.Text(win, font=th.MONO, relief="solid", borderwidth=1)
        txt.pack(fill="both", expand=True, padx=14)
        txt.insert("1.0", hostsmgr.preview(m))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=12)

    def write_hosts(self):
        m = self._mapping()
        if not m:
            messagebox.showinfo("无内容", "没有勾选任何条目。", parent=self.app)
            return
        if not hostsmgr.is_admin():
            messagebox.showwarning("需要管理员权限",
                                   "写入 hosts 需要管理员权限。\n"
                                   "请点右下角「以管理员重启」后重试。", parent=self.app)
            return
        conflicts = [e for e in hostsmgr.scan_conflicts(self.app.domains)
                     if e.active and not e.in_block]
        msg = (f"即将把 {len(m)} 条映射写入 hosts：\n\n"
               + "\n".join(f"  {ip}  →  {d}" for d, ip in sorted(m.items()))
               + "\n\n")
        if conflicts:
            msg += (f"另有 {len(conflicts)} 条既有条目会被自动注释（可一键还原）：\n"
                    + "\n".join(f"  {e.ip}  →  {e.domain}" for e in conflicts[:10])
                    + ("\n  …\n" if len(conflicts) > 10 else "\n") + "\n")
        msg += "写入前会自动备份原文件。确认继续？"
        if not messagebox.askyesno("确认写入 hosts", msg, parent=self.app, icon="warning"):
            return
        res = hostsmgr.apply(m)
        self.app.log(("hosts 写入成功：" if res.ok else "hosts 写入失败：") + res.message)
        if res.ok:
            self.app.log("DNS 缓存：" + (res.flush_note or "未刷新"))
        if res.backup_path:
            self.app.log(f"备份文件：{res.backup_path}")
        (messagebox.showinfo if res.ok else messagebox.showerror)(
            "完成" if res.ok else "失败", res.detail(), parent=self.app)
        self._refresh_env()

    def flush_cache(self):
        """手动刷新系统 DNS 缓存。

        写入 / 还原 hosts 之后程序都会自动刷一次；这个入口是留给
        「自己在记事本里改过 hosts」或「想强制重来一次」的情况。
        """
        ok, note = hostsmgr.flush_dns_cache()
        self.app.log(("刷新 DNS 缓存：" if ok else "刷新 DNS 缓存失败：") + note)
        if ok:
            messagebox.showinfo(
                "已刷新", note + "\n\n"
                "注意：浏览器（Chrome / Edge）另有自己的 DNS 缓存，"
                "系统刷新管不到它 —— 若仍访问到旧地址，请重启浏览器。",
                parent=self.app)
        else:
            messagebox.showwarning(
                "刷新失败", note + "\n\n可在命令行手动执行：ipconfig /flushdns",
                parent=self.app)

    def restore_hosts(self):
        if not hostsmgr.is_admin():
            messagebox.showwarning("需要管理员权限", "修改 hosts 需要管理员权限。",
                                   parent=self.app)
            return
        if not messagebox.askyesno(
                "确认还原",
                "将移除本工具写入的标记区块，并还原被注释掉的原有条目。\n\n"
                "其余内容逐字不变。继续？", parent=self.app, icon="warning"):
            return
        res = hostsmgr.restore()
        self.app.log(("hosts 还原成功：" if res.ok else "hosts 还原失败：") + res.message)
        if res.ok:
            self.app.log("DNS 缓存：" + (res.flush_note or "未刷新"))
        if res.backup_path:
            self.app.log(f"备份文件：{res.backup_path}")
        (messagebox.showinfo if res.ok else messagebox.showerror)(
            "完成" if res.ok else "失败", res.detail(), parent=self.app)
        self._refresh_env()

    def restore_from_backup(self):
        backups = hostsmgr.list_backups()
        if not backups:
            messagebox.showinfo("无备份", "还没有任何备份文件。", parent=self.app)
            return
        win = tk.Toplevel(self.app)
        win.title("从备份恢复 hosts")
        win.geometry("640x380")
        win.transient(self.app)
        win.configure(background=th.BG_APP)
        self.app.center_window(win)
        tk.Label(win, text="⚠ 这会用备份文件整体覆盖当前 hosts，"
                           "你在这之后做的其他改动也会丢失。\n"
                           "如果只是想撤销本工具的改动，请用「还原 hosts」。",
                 font=th.FONT, fg=th.BAD, bg=th.BG_APP, justify="left"
                 ).pack(anchor="w", padx=14, pady=(14, 6))
        lb = tk.Listbox(win, font=th.MONO, relief="solid", borderwidth=1,
                        selectbackground=th.BG_SEL, selectforeground=th.FG)
        for b in backups:
            lb.insert("end", os.path.basename(b))
        lb.pack(fill="both", expand=True, padx=14)

        def do():
            sel = lb.curselection()
            if not sel:
                return
            src = backups[sel[0]]
            if not messagebox.askyesno(
                    "最后确认",
                    f"用下面这个备份整体覆盖 hosts？\n\n{os.path.basename(src)}\n\n"
                    "此操作不可撤销。", parent=win, icon="warning"):
                return
            try:
                safe = hostsmgr.backup_hosts("before-overwrite")
                shutil.copy2(src, hostsmgr.HOSTS_PATH)
                self.app.log(f"已用备份覆盖 hosts：{src}（覆盖前备份：{safe}）")
                # 整体覆盖同样是改了 hosts，必须刷新缓存
                self.flush_after_overwrite()
                messagebox.showinfo("完成", "已恢复。", parent=win)
                win.destroy()
                self._refresh_env()
            except Exception as e:
                messagebox.showerror("失败", str(e), parent=win)

        box = tk.Frame(win, background=th.BG_APP)
        box.pack(fill="x", padx=14, pady=12)
        ttk.Button(box, text="恢复", style="Warn.TButton", command=do
                   ).pack(side="right", padx=4)
        ttk.Button(box, text="取消", command=win.destroy).pack(side="right")

    def flush_after_overwrite(self):
        """整体覆盖 hosts 之后的收尾：刷缓存（失败只记日志，不打断流程）。"""
        ok, note = hostsmgr.flush_dns_cache()
        self.app.log(("DNS 缓存：" if ok else "DNS 缓存刷新失败：") + note)

    def open_dir(self):
        try:
            os.startfile(os.path.dirname(hostsmgr.HOSTS_PATH))
        except Exception as e:
            messagebox.showerror("打开失败", str(e), parent=self.app)

    def relaunch(self):
        if hostsmgr.relaunch_as_admin():
            self.app.log("已发起提权重启，请在 UAC 弹窗中确认。")
            self.app._save_config()
            self.app.destroy()
        else:
            messagebox.showerror(
                "提权失败", "无法自动提权。请关闭本程序后，右键以「管理员身份运行」。",
                parent=self.app)
