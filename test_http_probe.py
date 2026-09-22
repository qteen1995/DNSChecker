# -*- coding: utf-8 -*-
"""三级落地探测（TCP → TLS → HTTP）与「真正能访问」判定验证。

分两部分：
  A. 纯逻辑（打桩，快且确定）—— 分类、重试、判定、推荐 IP 的取舍
  B. 真实网络 —— 拿几个已知地址验证三级探测确实跑通、HTTP 码确实拿到
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import dnsproto as P
import pollution as PL

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


def mk_probe(ip, dom, grade, *, flaky=False, http=None, latency=20.0,
             tcp=True, tls=True):
    return PL.IpProbe(ip=ip, domain=dom, grade=grade, tcp_ok=tcp,
                      tcp_ms=latency / 3, tls_ms=latency / 3 if tls else None,
                      tls_ok=tls, http_ok=http is not None, http_code=http,
                      http_ms=latency / 3 if http is not None else None,
                      flaky=flaky, verified=(grade == PL.GRADE_OK))


def mk_answer(dom, ips, key="k1", name="测试 DNS"):
    a = PL.ResolveAnswer(dns_key=key, dns_name=name, dns_group="国内",
                         kind="udp4", server="1.1.1.1", domain=dom, qtype=1,
                         qtypes=[1])
    a.ok = True
    a.ips = list(ips)
    a.ms = 10.0
    return a


print("=" * 74)
print("A. 纯逻辑：分类 / 重试 / 判定 / 推荐取舍")
print("=" * 74)


def classify_via_stub():
    """把 HTTP 那一层打桩，验证分类确实按「HTTP 通不通」分。"""
    real = P._probe_once

    def fake_ok(ip, domain, port, timeout, path, *a, **kw):
        p = P.TlsProbe(ip=ip, domain=domain, tcp_ok=True, tcp_ms=10,
                       tls_ok=True, tls_ms=20, verified=True)
        p.http_ok, p.http_code, p.http_ms = True, 200, 30
        p.grade = "ok"
        return p

    def fake_appfail(ip, domain, port, timeout, path, *a, **kw):
        p = P.TlsProbe(ip=ip, domain=domain, tcp_ok=True, tcp_ms=10,
                       tls_ok=True, tls_ms=20, verified=True)
        p.http_ms, p.http_error = 4000, "Timeout"
        p.grade = "appfail"
        p.error = "TLS 握手正常，但应用层拿不到响应（Timeout）"
        return p

    try:
        P._probe_once = fake_ok
        ok = P.probe_site("1.2.3.4", "example.com", 443, 3.0, "/")
        P._probe_once = fake_appfail
        bad = P.probe_site("1.2.3.4", "example.com", 443, 3.0, "/",
                           retries=0)
    finally:
        P._probe_once = real
    assert ok.grade == "ok" and ok.http_code == 200, ok
    assert bad.grade == "appfail", f"TLS 通但 HTTP 不通应当是 appfail，实际 {bad.grade}"
    return "HTTP 通→ok / TLS 通但 HTTP 不通→appfail"


step("分类以 HTTP 层为准", classify_via_stub)


def retry_rescues():
    """第一轮不通、第二轮通 → 应判 ok 且标记 flaky。"""
    real = P._probe_once
    calls = {"n": 0}

    def flaky_once(ip, domain, port, timeout, path, *a, **kw):
        calls["n"] += 1
        p = P.TlsProbe(ip=ip, domain=domain, tcp_ok=True, tcp_ms=10)
        if calls["n"] == 1:
            p.error = "Reset"
            p.grade = "dead"
            return p
        p.tls_ok = p.verified = p.http_ok = True
        p.tls_ms, p.http_ms, p.http_code = 20, 30, 200
        p.grade = "ok"
        return p

    try:
        P._probe_once = flaky_once
        p = P.probe_site("1.2.3.4", "example.com", 443, 3.0, "/", retries=1)
    finally:
        P._probe_once = real
    assert p.grade == "ok", f"重试后应当救回，实际 {p.grade}"
    assert p.flaky and p.attempts == 2 and p.rounds == 2, \
        f"应标记 flaky，实际 flaky={p.flaky} attempts={p.attempts} rounds={p.rounds}"
    return (f"第 2 轮救回：grade={p.grade} flaky={p.flaky} "
            f"attempts={p.attempts} rounds={p.rounds}")


step("失败重试能救回（标记为波动）", retry_rescues)


def retry_gives_more_http_time():
    """重试轮的 HTTP 超时必须是第一轮的两倍 —— 「慢但能通」不该被错杀。"""
    real = P._probe_once
    seen = []

    def spy(ip, domain, port, timeout, path, http_timeout=None, *a, **kw):
        seen.append(http_timeout)
        p = P.TlsProbe(ip=ip, domain=domain, tcp_ok=True, tcp_ms=10)
        p.http_error, p.grade = "Timeout", "appfail"
        return p

    try:
        P._probe_once = spy
        P.probe_site("1.2.3.4", "example.com", 443, 3.0, "/", retries=1,
                     http_timeout=4.0)
    finally:
        P._probe_once = real
    assert seen == [4.0, 8.0], f"两轮 HTTP 超时应为 [4.0, 8.0]，实际 {seen}"
    return f"两轮 HTTP 超时 = {seen}"


step("重试轮放宽 HTTP 超时", retry_gives_more_http_time)


def no_useless_retry():
    """第一轮就通 → 不该再花时间重试。"""
    real = P._probe_once
    calls = {"n": 0}

    def once(ip, domain, port, timeout, path, *a, **kw):
        calls["n"] += 1
        p = P.TlsProbe(ip=ip, domain=domain, tcp_ok=True, tcp_ms=10,
                       tls_ok=True, tls_ms=20, verified=True, http_ok=True,
                       http_ms=30, http_code=200, grade="ok")
        return p

    try:
        P._probe_once = once
        p = P.probe_site("1.2.3.4", "example.com", 443, 3.0, "/", retries=1)
    finally:
        P._probe_once = real
    assert calls["n"] == 1, f"通了的地址不该重试，实际探测了 {calls['n']} 轮"
    return f"只探测 {calls['n']} 轮，flaky={p.flaky}"


step("一轮就通的不重试", no_useless_retry)

print()
print("--- 判定与推荐（aggregate）---")


def case_appfail_only():
    """只有「握手可过但打不开」的地址：既不能说解析有效，也不该推荐。"""
    dom = "github.com"
    ans = mk_answer(dom, ["10.0.0.1", "10.0.0.2"])
    _pairs, freq = PL.collect_probe_pairs([ans])
    probes = {(ip, dom): mk_probe(ip, dom, PL.GRADE_APPFAIL, latency=4000)
              for ip in ("10.0.0.1", "10.0.0.2")}
    verdicts, _c, best = PL.aggregate([ans], probes, freq, {})
    v = verdicts[0]
    assert v.verdict == PL.VERDICT_APPFAIL, f"期望 appfail，实际 {v.verdict}"
    assert not best, f"打不开的地址不该被推荐，实际推荐了 {best}"
    return f"判定={v.verdict_label}，推荐 0 个（{v.detail}）"


step("TLS 通但 HTTP 不通 → 判「握得上打不开」且不推荐", case_appfail_only)


def case_prefer_stable():
    """稳定通过的地址要优先于「重试才通」的地址，哪怕后者延迟更低。"""
    dom = "github.com"
    ans = mk_answer(dom, ["10.0.0.1", "10.0.0.2"])
    _pairs, freq = PL.collect_probe_pairs([ans])
    probes = {
        (("10.0.0.1"), dom): mk_probe("10.0.0.1", dom, PL.GRADE_OK,
                                      flaky=True, http=200, latency=5.0),
        (("10.0.0.2"), dom): mk_probe("10.0.0.2", dom, PL.GRADE_OK,
                                      http=200, latency=300.0),
    }
    verdicts, _c, best = PL.aggregate([ans], probes, freq, {})
    assert best and best[0].ip == "10.0.0.2", \
        f"应收敛到稳定地址，实际 {best[0].ip if best else '无'}"
    assert verdicts[0].verdict in (PL.VERDICT_CLEAN, PL.VERDICT_MIXED)
    assert "重试" in verdicts[0].detail, verdicts[0].detail
    return (f"5ms 但波动 vs 300ms 但稳定 → 选 {best[0].ip}"
            f"（{best[0].latency_ms:.0f}ms）")


step("稳定优先于「重试才通」", case_prefer_stable)


def case_mixed():
    """真的能用 + 握得上打不开 混在一起 → 部分有效。"""
    dom = "pypi.org"
    ans = mk_answer(dom, ["10.0.0.1", "10.0.0.2"])
    _pairs, freq = PL.collect_probe_pairs([ans])
    probes = {
        (("10.0.0.1"), dom): mk_probe("10.0.0.1", dom, PL.GRADE_OK, http=200),
        (("10.0.0.2"), dom): mk_probe("10.0.0.2", dom, PL.GRADE_APPFAIL),
    }
    verdicts, _c, best = PL.aggregate([ans], probes, freq, {})
    v = verdicts[0]
    assert v.verdict == PL.VERDICT_MIXED, f"期望 mixed，实际 {v.verdict}"
    assert best and best[0].ip == "10.0.0.1"
    return f"判定={v.verdict_label}，推荐 {best[0].ip}"


step("能用的 + 打不开的混合 → 部分有效", case_mixed)


def case_hijack_still_wins():
    """有伪造证据时不能被「打不开」掩盖。"""
    dom = "github.com"
    ans = mk_answer(dom, ["10.0.0.1", "10.0.0.2"])
    _pairs, freq = PL.collect_probe_pairs([ans])
    probes = {
        (("10.0.0.1"), dom): mk_probe("10.0.0.1", dom, PL.GRADE_APPFAIL),
        (("10.0.0.2"), dom): mk_probe("10.0.0.2", dom, PL.GRADE_HIJACK),
    }
    verdicts, _c, _b = PL.aggregate([ans], probes, freq, {})
    assert verdicts[0].verdict == PL.VERDICT_HIJACK, verdicts[0].verdict
    return f"判定={verdicts[0].verdict_label}（污染信号优先）"


step("污染信号优先级高于「打不开」", case_hijack_still_wins)

print()
print("=" * 74)
print("B. 真实网络：三级探测跑通")
print("=" * 74)


def first_ok(domain, want=3):
    """用阿里 DNS 解析，逐个 IP 探，返回第一个三级全通的结果。

    被墙站点的 IP 是**间歇性**可用的，作为回归测试的目标不稳定；
    所以断言用国内大站（基本必通），墙外站点只作参考记录。
    """
    r = P.query_udp("223.5.5.5", domain, P.QTYPE_A, 53, 3.0)
    ips = list(r.answers) if r.ok else []
    tried = []
    for ip in ips[:want]:
        p = P.probe_site(ip, domain, 443, 4.0)
        tried.append((ip, p))
        if p.grade == "ok":
            return p, tried
    return None, tried


def real_ok():
    p, tried = first_ok("www.baidu.com")
    assert p is not None, f"国内大站三级都没通？{[(i, x.grade) for i, x in tried]}"
    assert p.http_ok and p.http_code, f"HTTP 层没通：{p.http_error}"
    assert p.verified, "TLS 严格验证没通过"
    return (f"www.baidu.com → {p.ip}  HTTP {p.http_code}  "
            f"tcp={p.tcp_ms:.0f} tls={p.tls_ms:.0f} http={p.http_ms:.0f}ms")


step("REAL：可稳定访问的站点三级全通", real_ok)


def real_appfail_or_note():
    """找一个「TLS 通但 HTTP 拿不到响应」的真实案例（找不到就如实说明）。

    这类地址在不同时刻可能表现不同，所以只作观察，不作断言。
    """
    for dom in ("github.com", "raw.githubusercontent.com",
                "objects.githubusercontent.com"):
        r = P.query_udp("223.5.5.5", dom, P.QTYPE_A, 53, 3.0)
        if not r.ok:
            continue
        for ip in list(r.answers)[:3]:
            p = P.probe_site(ip, dom, 443, 4.0)
            if p.grade == "appfail":
                return (f"抓到实例：{ip} / {dom} — TLS {p.tls_ms:.0f}ms 通了，"
                        f"HTTP {p.rounds} 轮都拿不到响应（{p.http_error}）")
    return "本轮没抓到这类实例（它是瞬时状态，不是每轮都有）"


step("REAL：观察「握手可过但打不开」", real_appfail_or_note)


def real_404_is_ok():
    """根路径 404 也必须是「可用」——状态码代表策略，不代表能不能访问。"""
    p, tried = first_ok("www.baidu.com")
    assert p is not None, "基准站点都不通，跳过"
    # 直接对一个已知会返回 404 的路径发请求，验证「非 2xx 也算通」
    code, err, ms = None, None, 0
    import socket as _s
    import ssl as _ssl
    s = _s.create_connection((p.ip, 443), 4.0)
    ctx = _ssl.create_default_context()
    ctx.set_alpn_protocols(["http/1.1"])
    ss = ctx.wrap_socket(s, server_hostname="www.baidu.com")
    code, err, ms = P._read_http_code(ss, "www.baidu.com",
                                      "/definitely-not-here-404", 5.0)
    ss.close()
    assert code is not None, f"404 路径也应当拿到状态行，实际 {err}"
    assert code >= 400, f"期望 4xx，实际 {code}"
    return f"请求不存在的路径拿到 HTTP {code} —— 非 2xx 同样算「能访问」"


step("REAL：非 2xx 状态码也判「可用」", real_404_is_ok)


def real_dead():
    p = P.probe_site("127.0.0.1", "github.com", 443, 1.0, retries=0)
    assert p.grade == "dead", f"回环地址应当是 dead，实际 {p.grade}"
    return f"grade={p.grade} error={p.error}"


step("REAL：连不上的地址判 dead", real_dead)


def real_bogus():
    r = P.is_bogus_ip("0.0.0.0")
    r2 = P.is_bogus_ip("127.0.0.1")
    assert r and r2, (r, r2)
    return f"0.0.0.0→{r} 127.0.0.1→{r2}"


step("REAL：拦截地址不进入探测", real_bogus)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
