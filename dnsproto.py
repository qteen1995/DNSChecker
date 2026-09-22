# -*- coding: utf-8 -*-
"""DNS 协议层 —— 纯标准库实现，零第三方依赖。

提供：
  * DNS 报文构造 / 解析（含压缩指针、CNAME、A/AAAA）
  * 四种传输通道的单次查询原语：UDP / TCP / DoT(TLS) / DoH(HTTPS, RFC 8484)
  * X.509 证书最小 DER 解析（SAN / CN），用于污染取证
  * TCP + TLS 落地探测（判断解析结果是否真的可用）

设计要点
  * 所有查询直接向目标服务器发包，**绝不调用 getaddrinfo 去解析被测域名**，
    以免被 hosts 文件或系统 DNS 干扰结论。
  * DoT / DoH 的服务器域名用内置 bootstrap DNS 解析并 pin 住 IP，
    同样绕开系统解析。
"""
from __future__ import annotations

import base64
import http.client
import ipaddress
import random
import socket
import ssl
import struct
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

QTYPE_A = 1
QTYPE_NS = 2
QTYPE_CNAME = 5
QTYPE_AAAA = 28

RCODE_NAMES = {
    0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN",
    4: "NOTIMP", 5: "REFUSED",
}

# 界面上给普通用户看的中文名。RFC 的 ASCII 名保留在 RCODE_NAMES，
# 详情弹窗与导出 CSV 会把两个一起给出，方便对照排障。
RCODE_CN = {
    0: "正常", 1: "格式错误", 2: "服务器故障", 3: "域名不存在",
    4: "未实现", 5: "拒绝",
}


def rcode_cn(rcode: Optional[int]) -> str:
    if rcode is None:
        return "-"
    return RCODE_CN.get(rcode, f"响应码 {rcode}")


UDP_TIMEOUT = 2.0
TCP_TIMEOUT = 3.0
DOT_TIMEOUT = 4.0
DOH_TIMEOUT = 5.0
TLS_TIMEOUT = 3.0
HTTP_TIMEOUT = 4.0
HTTP_PATH = "/"

# 探测用的 UA 带一段浏览器标识：有些站点对非浏览器 UA 直接 403/断连，
# 那会把「站点在正常服务」误读成「不可访问」。带浏览器标识才贴近真实访问。
HTTP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) dns-checker/1.0"

BOOTSTRAP_V4 = ["223.5.5.5", "119.29.29.29", "180.76.76.76", "114.114.114.114"]
BOOTSTRAP_V6 = ["2400:3200::1", "2402:4e00::", "2400:da00::6666"]

UA = "dns-checker/1.0 (+stdlib)"

_bootstrap_cache: dict = {}


# --------------------------------------------------------------------------
# 结果容器
# --------------------------------------------------------------------------
@dataclass
class DnsResult:
    ok: bool = False
    connect_ms: Optional[float] = None   # TCP+TLS 建连耗时（仅 DoT/DoH）
    rtt_ms: Optional[float] = None       # 查询往返耗时
    rcode: Optional[int] = None
    answers: List[str] = field(default_factory=list)
    cnames: List[str] = field(default_factory=list)
    error: Optional[str] = None
    truncated: bool = False

    @property
    def total_ms(self) -> Optional[float]:
        """首次查询的完整等待时间 = 建连 + 往返（UDP 只有往返）。"""
        if self.rtt_ms is None:
            return None
        return self.rtt_ms + (self.connect_ms or 0.0)

    @property
    def rcode_name(self) -> str:
        if self.rcode is None:
            return "-"
        return RCODE_NAMES.get(self.rcode, f"RCODE{self.rcode}")


@dataclass
class TlsProbe:
    """对某个 (IP, 域名) 组合的落地探测结果（三级：TCP → TLS → HTTP）。"""
    ip: str
    domain: str
    tcp_ok: bool = False
    tcp_ms: Optional[float] = None
    tls_ok: bool = False
    tls_ms: Optional[float] = None
    verified: bool = False               # 严格验证通过：链可信 + SAN 匹配
    # ---- 第三级：真的发一个 HTTP 请求 ----
    http_ok: bool = False
    http_code: Optional[int] = None
    http_ms: Optional[float] = None
    http_error: Optional[str] = None
    attempts: int = 1                    # 这个结果是第几轮探出来的
    rounds: int = 1                      # 一共探了几轮
    flaky: bool = False                  # 通了，但不是第一轮就通的 —— 链路在抖
    cert_cn: Optional[str] = None
    cert_sans: List[str] = field(default_factory=list)
    cert_covers: bool = False            # 实际拿到的证书是否覆盖该域名
    error: Optional[str] = None
    grade: str = "unknown"               # ok|unstable|appfail|hijack|blocked|dead

    @property
    def total_ms(self) -> Optional[float]:
        if not self.tcp_ok:
            return None
        return ((self.tcp_ms or 0.0) + (self.tls_ms or 0.0)
                + (self.http_ms or 0.0))

    @property
    def connect_ms(self) -> Optional[float]:
        """兼容旧字段名。"""
        return self.tls_ms


# --------------------------------------------------------------------------
# 报文构造与解析
# --------------------------------------------------------------------------
def _encode_name(name: str) -> bytes:
    out = bytearray()
    for label in name.rstrip(".").split("."):
        if not label:
            continue
        b = label.encode("ascii")
        if not 0 < len(b) < 64:
            raise ValueError(f"bad DNS label: {label!r}")
        out.append(len(b))
        out += b
    out.append(0)
    return bytes(out)


def build_query(name: str, qtype: int = QTYPE_A,
                qid: Optional[int] = None) -> Tuple[int, bytes]:
    """构造一个 RD=1 的查询报文，返回 (qid, packet)。"""
    if qid is None:
        qid = random.randrange(0, 0x10000)
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    return qid, header + _encode_name(name) + struct.pack("!HH", qtype, 1)


def _read_name(data: bytes, off: int) -> Tuple[str, int]:
    """读取域名，自动跟随压缩指针。返回 (name, 名字占位结束后的偏移)。"""
    labels: List[str] = []
    next_off: Optional[int] = None
    hops = 0
    while True:
        if off >= len(data):
            raise ValueError("name overrun")
        ln = data[off]
        if ln == 0:
            off += 1
            if next_off is None:
                next_off = off
            break
        if ln & 0xC0 == 0xC0:
            if off + 1 >= len(data):
                raise ValueError("truncated pointer")
            ptr = ((ln & 0x3F) << 8) | data[off + 1]
            if next_off is None:
                next_off = off + 2
            off = ptr
            hops += 1
            if hops > 32:
                raise ValueError("compression loop")
            continue
        off += 1
        labels.append(data[off:off + ln].decode("ascii", "replace"))
        off += ln
    return ".".join(labels), (next_off if next_off is not None else off)


def parse_message(data: bytes) -> dict:
    """解析应答，返回 {qid, rcode, truncated, answers, cnames}。"""
    if len(data) < 12:
        raise ValueError("short DNS message")
    qid, flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", data[:12])
    off = 12
    for _ in range(qd):
        _, off = _read_name(data, off)
        off += 4
    answers: List[str] = []
    cnames: List[str] = []
    for _ in range(an):
        _, off = _read_name(data, off)
        if off + 10 > len(data):
            break
        rtype, _rclass, _ttl, rdlen = struct.unpack("!HHIH", data[off:off + 10])
        off += 10
        rd = data[off:off + rdlen]
        if rtype == QTYPE_A and rdlen == 4:
            answers.append(socket.inet_ntoa(rd))
        elif rtype == QTYPE_AAAA and rdlen == 16:
            answers.append(socket.inet_ntop(socket.AF_INET6, rd))
        elif rtype == QTYPE_CNAME:
            try:
                cn, _ = _read_name(data, off)
                cnames.append(cn)
            except ValueError:
                pass
        off += rdlen
    return {"qid": qid, "rcode": flags & 0xF, "truncated": bool(flags & 0x0200),
            "answers": answers, "cnames": cnames}


# --------------------------------------------------------------------------
# 网络原语
# --------------------------------------------------------------------------
def _family(host: str) -> int:
    return socket.AF_INET6 if ":" in host else socket.AF_INET


def _connect(host: str, port: int, timeout: float) -> socket.socket:
    sock = socket.socket(_family(host), socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
    except Exception:
        sock.close()
        raise
    return sock


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("peer closed early")
        buf += chunk
    return bytes(buf)


def err_name(e: BaseException) -> str:
    if isinstance(e, TimeoutError):
        return "Timeout"
    if isinstance(e, ConnectionResetError):
        return "Reset"
    if isinstance(e, ConnectionRefusedError):
        return "Refused"
    if isinstance(e, ssl.SSLCertVerificationError):
        return "CertVerifyFail"
    if isinstance(e, ssl.SSLError):
        return "TLS:" + str(getattr(e, "reason", "") or type(e).__name__)
    if isinstance(e, socket.gaierror):
        return "ResolveFail"
    if isinstance(e, OSError) and e.errno:
        return f"OSErr{e.errno}"
    return type(e).__name__


# --------------------------------------------------------------------------
# 通道 1/2：明文 UDP
# --------------------------------------------------------------------------
def query_udp(server: str, name: str, qtype: int = QTYPE_A, port: int = 53,
              timeout: float = UDP_TIMEOUT) -> DnsResult:
    res = DnsResult()
    try:
        qid, pkt = build_query(name, qtype)
        sock = socket.socket(_family(server), socket.SOCK_DGRAM)
    except Exception as e:
        res.error = err_name(e)
        return res
    try:
        t0 = time.perf_counter()
        deadline = t0 + timeout
        sock.settimeout(timeout)
        sock.sendto(pkt, (server, port))
        while True:
            remain = deadline - time.perf_counter()
            if remain <= 0:
                raise TimeoutError("no reply")
            sock.settimeout(remain)
            data, _ = sock.recvfrom(4096)
            if len(data) >= 2 and struct.unpack("!H", data[:2])[0] == qid:
                break
        res.rtt_ms = (time.perf_counter() - t0) * 1000.0
        msg = parse_message(data)
        res.ok = True
        res.rcode = msg["rcode"]
        res.answers = msg["answers"]
        res.cnames = msg["cnames"]
        res.truncated = msg["truncated"]
    except Exception as e:
        res.error = err_name(e)
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return res


# --------------------------------------------------------------------------
# 通道 3：明文 TCP（DNS over TCP，2 字节长度前缀）—— 也用于截断重试
#
# 明文 TCP 和明文 UDP 一样可被劫持，对「判断污染」没有额外价值；但国内实测
# 8.8.8.8 的 UDP:53 被阻断、TCP:53 却是通的，所以它能把一批「看着不可用、
# 其实还能用」的服务器救回来。同机 UDP/TCP 延迟差得离谱，通常说明 UDP 层被
# QoS 限速了，这本身也是个有用的对比维度。
# --------------------------------------------------------------------------
def query_tcp(server: str, name: str, qtype: int = QTYPE_A, port: int = 53,
              timeout: float = TCP_TIMEOUT) -> DnsResult:
    res = DnsResult()
    try:
        qid, pkt = build_query(name, qtype)
        t_c = time.perf_counter()
        sock = _connect(server, port, timeout)
        # 建连耗时单独记：TCP 每次查询都要先握手，把它算进 rtt 会让延迟虚高、
        # 又和 UDP 的语义对不上。记在 connect_ms 里，total_ms 自然会加上它。
        res.connect_ms = (time.perf_counter() - t_c) * 1000.0
    except Exception as e:
        res.error = err_name(e)
        return res
    try:
        t0 = time.perf_counter()
        sock.sendall(struct.pack("!H", len(pkt)) + pkt)
        ln = struct.unpack("!H", _recv_exact(sock, 2))[0]
        data = _recv_exact(sock, ln)
        res.rtt_ms = (time.perf_counter() - t0) * 1000.0
        msg = parse_message(data)
        res.ok = True
        res.rcode = msg["rcode"]
        res.answers = msg["answers"]
        res.cnames = msg["cnames"]
    except Exception as e:
        res.error = err_name(e)
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return res


# --------------------------------------------------------------------------
# 通道 4：DoT（RFC 7858）
# --------------------------------------------------------------------------
def query_dot(host: str, name: str, qtype: int = QTYPE_A, port: int = 853,
              timeout: float = DOT_TIMEOUT,
              connect_ip: Optional[str] = None,
              max_candidates: Optional[int] = None) -> DnsResult:
    """DoT 查询。host 用于 SNI / 证书校验，TCP 连到它解析出的候选 IP 上重试。

    `max_candidates` 用于限制候选 IP 的尝试个数 —— 对"探路"性质的调用
    （比如判断某个基准源在当前线路通不通），遍历全部候选纯属浪费时间。
    """
    cands = [connect_ip] if connect_ip else resolve_candidates(host)
    if max_candidates:
        cands = cands[:max_candidates]
    if not cands:
        return DnsResult(error="BootstrapFail")
    last: Optional[DnsResult] = None
    for ip in cands:
        last = _dot_once(host, ip, name, qtype, port, timeout)
        if last.ok:
            return last
    return last or DnsResult(error="BootstrapFail")


def _dot_once(host: str, ip: str, name: str, qtype: int,
              port: int, timeout: float) -> DnsResult:
    res = DnsResult()
    try:
        ctx = ssl.create_default_context()
        try:
            ctx.set_alpn_protocols(["dot"])
        except Exception:
            pass
        t_conn = time.perf_counter()
        raw = _connect(ip, port, timeout)
        sock = ctx.wrap_socket(raw, server_hostname=host)
        res.connect_ms = (time.perf_counter() - t_conn) * 1000.0
    except Exception as e:
        res.error = err_name(e)
        return res
    try:
        qid, pkt = build_query(name, qtype)
        t0 = time.perf_counter()
        sock.sendall(struct.pack("!H", len(pkt)) + pkt)
        ln = struct.unpack("!H", _recv_exact(sock, 2))[0]
        data = _recv_exact(sock, ln)
        res.rtt_ms = (time.perf_counter() - t0) * 1000.0
        msg = parse_message(data)
        res.ok = True
        res.rcode = msg["rcode"]
        res.answers = msg["answers"]
        res.cnames = msg["cnames"]
    except Exception as e:
        res.error = err_name(e)
    finally:
        try:
            sock.close()
        except Exception:
            pass
    return res


# --------------------------------------------------------------------------
# 通道 5：DoH（RFC 8484）
# --------------------------------------------------------------------------
class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TCP 连到指定 IP，但 SNI / Host 头保持为原始域名。"""

    def __init__(self, host, port, connect_ip, timeout, context):
        super().__init__(host, port, timeout=timeout, context=context)
        self._connect_ip = connect_ip
        self.connect_ms: Optional[float] = None

    def connect(self):
        t0 = time.perf_counter()
        self.sock = _connect(self._connect_ip, self.port, self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)
        self.connect_ms = (time.perf_counter() - t0) * 1000.0


def query_doh(url: str, name: str, qtype: int = QTYPE_A,
              timeout: float = DOH_TIMEOUT,
              connect_ip: Optional[str] = None,
              max_candidates: Optional[int] = None) -> DnsResult:
    """DoH 查询（RFC 8484）。POST 优先，服务器不认再回退 GET。"""
    try:
        parts = urllib.parse.urlsplit(url)
    except Exception as e:
        return DnsResult(error=err_name(e))
    if parts.scheme not in ("https", "http"):
        return DnsResult(error="BadScheme")
    host = parts.hostname
    if not host:
        return DnsResult(error="BadURL")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/dns-query"
    if parts.query:
        path += "?" + parts.query

    try:
        ctx = ssl.create_default_context()
        try:
            ctx.set_alpn_protocols(["http/1.1"])   # http.client 不支持 h2
        except Exception:
            pass
    except Exception as e:
        return DnsResult(error=err_name(e))

    cands = [connect_ip] if connect_ip else resolve_candidates(host)
    if max_candidates:
        cands = cands[:max_candidates]
    if not cands:
        return DnsResult(error="BootstrapFail")
    last: Optional[DnsResult] = None
    for ip in cands:
        last = _doh_once(host, ip, port, path, name, qtype, timeout, ctx)
        if last.ok:
            return last
    return last or DnsResult(error="BootstrapFail")


def _doh_once(host: str, ip: str, port: int, path: str, name: str,
              qtype: int, timeout: float, ctx) -> DnsResult:
    res = DnsResult()
    qid, pkt = build_query(name, qtype)
    headers = {
        "Content-Type": "application/dns-message",
        "Accept": "application/dns-message",
        "User-Agent": UA,
    }
    last_err = "unknown"
    for method in ("POST", "GET"):
        conn = None
        try:
            conn = _PinnedHTTPSConnection(host, port, ip, timeout, ctx)
            t0 = time.perf_counter()
            if method == "POST":
                conn.request("POST", path, body=pkt, headers=headers)
            else:
                b64 = base64.urlsafe_b64encode(pkt).rstrip(b"=").decode("ascii")
                sep = "&" if "?" in path else "?"
                conn.request("GET", f"{path}{sep}dns={b64}", headers={
                    "Accept": "application/dns-message", "User-Agent": UA})
            resp = conn.getresponse()
            data = resp.read()
            res.rtt_ms = (time.perf_counter() - t0) * 1000.0
            res.connect_ms = getattr(conn, "connect_ms", None)
            if resp.status != 200:
                last_err = f"HTTP{resp.status}"
                continue
            msg = parse_message(data)
            res.ok = True
            res.rcode = msg["rcode"]
            res.answers = msg["answers"]
            res.cnames = msg["cnames"]
            return res
        except Exception as e:
            last_err = err_name(e)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    res.error = last_err
    return res


# --------------------------------------------------------------------------
# Bootstrap：解析 DoT/DoH 服务器自身的域名（绕开系统解析）
# --------------------------------------------------------------------------
def resolve_candidates(host: str, timeout: float = 2.0,
                       limit: int = 3) -> List[str]:
    """把 DoT/DoH 的服务器域名解析成一批候选 IP，用于 pin 连接。

    IP 字面量直接返回。域名用内置公共 DNS 解析，**收集多个候选**而不是只取第一个 ——
    实测海外 DoH 的域名虽然解析结果干净，但部分 IP 会连接超时，必须逐个回退重试。
    """
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass

    key = host.lower()
    if key in _bootstrap_cache:
        return _bootstrap_cache[key]

    cands: List[str] = []
    for qtype, servers in ((QTYPE_A, BOOTSTRAP_V4), (QTYPE_AAAA, BOOTSTRAP_V6)):
        for srv in servers:
            try:
                r = query_udp(srv, host, qtype, timeout=timeout)
            except Exception:
                continue
            if r.ok:
                for ip in r.answers:
                    if ip not in cands:
                        cands.append(ip)
            if len(cands) >= limit:
                break
        if cands:
            break
    _bootstrap_cache[key] = cands[:limit]
    return _bootstrap_cache[key]


def is_bogus_ip(ip: str) -> Optional[str]:
    """判断一个解析结果是否属于「必然异常」的地址。

    返回异常原因，正常公网地址返回 None。
    DNS 返回这些地址只可能是拦截 / 污染，没有必要再去做落地探测。
    """
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return "非法地址"
    if a.is_unspecified:
        return "未指定地址"
    if a.is_loopback:
        return "回环地址"
    if a.is_link_local:
        return "链路本地"
    if a.is_multicast:
        return "组播地址"
    if a.is_private:
        return "内网地址"
    if a.is_reserved:
        return "保留地址"
    return None


# --------------------------------------------------------------------------
# TCP + TLS 落地探测
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# 三级落地探测：TCP → TLS(严格) → HTTP
#
# 为什么必须做到 HTTP 这一层（实测数据说话）：
#   * 有一个 IP 的 TLS 握手完全正常（448ms 就握上了），但发不出任何应用层数据 ——
#     HTTP 层连试三轮全部超时。**握手成功只证明「能协商」，不证明「能访问」。**
#   * 反向的误判同样存在：有 IP 的 TLS 那一把被重置（现有代码判「疑似阻断」），
#     实际站点是完全好的（HTTP 三轮全部正常响应）。
#   * 链路本身在抖：同一 IP 三轮结果是 http / dead / dead。
# ⇒ 所以既要多测一层，也要**失败重试一次**，取最好的一轮作为结论。
# --------------------------------------------------------------------------
def _read_http_code(ss, domain: str, path: str, timeout: float
                    ) -> Tuple[Optional[int], Optional[str], float]:
    """在已握手的 TLS 连接上发一个 GET，返回 (状态码|None, 错误, 耗时ms)。

    **只要读到 HTTP 状态行就算成功，不看状态码是几。** 实测
    `objects.githubusercontent.com` 的根路径本来就返回 404、
    `raw.githubusercontent.com` 返回 301 跳到真实路径 —— 它们都完全可用。
    状态码代表服务器的策略，三层链路是通的才是我们要判的「能不能访问」。
    """
    t0 = time.perf_counter()
    try:
        req = (f"GET {path} HTTP/1.1\r\n"
               f"Host: {domain}\r\n"
               f"User-Agent: {HTTP_UA}\r\n"
               "Accept: */*\r\n"
               "Accept-Encoding: identity\r\n"
               "Connection: close\r\n\r\n")
        ss.settimeout(timeout)
        ss.sendall(req.encode("latin-1"))
        buf = b""
        while len(buf) < 4096:
            chunk = ss.recv(2048)
            if not chunk:
                break
            buf += chunk
            if b"\r\n\r\n" in buf:
                break
        ms = (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        return None, err_name(e), (time.perf_counter() - t0) * 1000.0

    line = buf.split(b"\r\n", 1)[0].decode("latin-1", "replace").strip()
    if not line.upper().startswith("HTTP/"):
        return None, (f"非 HTTP 响应({line[:24]})" if line else "空响应"), ms
    parts = line.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return None, f"状态行异常({line[:24]})", ms
    return int(parts[1]), None, ms


def _probe_once(ip: str, domain: str, port: int, timeout: float,
                path: str, http_timeout: float = HTTP_TIMEOUT) -> TlsProbe:
    """一次完整的三级探测。TLS 层失败时**不**做取证（取证贵，留给重试结束后做一次）。"""
    p = TlsProbe(ip=ip, domain=domain)

    # ---- 第 1 级：TCP ----
    try:
        t0 = time.perf_counter()
        sock = _connect(ip, port, timeout)
        p.tcp_ok = True
        p.tcp_ms = (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        p.error = err_name(e)
        p.grade = "dead"
        return p

    # ---- 第 2 级：TLS 严格校验 ----
    ss = None
    fallback = "blocked"
    try:
        ctx = ssl.create_default_context()
        # ★ ALPN 只声明 http/1.1，**绝不能带上 h2**：
        #   服务器一旦协商到 HTTP/2，后面发明文 HTTP/1.1 请求必然失败 ——
        #   那是我们自己造成的假失败，不是链路的锅。
        try:
            ctx.set_alpn_protocols(["http/1.1"])
        except Exception:
            pass
        t0 = time.perf_counter()
        ss = ctx.wrap_socket(sock, server_hostname=domain)
        p.tls_ok = True
        p.verified = True
        p.tls_ms = (time.perf_counter() - t0) * 1000.0
    except ssl.SSLCertVerificationError:
        p.error = "CertVerifyFail"
        fallback = "hijack"
    except Exception as e:
        p.error = err_name(e)

    # ---- 第 3 级：HTTP ----
    if p.tls_ok:
        code, err, ms = _read_http_code(ss, domain, path, http_timeout)
        p.http_ms = ms
        for s in (ss, sock):
            try:
                s.close()
            except Exception:
                pass
        if code is None:
            # 证书严格验证过了、握手也正常，但应用层一个字都拿不到
            p.http_error = err
            p.grade = "appfail"
            p.error = f"TLS 握手正常，但应用层拿不到响应（{err}）"
            return p
        p.http_ok = True
        p.http_code = code
        p.grade = "ok"
        return p

    try:
        sock.close()
    except Exception:
        pass
    p.grade = fallback
    return p


# 多轮尝试里「哪个结果更好」的排序（越小越好）
_GRADE_RANK = {"ok": 0, "unstable": 1, "appfail": 2, "hijack": 3,
               "blocked": 4, "dead": 5, "unknown": 6}


def probe_site(ip: str, domain: str, port: int = 443,
               timeout: float = TLS_TIMEOUT, path: str = HTTP_PATH,
               retries: int = 1, http_timeout: float = HTTP_TIMEOUT) -> TlsProbe:
    """三级落地探测，失败重试，取最好的一轮作为结论。

    **重试不是浪费，是必需**：实测同一 IP 三轮结果可能是
    `http:200 / dead / dead`，也可能 TLS 通了但 HTTP 连试两次都不通。
    只测一次会把「链路在抖」误判成「不通」，也会把「握得上但打不开」
    错当成「可用」—— 后者正是写进 hosts 之后打不开的原因。

    `http_timeout` 单独给 HTTP 阶段用，比握手宽松一点：被限速的链路
    「慢但能通」不该被判成「打不开」。

    取证（宽松握手）只在整个重试过程都失败之后做一次，不在每轮里重复做。
    """
    best: Optional[TlsProbe] = None
    tried = 0
    for i in range(max(1, retries + 1)):
        # 重试轮给 HTTP 层**双倍**时间：被限速的链路「慢但能通」，
        # 不该因为第一轮没在超时内回包就被判「打不开」。宁可多等一会，
        # 也不要把一个好地址错杀成不可用。
        ht = http_timeout if i == 0 else http_timeout * 2
        p = _probe_once(ip, domain, port, timeout, path, ht)
        tried = i + 1
        p.attempts = i + 1
        if best is None or (_GRADE_RANK.get(p.grade, 9)
                            < _GRADE_RANK.get(best.grade, 9)):
            best = p
        if best.grade == "ok":
            break

    assert best is not None
    best.rounds = tried
    if best.grade == "ok" and best.attempts > 1:
        best.flaky = True          # 通了，但不是第一轮就通的

    if best.grade == "appfail":
        # 严格验证已经过了，证书必然覆盖该域名，直接标上
        best.cert_covers = True
    elif best.grade in ("hijack", "blocked", "dead"):
        # 取证：宽松握手，把对端实际出示的证书抠出来。
        #
        # 这一步能救回大量误判。GitHub / PyPI 这类站点的 IP 在国内是**间歇性**
        # 被阻断的，同一把 TLS 可能超时、下一把就通。如果对端出示的证书如实
        # 覆盖了目标域名，那它就是这台服务器的真身，只是链路不稳 ——
        # 该判「可用但不稳定」，而不是扣一顶「疑似劫持」的帽子。
        info = grab_cert(ip, domain, port, timeout)
        if info:
            best.cert_cn, best.cert_sans = info
            best.cert_covers = cert_covers(best.cert_sans, best.cert_cn, domain)
            if best.cert_covers:
                best.grade = "unstable"
                best.error = f"{best.error or 'TLS 失败'}（但证书如实匹配 {domain}）"
    return best


def probe_tls(ip: str, domain: str, port: int = 443,
              timeout: float = TLS_TIMEOUT, path: str = HTTP_PATH,
              retries: int = 1) -> TlsProbe:
    """兼容旧名字 —— 现在做的是完整三级探测，见 `probe_site`。"""
    return probe_site(ip, domain, port, timeout, path, retries)


def grab_cert(ip: str, domain: str, port: int = 443,
              timeout: float = TLS_TIMEOUT):
    """不校验证书，只把对端证书的 (CN, SAN列表) 取回来。"""
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = _connect(ip, port, timeout)
        ss = ctx.wrap_socket(sock, server_hostname=domain)
        der = ss.getpeercert(binary_form=True)
        try:
            ss.close()
        except Exception:
            pass
        if not der:
            return None
        info = extract_cert_info(der)
        return info.get("subject_cn"), info.get("sans", [])
    except Exception:
        return None


def cert_covers(sans: List[str], cn: Optional[str], domain: str) -> bool:
    """证书的 SAN / CN 是否覆盖该域名（含单层通配符）。"""
    domain = domain.lower().rstrip(".")
    names = [s.lower().rstrip(".") for s in (sans or [])]
    if cn:
        names.append(cn.lower().rstrip("."))
    for n in names:
        if n == domain:
            return True
        if n.startswith("*."):
            base = n[2:]
            if domain.endswith("." + base):
                prefix = domain[:-(len(base) + 1)]
                if prefix and "." not in prefix:
                    return True
    return False


# --------------------------------------------------------------------------
# 最小 X.509 DER 解析（只为拿 SAN / CN，避免引入 cryptography）
# --------------------------------------------------------------------------
def _der_tlv(data: bytes, off: int):
    tag = data[off]
    off += 1
    ln = data[off]
    off += 1
    if ln & 0x80:
        n = ln & 0x7F
        if n == 0 or n > 4:
            raise ValueError("indefinite or oversized DER length")
        ln = int.from_bytes(data[off:off + n], "big")
        off += n
    if off + ln > len(data):
        raise ValueError("DER overrun")
    return tag, data[off:off + ln], off + ln


def _der_seq(data: bytes):
    out = []
    off = 0
    while off < len(data):
        tag, val, off = _der_tlv(data, off)
        out.append((tag, val))
    return out


def _decode_oid(b: bytes) -> str:
    if not b:
        return ""
    parts = [str(b[0] // 40), str(b[0] % 40)]
    val = 0
    for byte in b[1:]:
        val = (val << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(str(val))
            val = 0
    return ".".join(parts)


def _find_cn(name_der: bytes) -> Optional[str]:
    for _t, rdn in _der_seq(name_der):
        for _t2, atv in _der_seq(rdn):
            kv = _der_seq(atv)
            if len(kv) >= 2 and kv[0][0] == 0x06 and _decode_oid(kv[0][1]) == "2.5.4.3":
                return kv[1][1].decode("utf-8", "replace")
    return None


def extract_cert_info(der: bytes) -> dict:
    info = {"subject_cn": None, "issuer_cn": None, "sans": []}
    if not der:
        return info
    try:
        _t, cert, _ = _der_tlv(der, 0)
        top = _der_seq(cert)
        if not top:
            return info
        items = _der_seq(top[0][1])                 # tbsCertificate
        subj_idx = 5 if (items and items[0][0] == 0xA0) else 4
        if subj_idx < len(items):
            info["subject_cn"] = _find_cn(items[subj_idx][1])
        if len(items) > 3:
            info["issuer_cn"] = _find_cn(items[3][1])
        for tag, val in items:
            if tag != 0xA3:                          # [3] extensions
                continue
            _t2, exts, _ = _der_tlv(val, 0)
            for _t3, ext in _der_seq(exts):
                ek = _der_seq(ext)
                if not ek or ek[0][0] != 0x06:
                    continue
                if _decode_oid(ek[0][1]) != "2.5.29.17":   # subjectAltName
                    continue
                octets = [v for t, v in ek if t == 0x04]
                if not octets:
                    continue
                _t4, gns, _ = _der_tlv(octets[-1], 0)
                for gtag, gval in _der_seq(gns):
                    if gtag == 0x82:                     # dNSName
                        info["sans"].append(gval.decode("ascii", "replace"))
    except Exception:
        pass
    return info
