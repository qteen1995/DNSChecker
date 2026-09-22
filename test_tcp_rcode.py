# -*- coding: utf-8 -*-
"""验证本轮四条：汉字响应码、TCP 通道、右键复制用的字段、图标定义齐全。"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import channels
import dnsdata
import dnsproto as P

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


print("---- ① 响应码中文化 ----")


def rcode_map():
    out = []
    for rc in range(6):
        out.append(f"{rc}={P.rcode_cn(rc)}({P.RCODE_NAMES[rc]})")
    return "  ".join(out)


step("rcode_cn 映射", rcode_map)
step("未定义码兜底", lambda: P.rcode_cn(99))


def live_refused():
    """实测一台只服务教育网的 DNS，确认状态列显示「拒绝」。"""
    r = P.query_udp("101.6.6.6", "www.baidu.com", P.QTYPE_A, 53, 3.0)
    if not r.ok:
        return f"（本轮无应答：{r.error}，跳过）"
    s = channels.SpeedResult(key="k", kind="udp4", name="清华 TUNA", group="高校",
                             server="101.6.6.6", port=53, display="101.6.6.6")
    s.rcode = r.rcode
    s.ok = True
    s.best_ms = r.total_ms
    s.samples = [r.total_ms]
    assert s.status == "拒绝", f"期望「拒绝」，实际「{s.status}」"
    return f"udp rcode={r.rcode} → 状态列「{s.status}」，详情「{s.rcode_cn}（{s.rcode_name}）」"


step("REAL：REFUSED 显示为「拒绝」", live_refused)


def real_tcp_refused():
    r = P.query_tcp("101.6.6.6", "www.baidu.com", P.QTYPE_A, 53, 3.0)
    if not r.ok:
        return f"（TCP 无应答：{r.error}，跳过）"
    s = channels.SpeedResult(key="k", kind="tcp4", name="清华 TUNA", group="高校",
                             server="101.6.6.6", port=53, display="101.6.6.6")
    s.rcode = r.rcode
    s.ok = True
    s.samples = [r.total_ms]
    return f"tcp rcode={r.rcode} → 状态列「{s.status}」"


step("REAL：TCP 通道同样识别 REFUSED", real_tcp_refused)

print()
print("---- ② TCP 通道 ----")

step("KIND_LABEL", lambda: channels.KIND_LABEL)
step("KIND_ORDER", lambda: channels.KIND_ORDER)

entries = [dict(e) for e in dnsdata.DEFAULT_ENTRIES]
eps = list(dnsdata.iter_endpoints(entries))
step("端点总数", lambda: len(eps))


def per_kind():
    from collections import Counter
    c = Counter(k for _k, k, _p in eps)
    return "  ".join(f"{channels.KIND_LABEL[k]}={c[k]}" for k in channels.KIND_ORDER)


step("各通道端点数", per_kind)
step("key 唯一", lambda: (
    "唯一" if len({k for k, _k, _p in eps}) == len(eps) else "!!! 有重复"))


def real_udp_vs_tcp():
    """8.8.8.8：上轮实测 UDP 超时、TCP 通。两条通道都要能看到。"""
    lines = []
    for kind in ("udp4", "tcp4"):
        s = channels.SpeedResult(key="k", kind=kind, name="Google", group="国外",
                                 server="8.8.8.8", port=53, display="8.8.8.8")
        res = channels._query_once(kind, {"server": "8.8.8.8", "port": 53},
                                   "www.baidu.com")
        s.ok = res.ok
        s.rcode = res.rcode
        s.error = res.error
        s.best_ms = res.total_ms
        s.samples = [res.total_ms] if res.ok else [None]
        lat = f"{s.best_ms:.0f}ms" if s.best_ms else "—"
        lines.append(f"{channels.KIND_LABEL[kind]}: {s.status} {lat}"
                     + (f"  建连{res.connect_ms:.0f}ms" if res.connect_ms else ""))
    return "  |  ".join(lines)


step("REAL：8.8.8.8 的 UDP vs TCP", real_udp_vs_tcp)


def tcp_includes_handshake():
    r = P.query_tcp("119.29.29.29", "www.baidu.com", P.QTYPE_A, 53, 3.0)
    if not r.ok:
        return f"（腾讯 DNS TCP 无应答：{r.error}）"
    return (f"connect={r.connect_ms:.1f}ms rtt={r.rtt_ms:.1f}ms "
            f"total={r.total_ms:.1f}ms（total 已含握手）")


step("REAL：TCP 延迟含三次握手", tcp_includes_handshake)

print()
print("---- ③ 通道分发 ----")


def dispatch():
    got = []
    for kind in ("udp4", "tcp4", "udp6", "tcp6", "dot", "doh"):
        try:
            r = channels._query_once(
                kind, {"server": "127.0.0.1", "port": 9, "url": "x"}, "a.b")
            got.append(f"{kind}={r.error}")
        except Exception as e:
            got.append(f"{kind}=!!{type(e).__name__}")
    return "  ".join(got)


step("_query_once 六条通道均可分派", dispatch)

print()
print("---- ④ 污染引擎认 TCP ----")
import pollution


def pollution_tcp():
    t = [{"key": "k1", "kind": "tcp4",
          "payload": {"name": "阿里 AliDNS", "group": "国内",
                      "server": "223.5.5.5", "port": 53, "display": "223.5.5.5"}}]
    rep = pollution.run_check(t, ["github.com"], use_reference=False)
    if not rep.verdicts:
        return "！！没有判定"
    v = rep.verdicts[0]
    return f"{v.kind} 判定={v.verdict_label} 地址={v.ips[:2]}"


step("REAL：污染检测走 tcp4 端点", pollution_tcp)

print()
print("---- ⑥ 非 0 响应码一律算「不可用」----")


def mk(rcode=0, ms=20.0, ok=True):
    r = channels.SpeedResult(key="k", kind="udp4", name="X", group="国内",
                             server="1.1.1.1", port=53, display="1.1.1.1")
    r.ok, r.best_ms, r.rcode = ok, (ms if ok else None), rcode
    r.samples = [r.best_ms] if ok else [None]
    return r


def usable_matrix():
    out = []
    for label, rc in (("正常", 0), ("格式错误", 1), ("服务器故障", 2),
                      ("域名不存在", 3), ("未实现", 4), ("拒绝", 5)):
        r = mk(rcode=rc)
        out.append(f"{label}:{'可用' if r.usable else '不可用'}")
    r = mk(rcode=None, ok=False, ms=None)
    out.append(f"超时:{'可用' if r.usable else '不可用'}")
    return "  ".join(out)


step("ok / usable 是两个概念", usable_matrix)


def refused_sinks():
    """拒绝的服务器延迟再漂亮也不能占前排。"""
    rows = sorted([mk(rcode=5, ms=5.0), mk(rcode=0, ms=300.0),
                   mk(rcode=0, ms=12.0)], key=lambda x: x.sort_key())
    order = [f"{r.best_ms:.0f}ms/{'可用' if r.usable else '不可用'}" for r in rows]
    assert rows[-1].rcode == 5, "拒绝的没沉底"
    return "排序后 -> " + " < ".join(order)


step("拒绝的行沉底（尽管它最快）", refused_sinks)


def status_text():
    """状态列前缀：● 可用 / ✕ 有响应但不可用 / ○ 无响应。"""
    out = []
    for label, r in (("可用", mk(rcode=0, ms=12)),
                     ("拒绝", mk(rcode=5, ms=12)),
                     ("超时", mk(rcode=None, ok=False, ms=None))):
        mark = "●" if r.usable else ("✕" if r.ok else "○")
        out.append(f"{label}→{mark} {r.status}")
    return "  ".join(out)


step("状态列前缀", status_text)

print()
print("---- ⑦ 图标定义 ----")
import theme as th

step("ICON_KEYS", lambda: th.ICON_KEYS)
step("图标都在 ICON_KEYS 里", lambda: (
    "齐全" if not [k for k in th.ICON_KEYS
                   if f'key == "{k}"' not in open(
                       os.path.join(HERE, "theme.py"), encoding="utf-8").read()]
    else "!! 缺 " + str([k for k in th.ICON_KEYS
                         if f'key == "{k}"' not in open(
                             os.path.join(HERE, "theme.py"),
                             encoding="utf-8").read()])))
step("未知图标名会记账（不再静默留白）", lambda: (
    "有 UNKNOWN_ICON_KEYS" if hasattr(th, "UNKNOWN_ICON_KEYS")
    else "!! 缺 UNKNOWN_ICON_KEYS"))


def every_icon_draws():
    """每个图标名都真的能在 Canvas 上画出东西。

    `cv.find_all()` 是核对自绘控件的最低成本手段 —— 比肉眼看截图可靠。
    """
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    empty = []
    for k in th.ICON_KEYS:
        cv = tk.Canvas(root, width=18, height=18)
        th.draw_icon(cv, k, 1, 1, 18, "#185FA5")
        if not cv.find_all():
            empty.append(k)
    root.destroy()
    assert not empty, f"这些图标名画不出东西：{empty}"
    return f"{len(th.ICON_KEYS)} 个图标全部有笔迹"


step("每个 ICON_KEYS 都能画出东西", every_icon_draws)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
