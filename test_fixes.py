# -*- coding: utf-8 -*-
"""验证：A/AAAA 合并、DoT 基准源、推荐 IP 的 IPv4 优先。"""
import sys
import time

sys.path.insert(0, ".")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import dnsproto as P
import pollution

print("=" * 74)
print("① A + AAAA 合并（修复前 AAAA 会整个覆盖 A）")
print("=" * 74)
doms = ["github.com", "store.steampowered.com", "raw.githubusercontent.com",
        "pypi.org"]
targets = [{"key": "k1", "kind": "udp4",
            "payload": {"name": "阿里 AliDNS", "group": "国内",
                        "server": "223.5.5.5", "port": 53,
                        "display": "223.5.5.5"}}]
rep = pollution.run_check(targets, doms, use_reference=False,
                          qtypes=[P.QTYPE_A, P.QTYPE_AAAA])
for v in rep.verdicts:
    print(f"{v.domain:32s} [{v.qtype_label:9s}] {v.verdict_label:8s} "
          f"{len(v.ips)} 个地址")
    for ip in v.ips:
        kind = "IPv6" if ":" in ip else "IPv4"
        print(f"         {kind}  {ip}")

print()
print("=" * 74)
print("② 推荐 IP 挑选（应优先 IPv4、优先严格验证）")
print("=" * 74)
for b in rep.best_ips:
    kind = "IPv6" if ":" in b.ip else "IPv4"
    print(f"  {b.domain:32s} -> {b.ip:42s} {kind}  {b.grade_label}")

print()
print("=" * 74)
print("③ DoT 基准源逐个实测")
print("=" * 74)
for h in pollution.REFERENCE_DOTS:
    t0 = time.time()
    r = P.query_dot(h, "github.com", P.QTYPE_A, timeout=3.0)
    dt = time.time() - t0
    lat = f"{r.rtt_ms:.0f}ms" if r.rtt_ms else "-"
    print(f"  DoT {h:26s} ok={str(r.ok):5s} {lat:>8s}  "
          f"ans={r.answers[:2]} err={r.error}   ({dt:.1f}s)")

print()
print("④ DoH + DoT 并集构建")
t0 = time.time()
ref, srcs = pollution.build_reference(["github.com", "pypi.org"])
print(f"  用时 {time.time() - t0:.1f}s")
for d in ("github.com", "pypi.org"):
    print(f"  {d:16s} 参考 IP {len(ref.get(d) or [])} 个  "
          f"来源 {srcs.get(d) or '无'}")
