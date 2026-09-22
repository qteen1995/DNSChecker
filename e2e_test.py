# -*- coding: utf-8 -*-
"""端到端验证：小规模真实跑一遍测速 + 污染检测。"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import channels
import dnsdata
import pollution

PICKS = ["阿里 AliDNS", "腾讯 DNSPod", "114 DNS", "百度 BaiduDNS",
         "Google Public DNS", "Cloudflare 1.1.1.1", "台湾 Quad 101",
         "清华大学 TUNA"]
DOMAINS = ["github.com", "raw.githubusercontent.com", "store.steampowered.com",
           "pypi.org"]

by_name = {e["name"]: e for e in dnsdata.DEFAULT_ENTRIES}
entries = [by_name[n] for n in PICKS if n in by_name]
eps = [ep for ep in dnsdata.iter_endpoints(entries) if ep[1] == "udp4"]

print("=" * 74)
print(f"采样 DNS：{len(entries)} 个服务 / {len(eps)} 个端点")
print("=" * 74)

t0 = time.time()
results = channels.run_speedtest(eps, workers=32, samples=2)
print(f"\n测速用时 {time.time() - t0:.1f} 秒，结果（按延迟升序）：")
for i, r in enumerate(sorted(results, key=lambda x: x.sort_key()), 1):
    lat = f"{r.best_ms:7.1f} ms" if r.best_ms is not None else "      -  "
    print(f"  {i}. {r.name:26s} {r.display:16s} {lat}  {r.loss:5s} {r.status}")

print("\n" + "=" * 74)
print(f"污染检测：{len(eps)} 个 DNS × {len(DOMAINS)} 个域名")
print("=" * 74)

t0 = time.time()
report = pollution.run_check(
    [{"key": k, "kind": kd, "payload": p} for k, kd, p in eps],
    DOMAINS, use_reference=True,
    stage_cb=lambda n, d, t: None)
print(f"检测用时 {time.time() - t0:.1f} 秒\n")

print("基准参照（海外 DoH 拿到的参考 IP 集）：")
for dom in DOMAINS:
    ref = report.reference.get(dom) or set()
    src = report.reference_sources.get(dom) or []
    print(f"  {dom:32s} {len(ref):3d} 个 IP  来源 {len(src)} 个 DoH")
    if ref:
        print(f"      {sorted(ref)[:5]}")

print("\n本地共识 IP（被多个 DNS 共同返回）：")
for dom in DOMAINS:
    cons = report.consensus.get(dom) or set()
    print(f"  {dom:32s} {sorted(cons)[:6]}")

print("\n逐 DNS 判定：")
cur = None
for v in sorted(report.verdicts, key=lambda x: (x.domain, x.dns_name)):
    if v.domain != cur:
        cur = v.domain
        print(f"\n  ── {cur} " + "─" * (60 - len(cur)))
    ips = ", ".join(v.ips[:3]) + ("…" if len(v.ips) > 3 else "")
    print(f"     {v.dns_name:26s} {v.verdict_label:8s} {v.detail}")
    print(f"        {ips or '(无返回)'}")

print("\n落地探测明细：")
for (ip, dom), p in sorted(report.probes.items(), key=lambda kv: (kv[0][1], kv[0][0]))[:24]:
    lat = f"{p.latency_ms:.0f}ms" if p.latency_ms else "-"
    print(f"  {dom:28s} {ip:42s} {p.grade_label:8s} {lat:8s} "
          f"{('CN=' + p.cert_cn) if p.cert_cn else (p.error or '')}")

print("\n推荐写入 hosts 的 IP：")
for b in report.best_ips:
    print(f"  {b.domain:32s} -> {b.ip:42s} "
          f"{b.latency_ms and f'{b.latency_ms:.0f}ms'}  "
          f"{b.votes} 票  来自 {', '.join(b.sources[:3])}")
print("\n端到端验证结束。")
