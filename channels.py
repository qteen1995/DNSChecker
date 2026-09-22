# -*- coding: utf-8 -*-
"""并发测速引擎。

对每个端点做 N 次采样，取**最小 RTT** 作为成绩。取最小值而不是平均值，是因为
最小值最接近真实链路延迟，不受本机调度抖动和服务器排队影响；平均值会被单次
毛刺严重污染。

所有通道都不走系统代理、不走系统解析：
  * UDP / DoT 用裸 socket，天然直连
  * DoH 走 http.client，同样不读 HTTP_PROXY 环境变量
这样四条通道的延迟才在同一把尺子上，可以横向比较。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import dnsproto as P

GROUP_ORDER = ["国内", "港台", "国外", "去广告", "高校", "电信", "联通", "移动", "未分类"]

KIND_LABEL = {"udp4": "IPv4/UDP", "udp6": "IPv6/UDP",
              "tcp4": "IPv4/TCP", "tcp6": "IPv6/TCP",
              "dot": "DoT", "doh": "DoH"}

# 界面「通道」筛选框的顺序，也是清单摊平时的顺序
KIND_ORDER = ["udp4", "udp6", "tcp4", "tcp6", "dot", "doh"]

# 用两个国内大站的域名交替采样：都在各 DNS 的热缓存里，横向可比，
# 又避免单一域名被某家 DNS 特殊对待。
PROBE_DOMAINS = ["www.baidu.com", "www.qq.com"]

SAMPLES = 3
WORKERS = 128


@dataclass
class SpeedResult:
    key: str
    kind: str
    name: str
    group: str
    server: str
    port: int
    display: str
    ok: bool = False
    best_ms: Optional[float] = None
    samples: List[Optional[float]] = field(default_factory=list)
    rcode: Optional[int] = None
    answers: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def kind_label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)

    @property
    def avg_ms(self) -> Optional[float]:
        good = [s for s in self.samples if s is not None]
        return sum(good) / len(good) if good else None

    @property
    def loss(self) -> str:
        got = len([s for s in self.samples if s is not None])
        return f"{got}/{len(self.samples)}" if self.samples else "-"

    @property
    def rcode_name(self) -> str:
        """RFC 里的 ASCII 响应码名（导出 CSV、详情弹窗用，便于对照排障）。"""
        if self.rcode is None:
            return "-"
        return P.RCODE_NAMES.get(self.rcode, f"RCODE{self.rcode}")

    @property
    def rcode_cn(self) -> str:
        """给普通用户看的中文响应码。"""
        return P.rcode_cn(self.rcode)

    @property
    def status(self) -> str:
        """表格「状态」列。

        非 0 的响应码一律说人话：REFUSED → 「拒绝」。要特别提醒的是，
        被拒绝的服务器**延迟成绩是假的好成绩** —— 它确实 20ms 就回了包，
        但对你没有任何价值，别照着排行榜选它。状态列用暖色标出来就是在说这件事。
        """
        if not self.ok:
            return "超时" if self.error == "Timeout" else f"失败({self.error})"
        if self.rcode == 0:
            return "正常"
        return self.rcode_cn

    @property
    def usable(self) -> bool:
        """真的能拿来解析域名吗？

        **收到应答（ok）不等于可用。** REFUSED / SERVFAIL / NXDOMAIN 这些非 0
        响应码都说明服务器没给出解析结果。最典型的是 REFUSED：它往往只要 20ms
        就回包，在排行榜上非常靠前，但对你毫无价值 —— 所以排序、统计、Top 榜
        一律按「不可用」处理，不能让它占着前排。

        `ok` 保留原义（链路有应答），「有响应」和「可用」是两个不同的概念。
        """
        return self.ok and self.rcode == 0

    def sort_key(self):
        """排序：先可用的按延迟升序，再接不可用的。"""
        if self.usable and self.best_ms is not None:
            return (0, self.best_ms, self.name)
        if self.usable:
            return (1, 0.0, self.name)
        return (2, 0.0, self.name)


def _query_once(kind: str, payload: dict, domain: str):
    if kind == "udp4" or kind == "udp6":
        return P.query_udp(payload["server"], domain, P.QTYPE_A,
                           payload.get("port", 53), P.UDP_TIMEOUT)
    if kind == "tcp4" or kind == "tcp6":
        return P.query_tcp(payload["server"], domain, P.QTYPE_A,
                           payload.get("port", 53), P.TCP_TIMEOUT)
    if kind == "dot":
        return P.query_dot(payload["server"], domain, P.QTYPE_A, 853, P.DOT_TIMEOUT)
    if kind == "doh":
        return P.query_doh(payload["server"], domain, P.QTYPE_A, P.DOH_TIMEOUT)
    raise ValueError(f"unknown kind {kind}")


def test_endpoint(key: str, kind: str, payload: dict, samples: int = SAMPLES,
                  cancel=None) -> SpeedResult:
    r = SpeedResult(key=key, kind=kind, name=payload["name"], group=payload["group"],
                    server=payload["server"], port=payload.get("port", 53),
                    display=payload.get("display", payload["server"]))
    best: Optional[float] = None
    good = 0
    for i in range(samples):
        if cancel is not None and cancel.is_set():
            break
        domain = PROBE_DOMAINS[i % len(PROBE_DOMAINS)]
        res = _query_once(kind, payload, domain)
        if res.ok:
            good += 1
            t = res.total_ms
            r.samples.append(round(t, 2))
            if best is None or t < best:
                best = t
            r.rcode = res.rcode
            r.answers = res.answers
            r.error = None
        else:
            r.samples.append(None)
            if r.error is None:
                r.error = res.error
            # 前两次都没应答就直接放弃，不必等第三次超时
            if good == 0 and i >= 1:
                break
    r.best_ms = best
    r.ok = best is not None
    return r


def run_speedtest(endpoints: Sequence,
                  workers: int = WORKERS,
                  samples: int = SAMPLES,
                  cancel=None,
                  on_result: Optional[Callable[[SpeedResult], None]] = None,
                  on_progress: Optional[Callable[[int, int], None]] = None) -> List[SpeedResult]:
    """并发跑完所有端点。

    on_result / on_progress 会在工作线程里被调用，GUI 侧请自行转投消息队列。
    """
    total = len(endpoints)
    results: List[SpeedResult] = []
    done = 0

    def work(item):
        key, kind, payload = item
        if cancel is not None and cancel.is_set():
            return None
        try:
            return test_endpoint(key, kind, payload, samples, cancel)
        except Exception as e:      # 单个端点异常不能拖垮整轮
            r = SpeedResult(key=key, kind=kind, name=payload.get("name", "?"),
                            group=payload.get("group", "未分类"),
                            server=payload.get("server", "?"), port=0,
                            display=payload.get("display", "?"),
                            error=type(e).__name__)
            return r

    ex = ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        futures = [ex.submit(work, ep) for ep in endpoints]
        for fut in as_completed(futures):
            if cancel is not None and cancel.is_set():
                break
            try:
                r = fut.result()
            except Exception:
                r = None
            if r is not None:
                results.append(r)
            done += 1
            if on_result is not None and r is not None:
                on_result(r)
            if on_progress is not None:
                on_progress(done, total)
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            ex.shutdown(wait=False)
    return results
