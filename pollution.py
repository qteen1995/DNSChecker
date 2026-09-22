# -*- coding: utf-8 -*-
"""污染 / 可达性判定引擎。

分三段：

  段 A｜解析      —— 用每个 DNS 去解析目标域名，收集返回的 IP 集合
  段 B｜落地探测  —— 把所有 DNS 返回的 IP **按 (IP, 域名) 去重**，逐个做
                     TCP:443 → TLS 握手（SNI = 目标域名，严格校验证书）
  段 C｜归因      —— 把探测结果贴回每个 DNS，判定它是「解析有效」还是「被污染」

为什么以 TLS 证书为铁证：
    证书由站点真实 CA 签发，劫持方伪造不了（除非在你机器上装了根证书做 MITM）。
    所以「严格验证通过」= 这个 IP 上真的跑着那个站点；
    「TCP 通但证书不对」= 有人在中间冒充。

基准参照（两层，互相兜底）：
    1. 共识 IP —— 本地统计，被多个不同 DNS 共同返回的 IP 更可能是真的（永远可用）
    2. 海外 DoH —— Cloudflare / Google / Quad9 / DNS.SB 的解析结果并集
       （国内链路可能连不上，连不上就自动跳过并标注）
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

import dnsproto as P

# 单个地址的分级。探测是三级：TCP → TLS(严格) → HTTP。
# 「可用」的门槛落在 **HTTP 层拿到响应** 上 —— 不只是握手成功。
GRADE_OK = "ok"              # TCP 通 + TLS 严格验证 + HTTP 拿到响应 —— 真正能访问
GRADE_UNSTABLE = "unstable"  # 证书如实匹配域名，只是这一把 TLS 没走通 —— 真身，链路不稳
GRADE_APPFAIL = "appfail"    # TLS 握手正常但应用层拿不到响应 —— 握得上、打不开
GRADE_HIJACK = "hijack"      # 证书与该域名不符 —— 疑似劫持 / 中间人
GRADE_BLOCKED = "blocked"    # TCP 通但 TLS 被中断且抓不到证书 —— 疑似阻断
GRADE_DEAD = "dead"          # TCP 根本连不上
GRADE_BOGUS = "bogus"        # 保留 / 回环 / 内网地址 —— 明确拦截

GRADE_LABEL = {
    GRADE_OK: "可用",
    GRADE_UNSTABLE: "可用(不稳)",
    GRADE_APPFAIL: "握手可过但打不开",
    GRADE_HIJACK: "疑似劫持",
    GRADE_BLOCKED: "疑似阻断",
    GRADE_DEAD: "不可达",
    GRADE_BOGUS: "明确拦截",
}

VERDICT_CLEAN = "clean"        # 解析有效：返回的地址至少有一个真能承载该域名
VERDICT_MIXED = "mixed"        # 部分有效（混杂了不可用地址）
VERDICT_HIJACK = "hijack"      # 证书不符，疑似污染
VERDICT_BLOCKED = "blocked"    # TLS 被中断，疑似阻断
VERDICT_APPFAIL = "appfail"    # TLS 通但应用层打不开 —— 地址真实但当前线路访问不了
VERDICT_BOGUS = "bogus"        # 返回回环 / 内网 / 黑洞地址 —— 明确拦截
VERDICT_DEAD = "dead"          # 返回了地址但一个都连不上
VERDICT_NODATA = "nodata"      # 没有解析结果

VERDICT_LABEL = {
    VERDICT_CLEAN: "解析有效",
    VERDICT_MIXED: "部分有效",
    VERDICT_HIJACK: "疑似污染",
    VERDICT_BLOCKED: "疑似阻断",
    VERDICT_APPFAIL: "握得上打不开",
    VERDICT_BOGUS: "明确拦截",
    VERDICT_DEAD: "结果不可达",
    VERDICT_NODATA: "无解析结果",
}

REFERENCE_DOHS = [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query",
    "https://dns.quad9.net/dns-query",
    "https://doh.sb/dns-query",
    "https://dns.adguard.com/dns-query",
]

# DoT 和 DoH 在这件事上完全等价：都是加密查询通道、都能绕开明文劫持。
# 两条通道都留着是因为可通性随线路而变 —— 实测本机 DoH 有时能通、DoT 全被重置，
# 换个网络可能反过来。多一个源就多一次把基准建起来的机会。
REFERENCE_DOTS = [
    "one.one.one.one",
    "dns.google",
    "dns.quad9.net",
    "dot.sb",
    "dns.adguard.com",
]

# 基准参照只试前 N 个候选 IP：它只关心"这个源通不通"，
# 遍历全部候选纯属浪费（海外源全不通时尤其明显）。
REF_MAX_CANDIDATES = 2

MAX_IPS_PER_DOMAIN = 48      # 单个域名最多探测多少个不同 IP，防止极端情况炸开
CONSENSUS_RATIO = 0.10       # 被 ≥10% 的 DNS 返回 → 算共识 IP

# 三级探测的重试次数。实测链路波动很大（同一 IP 三轮可能是 http/dead/dead，
# 也可能 TLS 通了但 HTTP 连试两次都不通），单次采样会把「在抖」误判成「不通」、
# 把「握得上但打不开」错当成「可用」。失败重试 1 次能同时压掉这两类误判。
PROBE_RETRIES = 1
CONSENSUS_MIN = 3


# --------------------------------------------------------------------------
# 数据容器
# --------------------------------------------------------------------------
@dataclass
class ResolveAnswer:
    dns_key: str
    dns_name: str
    dns_group: str
    kind: str
    server: str
    domain: str
    qtype: int
    ok: bool = False
    ips: List[str] = field(default_factory=list)
    cnames: List[str] = field(default_factory=list)
    qtypes: List[int] = field(default_factory=list)   # 合并后这条记录覆盖的查询类型
    rcode: Optional[int] = None
    ms: Optional[float] = None
    error: Optional[str] = None

    def merge(self, other: "ResolveAnswer") -> None:
        """把同一 DNS 对同一域名的另一次查询结果并进来（A + AAAA）。

        早先是直接 `buckets[key] = a` 覆盖，导致后到的 AAAA 把 A 结果整个吃掉 ——
        而 github.com / store.steampowered.com 这类域名本来就没有 AAAA 记录，
        于是桶里只剩空结果，判定全变成「无解析结果」。
        """
        self.ok = self.ok or other.ok
        for ip in other.ips:
            if ip not in self.ips:
                self.ips.append(ip)
        for cn in other.cnames:
            if cn not in self.cnames:
                self.cnames.append(cn)
        for qt in (other.qtypes or [other.qtype]):
            if qt not in self.qtypes:
                self.qtypes.append(qt)
        if other.ok and other.rcode == 0:
            self.rcode = 0                       # 只要有一次 NOERROR 就算通
        elif self.rcode is None:
            self.rcode = other.rcode
        if other.ms is not None and (self.ms is None or other.ms < self.ms):
            self.ms = other.ms
        if not other.ok and self.error is None:
            self.error = other.error


@dataclass
class IpProbe:
    ip: str
    domain: str
    grade: str = GRADE_DEAD
    bogus_reason: Optional[str] = None
    tcp_ok: bool = False
    tcp_ms: Optional[float] = None
    tls_ok: bool = False
    tls_ms: Optional[float] = None
    verified: bool = False
    # 第三级：HTTP。只有这一层通了才算「真正能访问」
    http_ok: bool = False
    http_code: Optional[int] = None
    http_ms: Optional[float] = None
    http_error: Optional[str] = None
    attempts: int = 1
    rounds: int = 1
    flaky: bool = False
    cert_cn: Optional[str] = None
    cert_sans: List[str] = field(default_factory=list)
    cert_covers: bool = False
    error: Optional[str] = None

    @property
    def latency_ms(self) -> Optional[float]:
        """端到端耗时（三级全算上）—— 这才是「访问这个地址要等多久」。"""
        if not self.tcp_ok:
            return None
        return ((self.tcp_ms or 0.0) + (self.tls_ms or 0.0)
                + (self.http_ms or 0.0))

    @property
    def stage(self) -> str:
        """这三级走到哪一步断了，给详情面板用。"""
        if self.http_ok:
            return f"HTTP {self.http_code}"
        if not self.tcp_ok:
            return "TCP 不通"
        if not self.tls_ok:
            return "TLS 未通过"
        return "HTTP 无响应"

    @property
    def grade_label(self) -> str:
        return GRADE_LABEL.get(self.grade, self.grade)


@dataclass
class Verdict:
    """某个 DNS 对某个域名的最终判定。"""
    dns_key: str
    dns_name: str
    dns_group: str
    kind: str
    server: str
    domain: str
    ips: List[str] = field(default_factory=list)
    probes: List[IpProbe] = field(default_factory=list)
    verdict: str = VERDICT_NODATA
    detail: str = ""
    ms: Optional[float] = None
    qtypes: List[int] = field(default_factory=list)

    @property
    def qtype_label(self) -> str:
        names = {1: "A", 28: "AAAA"}
        qs = self.qtypes or [1]
        return " + ".join(names.get(q, str(q)) for q in sorted(qs))

    @property
    def verdict_label(self) -> str:
        return VERDICT_LABEL.get(self.verdict, self.verdict)

    @property
    def usable_count(self) -> int:
        return len([p for p in self.probes if p.grade == GRADE_OK])

    @property
    def max_tls_ms(self) -> Optional[float]:
        vals = [p.latency_ms for p in self.probes if p.grade == GRADE_OK and p.latency_ms]
        return min(vals) if vals else None


@dataclass
class BestIp:
    """给某个域名挑选出的推荐 IP（用于写 hosts）。"""
    domain: str
    ip: str
    latency_ms: Optional[float]
    votes: int                        # 有多少个 DNS 返回过它
    grade: str = GRADE_OK
    flaky: bool = False               # 重试后才通过 —— 链路在抖
    http_code: Optional[int] = None   # 实际拿到的 HTTP 状态码
    sources: List[str] = field(default_factory=list)

    @property
    def grade_label(self) -> str:
        return GRADE_LABEL.get(self.grade, self.grade)


@dataclass
class CheckReport:
    answers: List[ResolveAnswer] = field(default_factory=list)
    probes: Dict[Tuple[str, str], IpProbe] = field(default_factory=dict)
    verdicts: List[Verdict] = field(default_factory=list)
    reference: Dict[str, Set[str]] = field(default_factory=dict)
    reference_sources: Dict[str, List[str]] = field(default_factory=dict)
    best_ips: List[BestIp] = field(default_factory=list)
    consensus: Dict[str, Set[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------
# 段 0：基准参照
# --------------------------------------------------------------------------
def build_reference(domains: Sequence[str],
                    dohs: Sequence[str] = REFERENCE_DOHS,
                    dots: Sequence[str] = REFERENCE_DOTS,
                    cancel=None, timeout: float = 2.5,
                    on_progress: Optional[Callable[[int, int], None]] = None
                    ) -> Tuple[Dict[str, Set[str]], Dict[str, List[str]]]:
    """用海外加密 DNS（DoH + DoT 两条通道）建立「参考真实 IP 集」。

    并发单位是「一个源」。每个源**先用第一个域名探路**，不通就直接放弃它 ——
    海外源在国内大多是全程不通，不做这层短路的话，10 个源各自去等
    「域名数 × 候选 IP 数」次超时，光空转就要 20 多秒。探路策略把这段压到 5 秒内。

    全部源都连不上时，参考集为空 —— 此时判定自动退回到「本地共识 IP」，
    结果依然可用（实测 GitHub 的真实 IP 就是靠共识统计认出来的）。
    """
    domains = list(domains)
    sources = [("doh", u) for u in dohs] + [("dot", h) for h in dots]
    ips: Dict[str, Set[str]] = defaultdict(set)
    srcs: Dict[str, List[str]] = defaultdict(list)
    done = 0

    def query_src(kind, target, dom):
        if kind == "doh":
            return P.query_doh(target, dom, P.QTYPE_A, timeout=timeout,
                               max_candidates=REF_MAX_CANDIDATES)
        return P.query_dot(target, dom, P.QTYPE_A, timeout=timeout,
                           max_candidates=REF_MAX_CANDIDATES)

    def work(src):
        kind, target = src
        got: List[Tuple[str, List[str]]] = []
        if not domains or (cancel is not None and cancel.is_set()):
            return kind, target, got

        # 探路：第一个域名不通 → 这个源在当前线路就是不可用，直接收工
        r0 = query_src(kind, target, domains[0])
        if not r0.ok:
            return kind, target, got
        got.append((domains[0], list(r0.answers)))

        fails = 0
        for dom in domains[1:]:
            if cancel is not None and cancel.is_set():
                break
            r = query_src(kind, target, dom)
            if r.ok:
                got.append((dom, list(r.answers)))
                fails = 0
            else:
                fails += 1
                if fails >= 2:          # 连着两个域名失败，说明线路不稳，不再等
                    break
        return kind, target, got

    ex = ThreadPoolExecutor(max_workers=max(1, len(sources)))
    try:
        futs = {ex.submit(work, s): s for s in sources}
        for fut in as_completed(futs):
            if cancel is not None and cancel.is_set():
                break
            done += 1
            if on_progress:
                on_progress(done, len(sources))
            kind, target = futs[fut]
            label = f"{kind.upper()} {target}"
            try:
                _k, _t, got = fut.result()
            except Exception:
                got = []
            for dom, addrs in got:
                for ip in addrs:
                    if not P.is_bogus_ip(ip):
                        ips[dom].add(ip)
                if label not in srcs[dom]:
                    srcs[dom].append(label)
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            ex.shutdown(wait=False)
    return dict(ips), dict(srcs)


# --------------------------------------------------------------------------
# 段 A：解析
# --------------------------------------------------------------------------
def _resolve_one(target: dict, domain: str, qtype: int) -> Optional[ResolveAnswer]:
    pl = target["payload"]
    a = ResolveAnswer(dns_key=target["key"], dns_name=pl.get("name", "?"),
                      dns_group=pl.get("group", "未分类"), kind=target["kind"],
                      server=pl.get("server", "?"), domain=domain, qtype=qtype,
                      qtypes=[qtype])
    try:
        kind = target["kind"]
        if kind in ("udp4", "udp6"):
            r = P.query_udp(pl["server"], domain, qtype, pl.get("port", 53), P.UDP_TIMEOUT)
        elif kind in ("tcp4", "tcp6"):
            r = P.query_tcp(pl["server"], domain, qtype, pl.get("port", 53), P.TCP_TIMEOUT)
        elif kind == "dot":
            r = P.query_dot(pl["server"], domain, qtype, 853, P.DOT_TIMEOUT)
        elif kind == "doh":
            r = P.query_doh(pl["server"], domain, qtype, P.DOH_TIMEOUT)
        else:
            return None
    except Exception as e:
        a.error = type(e).__name__
        return a
    a.ok = r.ok
    a.ips = list(r.answers)
    a.cnames = list(r.cnames)
    a.rcode = r.rcode
    a.ms = r.total_ms
    a.error = r.error
    return a


def resolve_all(targets: Sequence[dict], domains: Sequence[str],
                qtypes: Sequence[int] = (P.QTYPE_A,),
                workers: int = 64, cancel=None,
                on_progress: Optional[Callable[[int, int], None]] = None,
                on_result: Optional[Callable[[ResolveAnswer], None]] = None
                ) -> List[ResolveAnswer]:
    """并发单位是「一个 DNS」，而不是「一次查询」。

    每个 DNS 连续处理全部目标域名，一旦它连第一个域名都答不上来就直接收工 ——
    国内环境下一大批海外 DNS 都是全程超时，这个短路能省掉大量无谓等待。

    on_result 会在工作线程里逐个回传解析结果，界面靠它做实时刷新。
    """
    out: List[ResolveAnswer] = []
    done = 0

    def work(t):
        if cancel is not None and cancel.is_set():
            return []
        res: List[ResolveAnswer] = []
        for dom in domains:
            if cancel is not None and cancel.is_set():
                break
            for qt in qtypes:
                a = _resolve_one(t, dom, qt)
                if a is not None:
                    res.append(a)
            if not any(x.ok for x in res):
                break                      # 这个 DNS 不通，后面的域名不用试了
        return res

    ex = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        futs = [ex.submit(work, t) for t in targets]
        for fut in as_completed(futs):
            if cancel is not None and cancel.is_set():
                break
            done += 1
            if on_progress:
                on_progress(done, len(targets))
            try:
                got = fut.result()
            except Exception:
                got = []
            for a in got:
                out.append(a)
                if on_result is not None:
                    on_result(a)
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            ex.shutdown(wait=False)
    return out


# --------------------------------------------------------------------------
# 段 B：落地探测
# --------------------------------------------------------------------------
def collect_probe_pairs(answers: Sequence[ResolveAnswer]
                        ) -> Tuple[List[Tuple[str, str]], Dict[str, Counter]]:
    """把解析结果摊平成待探测的 (ip, domain) 去重列表。

    单个域名超过 MAX_IPS_PER_DOMAIN 时，按被多少 DNS 返回过的频次降序截断。
    """
    per_domain: Dict[str, Counter] = defaultdict(Counter)
    for a in answers:
        if not a.ok:
            continue
        for ip in a.ips:
            per_domain[a.domain][ip] += 1

    pairs: List[Tuple[str, str]] = []
    seen = set()
    for dom, freq in per_domain.items():
        for ip, _n in freq.most_common(MAX_IPS_PER_DOMAIN):
            if (ip, dom) not in seen:
                seen.add((ip, dom))
                pairs.append((ip, dom))
    return pairs, per_domain


def probe_all(pairs: Sequence[Tuple[str, str]], workers: int = 96, cancel=None,
              on_progress: Optional[Callable[[int, int], None]] = None,
              timeout: float = 3.0,
              on_result: Optional[Callable[[IpProbe], None]] = None
              ) -> Dict[Tuple[str, str], IpProbe]:
    out: Dict[Tuple[str, str], IpProbe] = {}
    done = 0

    def work(pair):
        ip, dom = pair
        if cancel is not None and cancel.is_set():
            return None
        reason = P.is_bogus_ip(ip)
        if reason:
            return IpProbe(ip=ip, domain=dom, grade=GRADE_BOGUS, bogus_reason=reason)
        # 三级探测：TCP → TLS(严格) → HTTP，失败自动重试一次
        tls = P.probe_site(ip, dom, 443, timeout, P.HTTP_PATH, PROBE_RETRIES,
                           P.HTTP_TIMEOUT)
        return IpProbe(ip=ip, domain=dom, grade=tls.grade, tcp_ok=tls.tcp_ok,
                       tcp_ms=tls.tcp_ms, tls_ok=tls.tls_ok, tls_ms=tls.tls_ms,
                       verified=tls.verified, http_ok=tls.http_ok,
                       http_code=tls.http_code, http_ms=tls.http_ms,
                       http_error=tls.http_error, attempts=tls.attempts,
                       rounds=tls.rounds, flaky=tls.flaky, cert_cn=tls.cert_cn,
                       cert_sans=tls.cert_sans, cert_covers=tls.cert_covers,
                       error=tls.error)

    ex = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        futs = [ex.submit(work, p) for p in pairs]
        for fut in as_completed(futs):
            if cancel is not None and cancel.is_set():
                break
            done += 1
            if on_progress:
                on_progress(done, len(pairs))
            try:
                pr = fut.result()
            except Exception:
                pr = None
            if pr is not None:
                out[(pr.ip, pr.domain)] = pr
                if on_result is not None:
                    on_result(pr)
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            ex.shutdown(wait=False)
    return out


# --------------------------------------------------------------------------
# 段 C：归因
# --------------------------------------------------------------------------
def _judge(probes: List[IpProbe]) -> Tuple[str, str]:
    if not probes:
        return VERDICT_NODATA, "该 DNS 未返回任何地址"
    ok = [p for p in probes if p.grade == GRADE_OK]
    uns = [p for p in probes if p.grade == GRADE_UNSTABLE]
    app = [p for p in probes if p.grade == GRADE_APPFAIL]
    hij = [p for p in probes if p.grade == GRADE_HIJACK]
    bog = [p for p in probes if p.grade == GRADE_BOGUS]
    blk = [p for p in probes if p.grade == GRADE_BLOCKED]
    dead = [p for p in probes if p.grade == GRADE_DEAD]
    good = len(ok) + len(uns)

    # 有真身（三级全通，或证书如实匹配）且没有任何伪造证据 → 解析有效
    if good and not hij and not bog:
        parts = []
        if ok:
            txt = f"{len(ok)} 个地址三级全通（TCP+TLS+HTTP）"
            flaky = len([p for p in ok if p.flaky])
            if flaky:
                txt += f"，其中 {flaky} 个重试后才通"
            parts.append(txt)
        if uns:
            parts.append(f"{len(uns)} 个证书如实匹配但连接不稳")
        if app:
            parts.append(f"{len(app)} 个握手可过但应用层打不开")
        # 混进了「握手可过、实际打不开」的地址，也算部分有效
        return (VERDICT_CLEAN if not (uns or app) else VERDICT_MIXED), "，".join(parts)

    # 有真身，但也混进了伪造 / 拦截地址
    if good:
        parts = [f"{good} 个地址真实可用"]
        if hij:
            parts.append(f"{len(hij)} 个证书不符（疑似劫持）")
        if bog:
            parts.append(f"{len(bog)} 个拦截地址")
        return VERDICT_MIXED, "，".join(parts)

    if hij:
        cn = next((p.cert_cn for p in hij if p.cert_cn), None)
        return VERDICT_HIJACK, "证书与该域名不符" + (f"（实际 CN={cn}）" if cn else "")

    if bog:
        reasons = "、".join(sorted({p.bogus_reason or "异常" for p in bog}))
        return VERDICT_BOGUS, f"返回拦截地址（{reasons}）"

    # 地址是真实的（TLS 严格验证都过了），只是应用层一个字都拿不到。
    # 这一档要单独标出来：它既不是污染，也不该混进「解析有效」——
    # 用户照着选会写进 hosts，然后发现还是打不开。
    if app:
        rounds = max((p.rounds for p in app), default=1)
        return VERDICT_APPFAIL, (f"{len(app)} 个地址 TLS 握手正常，"
                                 f"但 HTTP 层拿不到响应（连试 {rounds} 轮仍未通）")

    if blk:
        return VERDICT_BLOCKED, f"{len(blk)} 个地址 TLS 阶段被中断且拿不到证书"

    if dead:
        return VERDICT_DEAD, f"{len(dead)} 个地址 TCP 均无法连通"

    return VERDICT_NODATA, "无有效探测结果"


def aggregate(answers: Sequence[ResolveAnswer],
              probes: Dict[Tuple[str, str], IpProbe],
              per_domain_freq: Dict[str, Counter],
              reference: Optional[Dict[str, Set[str]]] = None
              ) -> Tuple[List[Verdict], Dict[str, Set[str]], List[BestIp]]:
    ref = reference or {}

    # 共识 IP
    consensus: Dict[str, Set[str]] = {}
    for dom, freq in per_domain_freq.items():
        total = sum(freq.values()) or 1
        thresh = max(CONSENSUS_MIN, int(total * CONSENSUS_RATIO))
        consensus[dom] = {ip for ip, c in freq.items()
                          if c >= thresh and not P.is_bogus_ip(ip)}

    # 按 (dns_key, domain) 归组；同一个 DNS 的 A 与 AAAA 结果**合并**而不是覆盖
    buckets: Dict[Tuple[str, str], ResolveAnswer] = {}
    for a in answers:
        k = (a.dns_key, a.domain)
        cur = buckets.get(k)
        if cur is None:
            buckets[k] = a
        elif cur is not a:
            cur.merge(a)

    verdicts: List[Verdict] = []
    for (dns_key, dom), a in buckets.items():
        if not a.ok:
            verdicts.append(Verdict(
                dns_key=dns_key, dns_name=a.dns_name, dns_group=a.dns_group,
                kind=a.kind, server=a.server, domain=dom, verdict=VERDICT_NODATA,
                detail=f"解析失败（{a.error or a.rcode}）", ms=a.ms,
                qtypes=list(a.qtypes or [a.qtype])))
            continue
        prs = [probes[(ip, dom)] for ip in a.ips if (ip, dom) in probes]
        v, detail = _judge(prs)
        # 有共识 IP 参与时给个额外说明
        shared = [ip for ip in a.ips if ip in consensus.get(dom, set())]
        if shared and v in (VERDICT_CLEAN, VERDICT_MIXED):
            detail += f"；与 {len(shared)} 个共识地址一致"
        verdicts.append(Verdict(
            dns_key=dns_key, dns_name=a.dns_name, dns_group=a.dns_group,
            kind=a.kind, server=a.server, domain=dom, ips=list(a.ips),
            probes=prs, verdict=v, detail=detail, ms=a.ms,
            qtypes=list(a.qtypes or [a.qtype])))

    # 挑选每个域名的最佳 IP（用于写 hosts）
    best: List[BestIp] = []
    for dom, freq in per_domain_freq.items():
        cands: List[BestIp] = []
        for ip, votes in freq.items():
            pr = probes.get((ip, dom))
            if pr is None or pr.grade not in (GRADE_OK, GRADE_UNSTABLE):
                continue
            srcs = sorted({a.dns_name for a in answers
                           if a.domain == dom and a.ok and ip in a.ips})
            cands.append(BestIp(domain=dom, ip=ip, latency_ms=pr.latency_ms,
                                votes=votes, grade=pr.grade, flaky=pr.flaky,
                                http_code=pr.http_code, sources=srcs[:6]))
        # 排序：三级全通 → **稳定通过（不是重试才通的）** → IPv4 优先 → 延迟升序 → 票数。
        # IPv4 排在前面是因为：hosts 里写 IPv6 字面量，部分软件的兼容性一般；
        # 延迟升序优先于票数，则是为了避免选出「最多 DNS 认可但慢 2 秒」的地址。
        cands.sort(key=lambda b: (0 if b.grade == GRADE_OK else 1,
                                  0 if not b.flaky else 1,
                                  0 if ":" not in b.ip else 1,
                                  b.latency_ms if b.latency_ms else 9e9,
                                  -b.votes))
        if cands:
            best.append(cands[0])
    return verdicts, consensus, best


# --------------------------------------------------------------------------
# 一次跑完
# --------------------------------------------------------------------------
def run_check(targets: Sequence[dict], domains: Sequence[str],
              cancel=None,
              use_reference: bool = True,
              qtypes: Sequence[int] = (P.QTYPE_A,),
              workers_resolve: int = 64,
              workers_probe: int = 128,
              stage_cb: Optional[Callable[[str, int, int], None]] = None,
              on_resolve: Optional[Callable[[ResolveAnswer], None]] = None,
              on_pairs: Optional[Callable[[List[Tuple[str, str]]], None]] = None,
              on_probe: Optional[Callable[[IpProbe], None]] = None,
              ) -> CheckReport:
    """三个阶段串起来跑。on_resolve / on_probe 用于界面实时刷新。"""
    report = CheckReport()

    def stage(name):
        def cb(done, total):
            if stage_cb:
                stage_cb(name, done, total)
        return cb

    if use_reference:
        ref, refsrc = build_reference(domains, cancel=cancel,
                                      on_progress=stage("建立基准参照"))
        report.reference = ref
        report.reference_sources = refsrc

    answers = resolve_all(targets, domains, qtypes, workers_resolve, cancel,
                          stage("解析目标域名"), on_result=on_resolve)
    report.answers = answers

    pairs, freq = collect_probe_pairs(answers)
    if on_pairs:
        on_pairs(pairs)
    probes = probe_all(pairs, workers_probe, cancel,
                       stage("TCP / TLS / HTTP 三级落地探测"),
                       on_result=on_probe)
    report.probes = probes

    verdicts, consensus, best = aggregate(answers, probes, freq, report.reference)
    report.verdicts = verdicts
    report.consensus = consensus
    report.best_ips = best
    return report
