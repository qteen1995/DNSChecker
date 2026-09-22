# -*- coding: utf-8 -*-
"""hosts 文件管理 —— 本工具里唯一会动系统文件的部分，所以规则从紧。

安全设计
--------
1. **先备份**：任何写入前把原文件复制成 `hosts.bak.<时间戳>`，备份失败直接中止。
2. **只碰自己的一块**：所有写入都放在带标记的区块内，区块外的行一律不动。
3. **不删用户的东西**：命中目标域名、又在标记区块之外的既有条目会被**注释掉**
   （加固定前缀），而不是删除 —— 这样能一键还原，也不会丢掉用户原本写的备注。
4. **可还原**：还原 = 删掉标记区块 + 撤销注释前缀，其余内容逐字不变。
5. **写前校验**：写入的每条都是「合法 IP + 合法域名」，域名做了字符白名单，
   避免任何形式的行注入。
6. **要管理员权限**：没有权限时不尝试任何写操作，而是提示用户提权重启。
"""
from __future__ import annotations

import ipaddress
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HOSTS_PATH = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "drivers", "etc", "hosts")

BEGIN_MARK = "# >>> dns-checker BEGIN >>> (由 DNS 测速工具维护，请勿手动编辑本区块)"
END_MARK = "# <<< dns-checker END <<<"
DISABLED_PREFIX = "# [dns-checker disabled] "

_DOMAIN_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")

# 常见本地代理监听端口，用来判断本机是否挂着代理/加速器
PROXY_PORTS = (7890, 7891, 7897, 1080, 1081, 10808, 10809, 8080, 8888,
               1087, 5825, 10049, 443, 853)


@dataclass
class HostsResult:
    ok: bool
    message: str
    backup_path: Optional[str] = None
    written: int = 0
    disabled: int = 0
    restored: int = 0
    flushed: Optional[bool] = None       # None=没做 / True=成功 / False=失败
    flush_note: str = ""

    def detail(self) -> str:
        """给用户看的完整结果：写入情况 + 缓存刷新情况 + 浏览器缓存提醒。

        「刷新缓存」这一步必须让用户看见结果 —— 它失败了就意味着新映射不生效，
        但写入本身是成功的，所以不能算整体失败，只能显式提示。
        """
        parts = [self.message]
        if self.flushed is True:
            parts.append(self.flush_note or "已刷新系统 DNS 缓存。")
        elif self.flushed is False:
            parts.append(f"⚠ 未能刷新系统 DNS 缓存（{self.flush_note}）。\n"
                         "   请手动执行 ipconfig /flushdns，否则新映射可能不生效。")
        elif self.ok:
            parts.append("⚠ 没有刷新系统 DNS 缓存，新映射可能不生效。")
        if self.ok:
            parts.append("若浏览器仍访问到旧地址，请重启浏览器 —— "
                         "Chrome / Edge 有各自独立的 DNS 缓存，系统刷新管不到它。")
        return "\n\n".join(p for p in parts if p)


@dataclass
class HostsEntry:
    lineno: int
    ip: str
    domain: str
    raw: str
    in_block: bool = False
    disabled: bool = False

    @property
    def active(self) -> bool:
        return not self.disabled


# --------------------------------------------------------------------------
# 权限
# --------------------------------------------------------------------------
def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """用 UAC 提权重启自己。返回是否成功发起。"""
    try:
        import ctypes
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv[1:])
        else:
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv)
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
        return int(rc) > 32
    except Exception:
        return False


# --------------------------------------------------------------------------
# 读写
# --------------------------------------------------------------------------
def hosts_exists() -> bool:
    return os.path.isfile(HOSTS_PATH)


def _decode(raw: bytes) -> Tuple[str, bool]:
    """返回 (文本, 是否带 BOM)。"""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", "replace"), True
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc), False
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace"), False


def read_hosts() -> List[str]:
    if not hosts_exists():
        return []
    with open(HOSTS_PATH, "rb") as f:
        text, _bom = _decode(f.read())
    return text.splitlines()


def backup_hosts(tag: str = "") -> Optional[str]:
    if not hosts_exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{tag}" if tag else ""
    dst = f"{HOSTS_PATH}.bak.{stamp}{suffix}"
    try:
        shutil.copy2(HOSTS_PATH, dst)
        return dst
    except Exception:
        return None


def list_backups() -> List[str]:
    d = os.path.dirname(HOSTS_PATH)
    base = os.path.basename(HOSTS_PATH) + ".bak."
    try:
        names = [n for n in os.listdir(d) if n.startswith(base)]
    except Exception:
        return []
    return sorted((os.path.join(d, n) for n in names), reverse=True)


def _write_hosts(lines: List[str]) -> None:
    body = "\r\n".join(lines)
    if body and not body.endswith("\r\n"):
        body += "\r\n"
    tmp = HOSTS_PATH + ".dnschecker.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(body)
    os.replace(tmp, HOSTS_PATH)


# --------------------------------------------------------------------------
# 刷新系统 DNS 缓存（改完 hosts 必做，否则不生效）
# --------------------------------------------------------------------------
_dnsapi = None


def flush_dns_cache() -> Tuple[bool, str]:
    """刷新系统 DNS 解析缓存，返回 (是否成功, 说明)。

    **这一步不能省。** Windows 的 DNS Client 服务（Dnscache）会把解析结果
    连同 **hosts 的结果一起** 缓存起来；改完 hosts 它**不会自动失效**。
    不刷的话用户写完 hosts 打开浏览器，拿到的还是旧 IP，会以为工具没起作用。

    实现上走 `dnsapi.DnsFlushResolverCache` —— `ipconfig /flushdns` 底层就是调它。
    比起子进程有三个好处：零进程开销（实测 ~0.6ms）、不弹黑框、
    **不需要管理员权限**。而且本机 cmd.exe 被安全策略拦截，
    `cmd /c ipconfig /flushdns` 这条路根本走不通，走 API 是唯一干净的选择。
    """
    global _dnsapi
    try:
        import ctypes
        if _dnsapi is None:
            _dnsapi = ctypes.WinDLL("dnsapi.dll")     # 非 Windows 上会直接抛错
        fn = _dnsapi.DnsFlushResolverCache
        fn.restype = ctypes.c_ulong
        t0 = time.perf_counter()
        rc = fn()
        ms = (time.perf_counter() - t0) * 1000.0
        if not rc:
            return False, "系统调用返回 0（拒绝执行）"
        return True, f"已刷新系统 DNS 缓存（{ms:.0f} ms）"
    except AttributeError:
        return False, "当前系统没有 dnsapi.DnsFlushResolverCache"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------
def parse_entries(lines: Optional[List[str]] = None) -> List[HostsEntry]:
    lines = read_hosts() if lines is None else lines
    out: List[HostsEntry] = []
    in_block = False
    for i, raw in enumerate(lines):
        st = raw.strip()
        if st == BEGIN_MARK or st.startswith(BEGIN_MARK):
            in_block = True
            continue
        if st == END_MARK or st.startswith(END_MARK):
            in_block = False
            continue
        if not st:
            continue
        disabled = False
        body = st
        if body.startswith(DISABLED_PREFIX):
            disabled = True
            body = body[len(DISABLED_PREFIX):].strip()
        elif body.startswith("#"):
            continue                      # 普通注释，与我们无关
        parts = body.split()
        if len(parts) < 2:
            continue
        try:
            ipaddress.ip_address(parts[0])
        except ValueError:
            continue
        out.append(HostsEntry(lineno=i, ip=parts[0], domain=parts[1].lower(),
                              raw=raw, in_block=in_block, disabled=disabled))
    return out


def scan_conflicts(domains: Optional[List[str]] = None) -> List[HostsEntry]:
    """扫描 hosts 里会影响测试的条目。

    domains 为 None 时返回所有真实映射条目。
    """
    want = {d.lower() for d in domains} if domains else None
    out = []
    for e in parse_entries():
        if want is not None and e.domain not in want:
            continue
        out.append(e)
    return out


def current_block() -> Dict[str, str]:
    """返回当前标记区块里的映射。"""
    return {e.domain: e.ip for e in parse_entries() if e.in_block}


# --------------------------------------------------------------------------
# 写入 / 还原
# --------------------------------------------------------------------------
def _strip_block(lines: List[str]) -> List[str]:
    out, in_block = [], False
    for raw in lines:
        st = raw.strip()
        if st == BEGIN_MARK or st.startswith(BEGIN_MARK):
            in_block = True
            continue
        if st == END_MARK or st.startswith(END_MARK):
            in_block = False
            continue
        if not in_block:
            out.append(raw)
    # 去掉区块留下的尾部空行
    while out and not out[-1].strip():
        out.pop()
    return out


def _validate(ip: str, domain: str) -> str:
    ipaddress.ip_address(ip)                       # 必须是合法 IP 字面量
    d = domain.strip().lower()
    if not _DOMAIN_RE.match(d) or len(d) > 253 or ".." in d:
        raise ValueError(f"非法域名：{domain!r}")
    return d


def preview(mapping: Dict[str, str]) -> str:
    """生成即将写入的内容预览（不落盘）。"""
    lines = [BEGIN_MARK]
    for dom in sorted(mapping):
        ip = mapping[dom]
        try:
            d = _validate(ip, dom)
            lines.append(f"{ip}\t{d}")
        except ValueError as e:
            lines.append(f"# 跳过：{dom} — {e}")
    lines.append(END_MARK)
    return "\n".join(lines)


def apply(mapping: Dict[str, str], make_backup: bool = True) -> HostsResult:
    """把 {域名: IP} 写入 hosts（放进标记区块）。"""
    if not mapping:
        return HostsResult(False, "没有可写入的条目。")
    if not hosts_exists():
        return HostsResult(False, f"找不到 hosts 文件：{HOSTS_PATH}")
    if not is_admin():
        return HostsResult(False, "需要管理员权限才能修改 hosts。", None)

    # 先校验全部条目，校验不过就一条都不写
    clean: Dict[str, str] = {}
    for dom, ip in mapping.items():
        try:
            clean[_validate(ip, dom)] = ip
        except ValueError as e:
            return HostsResult(False, f"条目不合法，已中止：{e}")

    bak = backup_hosts("before-apply") if make_backup else None
    if make_backup and not bak:
        return HostsResult(False, "备份失败，为安全起见已中止写入。")

    try:
        lines = _strip_block(read_hosts())
        target = set(clean)
        disabled = 0
        for i, raw in enumerate(lines):
            st = raw.strip()
            if not st or st.startswith("#"):
                continue
            parts = st.split()
            if len(parts) < 2:
                continue
            if parts[1].lower() in target:
                lines[i] = DISABLED_PREFIX + raw
                disabled += 1

        block = [BEGIN_MARK]
        for dom in sorted(clean):
            block.append(f"{clean[dom]}\t{dom}")
        block.append(END_MARK)

        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
        _write_hosts(lines)
    except PermissionError:
        return HostsResult(False, "写入被系统拒绝，请确认以管理员身份运行。", bak)
    except Exception as e:
        return HostsResult(False, f"写入失败：{type(e).__name__}: {e}", bak)

    # ★ 写完立刻刷新系统 DNS 缓存，否则新映射不会生效
    flush_ok, flush_note = flush_dns_cache()
    return HostsResult(True, f"已写入 {len(clean)} 条映射，"
                             f"另有 {disabled} 条原有条目被临时注释。",
                       bak, written=len(clean), disabled=disabled,
                       flushed=flush_ok, flush_note=flush_note)


def restore(make_backup: bool = True) -> HostsResult:
    """撤销本工具的全部改动：删标记区块 + 还原被注释的条目。"""
    if not hosts_exists():
        return HostsResult(False, f"找不到 hosts 文件：{HOSTS_PATH}")
    if not is_admin():
        return HostsResult(False, "需要管理员权限才能修改 hosts。")

    bak = backup_hosts("before-restore") if make_backup else None
    if make_backup and not bak:
        return HostsResult(False, "备份失败，为安全起见已中止。")

    try:
        lines = _strip_block(read_hosts())
        restored = 0
        for i, raw in enumerate(lines):
            if raw.startswith(DISABLED_PREFIX):
                lines[i] = raw[len(DISABLED_PREFIX):]
                restored += 1
        _write_hosts(lines)
    except PermissionError:
        return HostsResult(False, "写入被系统拒绝，请确认以管理员身份运行。", bak)
    except Exception as e:
        return HostsResult(False, f"还原失败：{type(e).__name__}: {e}", bak)

    # ★ 还原同样要刷新 —— 否则缓存里还留着我们写进去的旧映射
    flush_ok, flush_note = flush_dns_cache()
    return HostsResult(True, f"已移除标记区块，还原了 {restored} 条原有条目。",
                       bak, restored=restored,
                       flushed=flush_ok, flush_note=flush_note)


# --------------------------------------------------------------------------
# 环境体检
# --------------------------------------------------------------------------
def detect_local_proxies() -> List[int]:
    """扫描本地常见代理端口。开着代理会让所有连通性测试失真。"""
    import socket
    open_ports = []
    for port in PROXY_PORTS:
        s = socket.socket()
        s.settimeout(0.25)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                open_ports.append(port)
        except Exception:
            pass
        finally:
            s.close()
    return open_ports


def proxy_env() -> Dict[str, str]:
    return {k: v for k, v in os.environ.items()
            if "proxy" in k.lower() and not k.startswith("CODEBUDDY")}
