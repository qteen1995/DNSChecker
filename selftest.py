# -*- coding: utf-8 -*-
"""自检脚本：验证数据层与协议层是否正常工作。"""
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import dnsdata
import dnsproto as P


def sec(t):
    print("\n" + "=" * 62)
    print(t)
    print("=" * 62)


sec("1. 数据统计")
entries = dnsdata.DEFAULT_ENTRIES
eps = list(dnsdata.iter_endpoints(entries))
kinds = Counter(k for _, k, _ in eps)
groups = Counter(e.get("group", "?") for e in entries)
print(f"服务条目 : {len(entries)}")
print(f"端点总数 : {len(eps)}")
print("通道分布 :", dict(kinds))
print("分类分布 :", dict(groups))
names = [e["name"] for e in entries]
dup = [n for n, c in Counter(names).items() if c > 1]
print("重名条目 :", dup or "无")
print("目标域名 :", len(dnsdata.DEFAULT_DOMAINS))

sec("2. 报文构造 / 解析回环")
qid, pkt = P.build_query("www.baidu.com", P.QTYPE_A)
print("查询报文长度:", len(pkt), "qid:", qid)
print("报文字节头:", pkt[:16].hex())

sec("3. IPv4 明文 UDP")
for srv in ("223.5.5.5", "119.29.29.29", "180.76.76.76"):
    r = P.query_udp(srv, "www.baidu.com")
    print(f"  {srv:16s} ok={r.ok} rtt={r.rtt_ms and round(r.rtt_ms,1)} "
          f"rcode={r.rcode_name} ans={r.answers[:3]} err={r.error}")

sec("4. IPv6 明文 UDP")
for srv in ("2400:3200::1", "2402:4e00::"):
    r = P.query_udp(srv, "www.baidu.com")
    print(f"  {srv:20s} ok={r.ok} rtt={r.rtt_ms and round(r.rtt_ms,1)} "
          f"rcode={r.rcode_name} ans={r.answers[:3]} err={r.error}")

sec("5. DoT")
for host in ("dns.alidns.com", "dot.pub", "dns.google"):
    r = P.query_dot(host, "www.baidu.com")
    print(f"  {host:20s} ok={r.ok} conn={r.connect_ms and round(r.connect_ms,1)} "
          f"rtt={r.rtt_ms and round(r.rtt_ms,1)} rc={r.rcode_name} err={r.error}")

sec("6. DoH")
for url in ("https://dns.alidns.com/dns-query", "https://doh.pub/dns-query",
            "https://cloudflare-dns.com/dns-query"):
    r = P.query_doh(url, "www.baidu.com")
    print(f"  {url:42s} ok={r.ok} conn={r.connect_ms and round(r.connect_ms,1)} "
          f"rtt={r.rtt_ms and round(r.rtt_ms,1)} rc={r.rcode_name} err={r.error}")

sec("7. TLS 落地探测（GitHub 真实 IP）")
for ip, dom in (("185.199.109.133", "raw.githubusercontent.com"),
                ("20.205.243.165", "codeload.github.com"),
                ("1.2.3.4", "github.com")):
    t0 = time.perf_counter()
    p = P.probe_tls(ip, dom, timeout=3.0)
    dt = (time.perf_counter() - t0) * 1000
    print(f"  {ip:18s} {dom:30s} grade={p.grade:8s} tcp={p.tcp_ms and round(p.tcp_ms)} "
          f"tls={p.tls_ms and round(p.tls_ms)} err={p.error} ({dt:.0f}ms)")

sec("8. X.509 证书解析（SAN / CN）")
info = P.grab_cert("185.199.109.133", "raw.githubusercontent.com")
if info:
    cn, sans = info
    print("  CN  :", cn)
    print("  SAN :", sans)
    print("  覆盖 raw.githubusercontent.com ?",
          P.cert_covers(sans, cn, "raw.githubusercontent.com"))
    print("  覆盖 github.com ?", P.cert_covers(sans, cn, "github.com"))
else:
    print("  抓取失败")

sec("9. 污染模拟：拿一个假 IP 试试")
p = P.probe_tls("127.0.0.1", "github.com", timeout=1.5)
print("  127.0.0.1 ->", p.grade, p.error)

print("\n自检完成。")
