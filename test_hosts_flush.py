# -*- coding: utf-8 -*-
"""验证 hosts 写入 / 还原之后确实刷新了系统 DNS 缓存。

**全程在临时文件上做，绝不碰真实 hosts。**
把 `HOSTS_PATH` 指向临时文件、把 `is_admin()` 假装成 True，就能把
`apply()` / `restore()` 的完整流程（含备份、写区块、注释既有条目、刷缓存）
跑一遍。最后再核对真实 hosts 的内容哈希没变，确认测试真的没越界。
"""
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import hostsmgr as H

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


SEED = ("# 原始 hosts 注释行\r\n"
        "127.0.0.1  localhost\r\n"
        "10.0.0.1  github.com\r\n")


def real_signature():
    """真实 hosts 的内容指纹（用来证明测试没动它）。"""
    if not H.hosts_exists():
        return "（不存在）"
    with open(H.HOSTS_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


# 开跑前先记下真实 hosts 的指纹，跑完要一模一样
REAL_BEFORE = real_signature()
REAL_HOSTS = H.HOSTS_PATH
print(f"真实 hosts：{REAL_HOSTS}")
print(f"内容指纹  ：{REAL_BEFORE}\n")


def with_fake_hosts(fn):
    tmpd = tempfile.mkdtemp(prefix="hoststest-")
    fake = os.path.join(tmpd, "hosts")
    with open(fake, "w", encoding="utf-8", newline="") as f:
        f.write(SEED)
    real_path, real_admin = H.HOSTS_PATH, H.is_admin
    H.HOSTS_PATH = fake
    H.is_admin = lambda: True
    try:
        return fn(fake)
    finally:
        H.HOSTS_PATH = real_path
        H.is_admin = real_admin
        shutil.rmtree(tmpd, ignore_errors=True)


def read(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8", "replace")


print("=" * 74)
print("① dnsapi.DnsFlushResolverCache 能不能用（这是 ipconfig /flushdns 的底层）")
print("=" * 74)

step("直接调用 flush_dns_cache()", lambda: (
    (lambda ok, note: note + ("" if ok else "  ← 失败"))(*H.flush_dns_cache())))


def fast_enough():
    import time
    t0 = time.perf_counter()
    for _ in range(5):
        H.flush_dns_cache()
    ms = (time.perf_counter() - t0) / 5 * 1000
    return f"平均 {ms:.1f} ms / 次（零子进程、不弹黑框、不需要管理员）"


step("调用开销", fast_enough)

print()
print("=" * 74)
print("② 写入 hosts 后自动刷新")
print("=" * 74)


def apply_flushes():
    def run(fake):
        res = H.apply({"github.com": "20.205.243.166",
                       "pypi.org": "151.101.128.223"})
        assert res.ok, f"写入失败：{res.message}"
        assert res.flushed is True, f"没刷新缓存：flushed={res.flushed} {res.flush_note}"
        body = read(fake)
        assert H.BEGIN_MARK in body and "20.205.243.166\tgithub.com" in body
        assert H.DISABLED_PREFIX + "10.0.0.1  github.com" in body, "原有条目没被注释"
        assert "# 原始 hosts 注释行" in body, "无关的注释行被动过了"
        return f"写入 {res.written} 条，flushed={res.flushed}，{res.flush_note}"
    return with_fake_hosts(run)


step("apply() 写完后刷新缓存", apply_flushes)


def detail_mentions_flush():
    def run(fake):
        res = H.apply({"github.com": "20.205.243.166"})
        d = res.detail()
        assert "已刷新系统 DNS 缓存" in d, f"详细说明里没提刷新：{d!r}"
        assert "重启浏览器" in d, "没提醒浏览器自己的缓存"
        return d.replace("\n", " ⏎ ")[:110] + " …"
    return with_fake_hosts(run)


step("完成提示里写明已刷新 + 浏览器缓存提醒", detail_mentions_flush)

print()
print("=" * 74)
print("③ 还原 hosts 后同样刷新")
print("=" * 74)


def restore_flushes():
    def run(fake):
        H.apply({"github.com": "20.205.243.166"})
        res = H.restore()
        assert res.ok, f"还原失败：{res.message}"
        assert res.flushed is True, f"还原后没刷新：flushed={res.flushed}"
        body = read(fake)
        assert H.BEGIN_MARK not in body, "标记区块没删掉"
        assert H.DISABLED_PREFIX not in body, "注释没撤销"
        assert "10.0.0.1  github.com" in body, "原有条目没还原"
        assert body.replace("\r\n", "\n") == SEED.replace("\r\n", "\n"), \
            "还原后内容与原始不一致"
        return f"还原 {res.restored} 条，flushed={res.flushed}，内容逐字还原 ✓"
    return with_fake_hosts(run)


step("restore() 后刷新缓存且内容逐字还原", restore_flushes)

print()
print("=" * 74)
print("④ 刷新失败的提示（构造场景，不真制造失败）")
print("=" * 74)


def failure_hint():
    res = H.HostsResult(True, "已写入 2 条映射。", None, written=2,
                        flushed=False, flush_note="系统调用返回 0（拒绝执行）")
    d = res.detail()
    assert "未能刷新系统 DNS 缓存" in d
    assert "ipconfig /flushdns" in d, "失败时没给出补救办法"
    return "失败时提示手动 ipconfig /flushdns ✓"


step("刷新失败要给出补救办法", failure_hint)


def not_done_hint():
    res = H.HostsResult(True, "已写入 1 条映射。", None, written=1)
    d = res.detail()
    assert "没有刷新系统 DNS 缓存" in d
    return "漏刷时也能被发现 ✓"


step("flushed=None 也要显式提示", not_done_hint)

print()
print("=" * 74)
print("⑤ 确认测试没有碰过真实 hosts")
print("=" * 74)


def real_untouched():
    now = real_signature()
    if now != REAL_BEFORE:
        raise AssertionError(f"真实 hosts 被动了！{REAL_BEFORE} -> {now}")
    return f"{REAL_HOSTS} 指纹未变（{now}）"


step("真实 hosts 内容一字未改", real_untouched)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
