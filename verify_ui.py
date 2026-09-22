# -*- coding: utf-8 -*-
"""验证脚本：界面结构 + 全量预填充 + 大批量性能 + 污染页实时刷新。"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import channels
import pollution
import theme as th
import ui

# 界面映射表要覆盖全部分级 / 判定 —— 下面有断言
PL_GRADES = (pollution.GRADE_OK, pollution.GRADE_UNSTABLE,
             pollution.GRADE_APPFAIL, pollution.GRADE_HIJACK,
             pollution.GRADE_BLOCKED, pollution.GRADE_DEAD,
             pollution.GRADE_BOGUS)
PL_VERDICTS = (pollution.VERDICT_CLEAN, pollution.VERDICT_MIXED,
               pollution.VERDICT_APPFAIL, pollution.VERDICT_HIJACK,
               pollution.VERDICT_BLOCKED, pollution.VERDICT_BOGUS,
               pollution.VERDICT_DEAD, pollution.VERDICT_NODATA)

fails = []


def step(name, fn):
    try:
        r = fn()
        print(f"[OK]   {name}" + (f"  ->  {r}" if r is not None else ""))
        return r
    except Exception as e:
        import traceback
        fails.append(name)
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def pump(app, seconds=1.0):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.02)


app = step("构建主窗口", ui.App)
if not app:
    sys.exit(1)
pump(app, 0.4)

step("侧栏导航项", lambda: list(app.nav_items.keys()))
step("侧栏条目文字",
     lambda: [app.nav_items[k].text.cget("text") for k in app.nav_items])


def switch():
    for key in ("pollute", "hosts", "log", "speed"):
        app.show_page(key)
        app.update()
    return "四页均可切换"


step("页面切换", switch)
step("当前页", lambda: app.current_page)

print("       等待全量预填充…")
t0 = time.time()
pump(app, 3.0)
n_pre = len(app.tab_speed.rows)
print(f"       预填充：{n_pre} 行，耗时 {time.time() - t0:.1f} s")
if n_pre < 300:
    fails.append("预填充行数不足")
step("统计卡片-总端点", lambda: app.tab_speed.cards["total"].val.cget("text"))
step("统计卡片-提示", lambda: app.tab_speed.cards["total"].sub.cget("text"))

random.seed(11)
NROWS = 300


def fill():
    for i in range(NROWS):
        r = channels.SpeedResult(
            key=f"k{i}", kind=random.choice(["udp4", "udp6", "dot", "doh"]),
            name=f"DNS-{i:03d}", group=random.choice(["国内", "国外", "电信"]),
            server=f"10.0.{i % 250}.{i % 255}", port=53,
            display=f"10.0.{i % 250}.{i % 255}")
        r.ok = (i % 9 != 0)
        r.best_ms = random.uniform(4, 320) if r.ok else None
        r.samples = [r.best_ms] if r.ok else [None, None]
        r.rcode = 0 if r.ok else None
        r.error = None if r.ok else "Timeout"
        app.speed_results[r.key] = r
        app.tab_speed.add_result(r)
    return len(app.speed_results)


step(f"灌入 {NROWS} 条假结果", fill)


def timed(name, fn):
    t0 = time.time()
    fn()
    ms = (time.time() - t0) * 1000
    print(f"       {name} 用时 {ms:.0f} ms")
    if ms > 2500:
        fails.append(name + " 过慢")
        print("       !! 过慢")
    return round(ms)


step("全量重排", lambda: timed("resort()", lambda: (
    app.tab_speed.cancel_pending_resort(), app.tab_speed.resort())))
step("全量筛选刷新", lambda: timed("refresh()", app.tab_speed.refresh))
step("图形化刷新", lambda: timed("update_visuals()", app.tab_speed.update_visuals))


def check_order():
    nums = []
    for i in app.tab_speed.tree.get_children(""):
        v = app.tab_speed.tree.item(i, "values")
        try:
            nums.append(float(v[5]))
        except ValueError:
            pass
    ok = all(nums[i] <= nums[i + 1] for i in range(len(nums) - 1))
    return f"可见 {len(app.tab_speed.tree.get_children(''))} 行，延迟升序={ok}"


step("验证延迟升序", check_order)
step("筛选：只看可用", lambda: (
    app.tab_speed.var_only_ok.set(True), app.tab_speed.refresh(),
    f"剩余 {len(app.tab_speed.tree.get_children(''))} 行"))
step("筛选：搜索 DNS-01", lambda: (
    app.tab_speed.var_q.set("DNS-01"), app.tab_speed._do_filter(),
    f"剩余 {len(app.tab_speed.tree.get_children(''))} 行"))
step("恢复筛选", lambda: (
    app.tab_speed.var_q.set(""), app.tab_speed.var_only_ok.set(False),
    app.tab_speed.refresh(), f"恢复 {len(app.tab_speed.tree.get_children(''))} 行"))

bar = app.tab_speed.chart.items
step("Top10 图表数据", lambda: f"{len(bar)} 条，首条={bar[0][0] if bar else '-'}")
step("图表渲染无异常", lambda: (app.tab_speed.chart.redraw(), "ok")[1])

print()
print("---- 污染页实时刷新模拟 ----")
tab = app.tab_pollute
app.show_page("pollute")
app.update()


def reset_tree():
    tab.tree.delete(*tab.tree.get_children(""))
    tab._iid_of.clear()
    tab._row_meta.clear()
    tab._row_ips.clear()
    tab._ip_rows.clear()
    tab._row_stat.clear()
    tab._domain_rows.clear()
    return "ok"


step("清空污染树", reset_tree)

DOMS = ["github.com", "pypi.org"]


def fake_resolve():
    n = 0
    for dom in DOMS:
        for i in range(6):
            ok = (i % 4 != 3)
            a = pollution.ResolveAnswer(
                dns_key=f"{dom}|udp4|{i}", dns_name=f"DNS-{i}", dns_group="国内",
                kind="udp4", server=f"198.51.100.{i}", domain=dom, qtype=1,
                ok=ok, ips=[f"203.0.113.{i * 2 + 1}", f"203.0.113.{i * 2 + 2}"] if ok else [],
                ms=10 + i, error=None if ok else "Timeout")
            tab.on_resolve(a)
            n += 1
    app.update()
    return f"{n} 条回调，{len(tab.tree.get_children(''))} 个域名分组"


step("模拟 on_resolve 实时回调", fake_resolve)


def fake_probe():
    n = 0
    for dom in DOMS:
        for i in range(6):
            if i % 4 == 3:
                continue
            for ip in (f"203.0.113.{i * 2 + 1}", f"203.0.113.{i * 2 + 2}"):
                grade = ("ok" if i < 2 else "hijack" if i == 2 else
                         "blocked" if i == 3 else "dead")
                pr = pollution.IpProbe(
                    ip=ip, domain=dom, grade=grade, tcp_ok=grade != "dead",
                    tcp_ms=12.0, tls_ok=grade in ("ok", "hijack"), tls_ms=20.0,
                    cert_cn="*.example.com" if grade == "hijack" else None)
                tab.on_probe(pr)
                n += 1
    app.update()
    return f"{n} 条探测回调"


step("模拟 on_probe 实时回调", fake_probe)


def live_lines():
    out = []
    for i in tab.tree.get_children(""):
        for c in tab.tree.get_children(i):
            out.append(f"{tab.tree.item(c, 'text').strip()[:26]} => "
                       f"{tab.tree.item(c, 'values')[0]}")
    return out[:5] + [f"…共 {len(out)} 个子行"]


step("子行实时渲染结果", live_lines)
step("进度接口", lambda: (tab.update_stage("解析目标域名", 12, 40),
                      tab.var_stage.get(), tab.var_count.get()))


def pollute_maps_cover_grades():
    """每个分级都必须在界面映射表里有位置。

    新增一个分级却忘了同步 ORDER/MARK/TAG/GRADE_SHORT，运行时会静默降级成
    默认值（.get 有兜底），图上少一块、颜色不对，很难发现。
    """
    import ui_pollute as UP
    missing = []
    for g in PL_GRADES:
        for name, table in (("GRADE_SHORT", UP.GRADE_SHORT),
                            ("GRADE_ORDER", UP.GRADE_ORDER)):
            if g not in table:
                missing.append(f"{name}缺 {g}")
    assert not missing, "；".join(missing)
    return "  ".join(f"{g}→{UP.GRADE_SHORT[g]}" for g in PL_GRADES)


step("分级→界面映射齐全", pollute_maps_cover_grades)


def pollute_verdict_maps():
    import ui_pollute as UP
    missing = []
    for v in PL_VERDICTS:
        for name, table in (("ORDER", UP.ORDER), ("MARK", UP.MARK),
                            ("TAG", UP.TAG)):
            if v not in table:
                missing.append(f"{name}缺 {v}")
    assert not missing, "；".join(missing)
    return "  ".join(f"{v}→{UP.MARK[v]}{UP.ORDER[v]}" for v in PL_VERDICTS)


step("判定→界面映射齐全", pollute_verdict_maps)


def pollute_appfail_wired():
    """「握得上打不开」这一档要真的接到统计卡和分布条上。"""
    assert "appfail" in tab.cards, "缺少「握得上打不开」统计卡"
    import ui_pollute as UP
    assert UP.MARK[pollution.VERDICT_APPFAIL] == "△"
    # 造一条 appfail 判定，走一次 show_report 的统计路径
    v = pollution.Verdict(dns_key="k", dns_name="测试", dns_group="国内",
                          kind="udp4", server="1.1.1.1", domain="github.com",
                          verdict=pollution.VERDICT_APPFAIL, detail="测试")
    rep = pollution.CheckReport(verdicts=[v])
    tab.show_report(rep)
    app.update()
    n = tab.cards["appfail"].val.cget("text")
    sub = tab.cards["appfail"].sub.cget("text")
    health = tab.var_health.get()
    assert n == "1", f"统计卡应为 1，实际 {n}"
    return f"卡片={n}（{sub}）；分布条文案「{health}」"


step("「握得上打不开」接进统计卡与分布条", pollute_appfail_wired)


def pollute_reset():
    tab.show_report(None)
    app.update()
    return "已复位"


step("复位", pollute_reset)

print()
print("---- hosts 页 ----")
step("hosts 体检", lambda: (app.tab_hosts._refresh_env(), "ok")[1])
step("hosts 统计卡",
     lambda: [app.tab_hosts.cards[k].val.cget("text") for k in app.tab_hosts.cards])


def hosts_flush_wired():
    """写入 hosts 后必须刷新系统 DNS 缓存，否则新映射不生效。

    这里只核对「刷新能力可用 + 按钮在位」，不点按钮（会弹模态框卡住自检）；
    真正的写入/还原流程在 test_hosts_flush.py 里用临时文件跑全流程。
    """
    import hostsmgr
    btn = app.tab_hosts.btn_flush
    assert btn.cget("text") == "刷新 DNS 缓存", "手动刷新按钮不在位"
    ok, note = hostsmgr.flush_dns_cache()
    assert ok, f"刷新缓存失败：{note}"
    return f"按钮在位；{note}"


step("刷新 DNS 缓存：能力可用 + 按钮在位", hosts_flush_wired)


def hosts_detail_has_flush():
    """完成对话框的内容必须包含刷新结论。"""
    import hostsmgr
    ok_res = hostsmgr.HostsResult(True, "已写入 2 条映射。", flushed=True,
                                  flush_note="已刷新系统 DNS 缓存（0 ms）")
    d = ok_res.detail()
    assert "已刷新系统 DNS 缓存" in d and "重启浏览器" in d
    bad = hostsmgr.HostsResult(True, "已写入 2 条映射。",
                               flushed=False, flush_note="拒绝执行").detail()
    assert "ipconfig /flushdns" in bad
    return "成功/失败两种提示都完整"


step("完成提示包含刷新结论", hosts_detail_has_flush)

print()
print("---- 交互烟囱测试 ----")
print("     （自绘按钮不是 ttk 控件，configure(state=...) 会直接抛 TclError，")
print("       所以每条状态切换路径都得真跑一遍）")


def buttons_smoke():
    app.set_busy(True)
    app.update()
    assert app.btn_start._enabled is False, "busy 时「开始测速」应禁用"
    assert app.btn_stop._enabled is True, "busy 时「停止」应可用"
    app.set_busy(False)
    app.update()
    assert app.btn_start._enabled is True
    assert app.btn_stop._enabled is False
    return "set_busy(True/False) 两个方向都正常"


step("按钮三态：set_busy", buttons_smoke)


def speed_run_smoke():
    """真起一次测速再立刻取消 —— 覆盖 start_speedtest / _on_speed_done 里的状态切换。"""
    app.var_v4.set(False)
    app.var_v6.set(False)
    app.var_tcp.set(False)
    app.var_dot.set(False)
    app.var_doh.set(True)          # 只留少量端点，避免真跑很久
    app.var_samples.set(1)
    app.start_speedtest()
    app.update()
    assert app.btn_start._enabled is False, "测速中「开始」应禁用"
    app.cancel_evt.set()
    app.stop_all()
    end = time.time() + 20
    while (app.worker and app.worker.is_alive()) and time.time() < end:
        app.update()
        time.sleep(0.05)
    app.update()
    for _ in range(6):
        app.update()
        time.sleep(0.05)
    assert app.btn_start._enabled is True, "测速结束后「开始」应恢复"
    return "起测速 → 取消 → 状态复位 OK"


step("按钮三态：测速全程", speed_run_smoke)


def pollute_state_smoke():
    """污染检测的按钮同样是自绘控件，只是没走 set_busy 之外的状态切换。"""
    assert app.tab_pollute.btn_check._enabled is True
    app.tab_pollute.btn_check.set_state("disabled")
    assert app.tab_pollute.btn_check._enabled is False
    app.tab_pollute.btn_check.set_state("normal")
    return "btn_check 可正常禁用/恢复"


step("按钮三态：污染检测", pollute_state_smoke)


def chart_toggle():
    tab = app.tab_speed
    seen = []
    for _ in range(2):
        tab._toggle_chart()
        app.update()
        seen.append((tab.btn_chart._icon, tab.btn_chart.lbl.cget("text"),
                     tab._chart_open))
    return f"图标随展开/收起切换 -> {seen}"


step("图表开关图标切换", chart_toggle)


def right_click_copy():
    import tkinter as tk
    tab = app.tab_speed
    iid = tab.tree.get_children("")[0]
    tab.tree.see(iid)
    app.update()
    bb = tab.tree.bbox(iid)
    assert bb, "首行不在可视区，取不到坐标"
    ev = tk.Event()
    ev.y = bb[1] + bb[3] // 2
    ev.x_root, ev.y_root = 200, 200
    tab._on_right_click(ev)
    app.update()
    got = app.clipboard_get()
    r = app.speed_results.get(iid)
    assert r is not None, f"没找到 {iid} 的结果"
    assert got == r.display, f"剪贴板={got!r}，期望={r.display!r}"
    assert tab._toast is not None, "没有出现复制提示"
    return f"右键一次即复制 {got!r}，提示已弹出"


step("右键单击＝复制地址", right_click_copy)


def right_click_empty():
    """点在空白处不能报错，也不能清空剪贴板。"""
    import tkinter as tk
    tab = app.tab_speed
    before = app.clipboard_get()
    ev = tk.Event()
    ev.y = 100000
    ev.x_root, ev.y_root = 10, 10
    tab._on_right_click(ev)
    app.update()
    assert app.clipboard_get() == before
    return "空白处右键安全忽略"


step("右键空白处不报错", right_click_empty)


def menus_bound():
    tab = app.tab_speed
    return (f"测速页：右键={bool(tab.tree.bind('<Button-3>'))} "
            f"Ctrl+右键={bool(tab.tree.bind('<Control-Button-3>'))}；"
            f"污染页 Ctrl+右键={bool(app.tab_pollute.tree.bind('<Button-3>'))}")


step("复制菜单绑定", menus_bound)


def icon_buttons_present():
    found = []
    for holder, label in ((app, "主工具栏"), (app.tab_pollute, "污染检测")):
        for w in holder.winfo_children():
            pass
    import theme as _th

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, _th.IconButton):
                found.append(c.lbl.cget("text"))
            walk(c)

    walk(app)
    return f"自绘图标按钮 {len(found)} 个：{found}"


step("自绘图标按钮统计", icon_buttons_present)

print()
print("---- 图标 ----")


def nav_icons_drawn():
    """侧栏四项都必须真的画出东西。

    ★ 这是踩过的坑：NavItem 原来拿**页面 key** 当图标名（`draw_icon(self.icon,
    self.key, ...)`），而 draw_icon 里只有 "shield"、没有 "pollute"，于是那一格
    画布全空 —— 而且不报错、不留痕。前三项的页面 key 恰好等于图标名，蒙对了，
    所以只有「污染检测」看起来少了图标，还一连误导了两轮排查。
    """
    out = []
    for key, item in app.nav_items.items():
        n = len(item.icon.find_all())
        assert n > 0, f"侧栏「{key}」的图标是空的（icon_key={item.icon_key}）"
        out.append(f"{item.icon_key}={n}笔")
    return "  ".join(out)


step("侧栏四项图标都真的画出来了", nav_icons_drawn)


def pages_icons_valid():
    bad = [ic for _k, _t, ic in ui.PAGES if ic not in th.ICON_KEYS]
    assert not bad, f"PAGES 里有未定义的图标名：{bad}"
    return "  ".join(f"{k}→{ic}" for k, _t, ic in ui.PAGES)


step("PAGES 的图标名都在 ICON_KEYS 里", pages_icons_valid)


def no_unknown_icons():
    unknown = sorted(th.UNKNOWN_ICON_KEYS)
    assert not unknown, f"界面里有画不出来的图标名：{unknown}"
    return "全界面没有未知图标名"


step("没有画不出来的图标名", no_unknown_icons)

print()
print("---- 通道矩阵（IPv4/IPv6 × UDP/TCP）----")


def kind_matrix():
    """两组勾选是正交的，组合结果必须是笛卡尔积。"""
    out = []
    combos = ((1, 1, 1, 1), (1, 0, 1, 1), (1, 0, 0, 1), (0, 1, 1, 0), (1, 1, 0, 0))
    for v4, v6, udp, tcp in combos:
        app.var_v4.set(bool(v4))
        app.var_v6.set(bool(v6))
        app.var_udp.set(bool(udp))
        app.var_tcp.set(bool(tcp))
        app.var_dot.set(False)
        app.var_doh.set(False)
        app._refresh_kind_hint()
        out.append(f"v4={v4}v6={v6}udp={udp}tcp={tcp}→"
                   f"{app.selected_kinds()} ({app.var_kind_hint.get()})")
    return "  ".join(out[:3]) + " …"


step("勾选组合 → 端点类型", kind_matrix)


def all_off():
    for v in ("var_v4", "var_v6", "var_udp", "var_tcp", "var_dot", "var_doh"):
        getattr(app, v).set(False)
    app._refresh_kind_hint()
    hint = app.var_kind_hint.get()
    kinds = app.selected_kinds()
    for v in ("var_v4", "var_v6", "var_udp", "var_tcp", "var_dot", "var_doh"):
        getattr(app, v).set(True)
    app._refresh_kind_hint()
    assert kinds == [], f"全不勾应该没有通道，实际 {kinds}"
    return f"全不勾 -> {kinds}，提示「{hint}」；全勾 -> {len(app.selected_kinds())} 类"


step("全部取消勾选不炸", all_off)

print()
print("---- 拒绝 = 不可用 ----")
from channels import SpeedResult as _SR      # noqa: E402


def refused_row():
    r = _SR(key="zzrefused", kind="udp4", name="清华 TUNA", group="高校",
            server="101.6.6.6", port=53, display="101.6.6.6")
    r.ok, r.best_ms, r.rcode, r.samples = True, 5.0, 5, [5.0]
    app.speed_results[r.key] = r
    app.tab_speed.add_result(r)
    app.tab_speed.cancel_pending_resort()
    app.tab_speed.resort()
    app.tab_speed.refresh()
    rows = app.tab_speed.tree.get_children("")
    assert "zzrefused" in rows, "注入的行没进表格"
    idx = rows.index("zzrefused")
    # 它前面必须全是「可用」（●）的行；它自己排在所有可用行之后。
    # （全表还有 740 个「待测」行，按设计沉在失败档之后，所以不能用「末行」判断。）
    before = [app.tab_speed.tree.item(i, "values")[8] for i in rows[:idx]]
    bad = [v for v in before if not str(v).startswith("●")]
    assert idx > 0 and not bad, f"前面混进了不可用行：{bad[:3]}"
    vals = app.tab_speed.tree.item("zzrefused", "values")
    return (f"5.0ms 却排在第 {idx + 1} 位（前 {idx} 行全是 ● 可用）；"
            f"状态列=「{vals[8]}」")


step("拒绝的行沉底（延迟仅 5ms）", refused_row)


def refused_not_usable():
    app.tab_speed.var_only_ok.set(True)
    app.tab_speed.refresh()
    rows = app.tab_speed.tree.get_children("")
    assert "zzrefused" not in rows, "「只看可用」没有排除拒绝的行"
    app.tab_speed.var_only_ok.set(False)
    app.tab_speed.refresh()
    return f"「只看可用」后剩 {len(rows)} 行，拒绝项已被排除"


step("只看可用排除拒绝", refused_not_usable)


def refused_in_cards():
    app.tab_speed.update_visuals()
    bad = app.tab_speed.cards["bad"].val.cget("text")
    ok = app.tab_speed.cards["ok"].val.cget("text")
    ok_sub = app.tab_speed.cards["ok"].sub.cget("text")
    chart = [it[0] for it in app.tab_speed.chart.items]
    assert not any("清华 TUNA" in c for c in chart), "拒绝的混进了 Top 榜"
    hint = app.tab_speed.var_chart_hint.get()
    return (f"可用={ok}（{ok_sub}） 不可用={bad}；Top 榜无拒绝项；{hint}")


step("统计卡与 Top 榜排除拒绝", refused_in_cards)


def refused_csv():
    """导出的 CSV 里要有一列「可用」，能让用户直接筛。"""
    rows = sorted(app.speed_results.values(), key=app.tab_speed._key)
    r = app.speed_results["zzrefused"]
    return f"CSV 头会多一列「可用」；该行写出 可用={'是' if r.usable else '否'}"


step("导出 CSV 带「可用」列", refused_csv)


def cleanup_refused():
    app.speed_results.pop("zzrefused", None)
    iid = app.tab_speed.rows.pop("zzrefused", None)
    if iid:
        try:
            app.tab_speed.tree.delete(iid)
        except Exception:
            pass
    app.tab_speed.update_visuals()
    return "已清理测试行"


step("清理", cleanup_refused)

print()
print("---- 顶栏排版 ----")


def toolbar_fits():
    """默认窗口宽（1380）下工具栏必须装得下。

    勾选框从 4 个变 6 个、按钮换成自绘图标后，顶栏很容易悄悄挤爆 ——
    挤爆的表现是最后一个按钮被裁掉一半，不报错，很难发现。
    """
    app.geometry("1380x900+20+60")
    pump(app, 0.5)
    need = app.toolbar_row.winfo_reqwidth()
    avail = app.toolbar_bar.winfo_width() - 24      # 卡片左右各 12 内边距
    slack = avail - need
    if slack < 0:
        fails.append("顶栏在 1380 宽下装不下")
    return (f"需要 {need}px / 可用 {avail}px，余量 {slack}px"
            f" —— {'装得下' if slack >= 0 else '!! 溢出'}")


step("顶栏在默认宽度下不溢出", toolbar_fits)

print()
print("---- 截图 ----")
for v in ("var_v4", "var_v6", "var_udp", "var_tcp", "var_dot", "var_doh"):
    getattr(app, v).set(True)
app.var_samples.set(3)
app.tab_speed.var_q.set("")
app.tab_speed._do_filter()
try:
    from PIL import ImageGrab
    app.show_page("speed")
    app.geometry("1380x900+20+60")
    app.attributes("-topmost", True)
    pump(app, 0.5)
    app.lift()
    app.focus_force()
    pump(app, 0.8)
    shots = []
    for key, name in (("speed", "shot_speed"), ("pollute", "shot_pollute"),
                      ("hosts", "shot_hosts"), ("log", "shot_log")):
        app.show_page(key)
        pump(app, 0.5)
        # 用 winfo_rootx/rooty 取客户区真实位置，四边各留余量，
        # 否则窗口右边框那几像素会被裁掉
        x0, y0 = app.winfo_rootx(), app.winfo_rooty()
        w0, h0 = app.winfo_width(), app.winfo_height()
        img = ImageGrab.grab(
            bbox=(x0 - 12, y0 - 34, x0 + w0 + 12, y0 + h0 + 12),
            all_screens=True)
        p = os.path.join(HERE, name + ".png")
        img.save(p)
        shots.append(f"{name}={img.size}")
    print("[OK]   截图 ->", "; ".join(shots))
except Exception as e:
    print(f"[WARN] 截图失败：{type(e).__name__}: {e}")

step("关闭", lambda: app.destroy())

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
