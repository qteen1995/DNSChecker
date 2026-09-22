# -*- coding: utf-8 -*-
"""生成演示截图：跑一次真实测速 + 真实污染检测，再逐页截图。

截图走 `winshot.capture`（PrintWindow），**不抓屏幕像素** —— 这一点很重要：
`ImageGrab` 抓的是屏幕，机器一锁屏就抓到锁屏壁纸，而且**不报错**，
演示图被静默覆盖成壁纸、看文件名完全正常。（踩过。）
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import ui
import winshot


def pump(app, sec):
    end = time.time() + sec
    while time.time() < end:
        app.update()
        time.sleep(0.02)


def save_shot(app, path):
    """抓窗口内容并保存。抓到纯色/失败就报错，绝不静默覆盖已有截图。"""
    img = winshot.capture(int(app.winfo_id()))
    if img is None:
        raise RuntimeError(f"抓窗口失败，未覆盖 {os.path.basename(path)}")
    ext = img.getextrema()
    if all(lo == hi for lo, hi in ext):
        raise RuntimeError(f"抓到纯色图 {ext}，疑似渲染失败，"
                           f"未覆盖 {os.path.basename(path)}")
    img.save(path)
    return img.size


app = ui.App()
app.geometry("1380x900+20+60")
app.attributes("-topmost", True)
pump(app, 3.0)
print("预填充行数：", len(app.tab_speed.rows))

# 只跑明文通道（IPv4/UDP + IPv4/TCP）、采样 1 次，尽快出结果。
# 明文 TCP 是本轮新增的通道，特意开着，让演示图里能同时看到两种传输的成绩。
app.var_v4.set(True)
app.var_v6.set(False)
app.var_udp.set(True)
app.var_tcp.set(True)
app.var_dot.set(False)
app.var_doh.set(False)
app.var_samples.set(1)
app._refresh_kind_hint()
app.start_speedtest()
print("测速中…")
t0 = time.time()
while app.worker and app.worker.is_alive():
    app.update()
    time.sleep(0.05)
print(f"测速结束，用时 {time.time() - t0:.1f} s")
pump(app, 2.0)
tested = [r for r in app.speed_results.values() if r.samples]
usable = [r for r in tested if r.usable]
refused = [r for r in tested if r.rcode == 5]
print(f"测速完成：{len(usable)}/{len(tested)} 可用，其中 {len(refused)} 个返回 REFUSED")
print(f"    这 {len(refused)} 个已按「不可用」处理：状态列写「拒绝」、沉到可用行的后面、"
      f"不进统计卡与 Top 榜")
for r in refused[:3]:
    print(f"    {r.name:22s} {r.kind_label:10s} {r.display:16s} "
          f"{r.best_ms:7.1f} ms -> 状态「{r.status}」 可用={r.usable}")
print(f"明文 TCP 通道有响应："
      f"{len([r for r in tested if r.kind == 'tcp4' and r.ok])} 个"
      f"（UDP 被阻断但 TCP 还通的服务器会在这里出现）")

# 污染检测：挑 5 个代表性域名，关掉海外基准参照（国内直连不通，省时间）
app.domains = ["github.com", "raw.githubusercontent.com", "pypi.org",
               "store.steampowered.com", "files.pythonhosted.org"]
app.tab_pollute._update_scope()
app.tab_pollute.var_ref.set(False)      # 海外源在国内直连不通，关掉省时间
app.tab_pollute.var_aaaa.set(True)      # 顺便验证 A + AAAA 合并
app.tab_pollute.start_check()
print("污染检测中…")
while app.pollute_worker and app.pollute_worker.is_alive():
    app.update()
    time.sleep(0.05)
pump(app, 2.0)
print("检测完成")

x0, y0 = app.winfo_rootx(), app.winfo_rooty()
w0, h0 = app.winfo_width(), app.winfo_height()
for key, name in (("speed", "demo_speed"), ("pollute", "demo_pollute"),
                  ("hosts", "demo_hosts"), ("log", "demo_log")):
    app.show_page(key)
    pump(app, 0.7)
    p = os.path.join(HERE, name + ".png")
    size = save_shot(app, p)
    print("已保存", os.path.basename(p), size)

# 再补一张：筛出 Google DNS，同一台服务器上 UDP 与 TCP 并排对比 ——
# 8.8.8.8 的 UDP 在国内被阻断、TCP 还通，是新增通道最直观的证明。
app.show_page("speed")
app.tab_speed.var_q.set("Google")
app.tab_speed._do_filter()
pump(app, 0.7)
p = os.path.join(HERE, "demo_tcp.png")
size = save_shot(app, p)
print("已保存", os.path.basename(p), size)
app.destroy()
print("完成")
