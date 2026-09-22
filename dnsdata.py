# -*- coding: utf-8 -*-
"""内置公共 DNS 清单。

数据来源（2026-09-21 抓取）：
    https://dns.iui.im/         —— IPv4 / DoH / DoT
    https://dns.iui.im/ipv6/    —— IPv6 / DoH / DoT

两个页面的条目已按「服务名」合并：同一家 DNS 的 v4、v6、DoH、DoT 归到一条记录，
因为用户真正关心的是「这家 DNS 好不好用」，而不是「这个 IP 通不通」。

字段：
    name    服务名
    group   分类（国内 / 港台 / 国外 / 去广告 / 高校 / 电信 / 联通 / 移动）
    v4      IPv4 明文 UDP:53 地址
    v6      IPv6 明文 UDP:53 地址
    dot     DoT 主机名（:853）
    doh     DoH URL
    port    非 53 端口（少数服务用自定义端口）
    note    备注（已停服 / 数据存疑等）
"""

VERSION = "2026-09-21"
SOURCES = ["https://dns.iui.im/", "https://dns.iui.im/ipv6/"]

GROUPS = ["国内", "港台", "国外", "去广告", "高校", "电信", "联通", "移动"]

DEFAULT_ENTRIES = [
    # ---------------- 国内 ----------------
    {"name": "114 DNS", "group": "国内", "v4": ["114.114.114.114", "114.114.115.115"]},
    {"name": "114 DNS 安全版", "group": "国内", "v4": ["114.114.114.119", "114.114.115.119"]},
    {"name": "114 DNS 家庭版", "group": "国内", "v4": ["114.114.114.110", "114.114.115.110"]},
    {"name": "阿里 AliDNS", "group": "国内",
     "v4": ["223.5.5.5", "223.6.6.6"], "v6": ["2400:3200::1", "2400:3200:baba::1"],
     "dot": ["dns.alidns.com"],
     "doh": ["https://dns.alidns.com/dns-query", "https://223.5.5.5/dns-query",
             "https://223.6.6.6/dns-query", "https://[2400:3200::1]/dns-query",
             "https://[2400:3200:baba::1]/dns-query"]},
    {"name": "百度 BaiduDNS", "group": "国内",
     "v4": ["180.76.76.76"], "v6": ["2400:da00::6666"]},
    {"name": "腾讯 DNSPod", "group": "国内",
     "v4": ["119.29.29.29", "182.254.116.116", "119.28.28.28", "182.254.118.118"],
     "v6": ["2402:4e00::", "2402:4e00:1::"],
     "dot": ["dot.pub", "1.12.12.12", "120.53.53.53"],
     "doh": ["https://doh.pub/dns-query", "https://1.12.12.12/dns-query",
             "https://120.53.53.53/dns-query", "https://sm2.doh.pub/dns-query"]},
    {"name": "CNNIC SDNS", "group": "国内",
     "v4": ["1.2.4.8", "210.2.4.8"], "v6": ["2001:dc7:1000::1"]},
    {"name": "ChinaIPv6 PDNS", "group": "国内",
     "v6": ["240C::6666", "240C::6644"],
     "dot": ["dns.ipv6dns.com"], "doh": ["https://dns.ipv6dns.com/dns-query"]},
    {"name": "OneDNS 拦截版", "group": "国内",
     "v4": ["117.50.22.22", "52.80.66.66"],
     "v6": ["2400:7fc0:849e:200::4", "2404:c2c0:85d8:901::4"],
     "dot": ["dot.onedns.net"], "doh": ["https://doh.onedns.net/dns-query"]},
    {"name": "OneDNS 纯净版", "group": "国内",
     "v4": ["117.50.10.10", "52.80.52.52"],
     "v6": ["2400:7fc0:849e:200::8", "2404:c2c0:85d8:901::8"],
     "dot": ["dot-pure.onedns.net"], "doh": ["https://doh-pure.onedns.net/dns-query"]},
    {"name": "OneDNS 家庭版", "group": "国内",
     "v4": ["117.50.60.30", "52.80.60.30"],
     "dot": ["dot-home.onedns.net"], "doh": ["https://doh-home.onedns.net/dns-query"]},
    {"name": "DNS派 DNS PAI", "group": "国内",
     "v4": ["101.226.4.6", "218.30.118.6", "123.125.81.6", "140.207.198.6"]},
    {"name": "牙木网络", "group": "国内", "v4": ["1.1.8.8", "1.1.8.9"]},
    {"name": "360 DNS", "group": "国内", "note": "与 DNS派 同 IP 组",
     "v4": ["101.226.4.6", "218.30.118.6", "123.125.81.6", "140.207.198.6"],
     "dot": ["dot.360.cn"], "doh": ["https://doh.360.cn/dns-query"]},
    {"name": "火山引擎 DNS", "group": "国内", "v4": ["180.184.1.1", "180.184.2.2"]},
    {"name": "中科院网络信息中心", "group": "国内", "v6": ["2001:cc0:2fff:1::6666"]},
    {"name": "科技网 IPv6 DNS", "group": "国内", "v6": ["2001:cc0:2fff:2::6"]},

    # ---------------- 港台 ----------------
    {"name": "台湾 Quad 101", "group": "港台",
     "v4": ["101.101.101.101", "101.102.103.104"],
     "v6": ["2001:de4::101", "2001:de4::102"],
     "doh": ["https://dns.twnic.tw/dns-query"]},
    {"name": "中国香港 宽频 DNS", "group": "港台", "v4": ["203.80.96.10", "203.80.96.9"]},
    {"name": "中国香港 网上行宽频", "group": "港台", "v4": ["218.102.23.228", "203.198.7.66"]},
    {"name": "中国香港 有线宽频 i-Cable", "group": "港台", "v4": ["61.10.0.130", "61.10.1.130"]},
    {"name": "中国香港 和记环球电讯", "group": "港台", "v4": ["202.181.240.44", "210.0.255.251"]},
    {"name": "中国香港 HKNet 宽频", "group": "港台", "v4": ["202.67.240.222"]},
    {"name": "中国香港 PCCW DNS", "group": "港台", "v4": ["202.153.97.2", "202.153.97.130"]},
    {"name": "中国香港 Pacific Internet", "group": "港台", "v4": ["202.14.67.4", "202.14.67.14"]},
    {"name": "中国香港 CPCNet DNS", "group": "港台", "v4": ["202.76.4.1", "202.76.4.2"]},
    {"name": "中国香港 KDDI DNS", "group": "港台", "v4": ["202.177.2.2", "202.177.2.3"]},
    {"name": "中国香港 iAdvantage DNS", "group": "港台",
     "v4": ["202.85.128.32", "202.85.128.33", "203.194.239.32", "202.85.170.89"]},
    {"name": "中国台湾 中华电信", "group": "港台",
     "v4": ["168.95.192.1", "168.95.1.1"], "doh": ["https://dns.hinet.net/dns-query"]},
    {"name": "中国香港 西门子服务器", "group": "港台", "v4": ["112.121.178.187"]},

    # ---------------- 国外 ----------------
    {"name": "Google Public DNS", "group": "国外",
     "v4": ["8.8.8.8", "8.8.4.4"], "v6": ["2001:4860:4860::8888", "2001:4860:4860::8844"],
     "dot": ["dns.google"],
     "doh": ["https://dns.google/dns-query", "https://[2001:4860:4860::64]/dns-query",
             "https://[2001:4860:4860::6464]/dns-query"]},
    {"name": "IBM Quad9", "group": "国外",
     "v4": ["9.9.9.9", "149.112.112.112"], "v6": ["2620:fe::fe", "2620:fe::9"],
     "doh": ["https://dns.quad9.net/dns-query", "https://dns11.quad9.net/dns-query"]},
    {"name": "Cisco OpenDNS", "group": "国外",
     "v4": ["208.67.222.222", "208.67.220.220"],
     "v6": ["2620:119:35::35", "2620:119:53::53"],
     "doh": ["https://doh.opendns.com/dns-query",
             "https://doh.familyshield.opendns.com/dns-query"]},
    {"name": "Level3 DNS", "group": "国外", "v4": ["4.2.2.1", "4.2.2.2"]},
    {"name": "韩国 KT DNS", "group": "国外", "v4": ["168.126.63.1", "168.126.63.2"]},
    {"name": "Cloudflare 1.1.1.1", "group": "国外",
     "v4": ["1.1.1.1", "1.0.0.1"], "v6": ["2606:4700:4700::1111", "2606:4700:4700::1001"],
     "dot": ["one.one.one.one", "1dot1dot1dot1.cloudflare-dns.com"],
     "doh": ["https://cloudflare-dns.com/dns-query", "https://1.1.1.1/dns-query",
             "https://1.0.0.1/dns-query", "https://[2606:4700:4700::1111]/dns-query",
             "https://[2606:4700:4700::1001]/dns-query"]},
    {"name": "Free DNS", "group": "国外", "v4": ["37.235.1.174", "37.235.1.177"]},
    {"name": "Oracle DynDNS", "group": "国外", "v4": ["216.146.35.35", "216.146.36.36"]},
    {"name": "Comodo Secure DNS", "group": "国外", "v4": ["8.26.56.26", "8.20.247.20"]},
    {"name": "Verisign DNS", "group": "国外",
     "v4": ["64.6.64.6", "64.6.65.6"], "v6": ["2620:74:1b::1:1", "2620:74:1c::2:2"]},
    {"name": "Yandex DNS", "group": "国外", "v4": ["77.88.8.8", "77.88.8.1"]},
    {"name": "Freenom DNS", "group": "国外", "v4": ["80.80.80.80", "80.80.81.81"]},
    {"name": "AdGuard DNS 默认", "group": "国外",
     "v4": ["94.140.14.14", "94.140.15.15"],
     "v6": ["2a00:5a60::ad1:0ff", "2a00:5a60::ad2:0ff"],
     "dot": ["dns.adguard.com"], "doh": ["https://dns.adguard.com/dns-query"]},
    {"name": "AdGuard DNS 家庭保护", "group": "国外",
     "v4": ["94.140.14.15", "94.140.15.16"],
     "v6": ["2a00:5a60::bad1:0ff", "2a00:5a60::bad2:0ff"],
     "dot": ["dns-family.adguard.com"],
     "doh": ["https://dns-family.adguard.com/dns-query"]},
    {"name": "Neustar UltraDNS", "group": "国外", "note": "IPv6 原文有一条重复已去重",
     "v4": ["156.154.70.1", "156.154.71.1", "156.154.70.5", "156.154.71.5"],
     "v6": ["2610:a1:1018::1", "2610:a1:1019::1", "2610:a1:1018::5"]},
    {"name": "柬埔寨 DNS", "group": "国外",
     "v4": ["103.197.104.178", "103.197.106.75", "203.189.136.148"]},
    {"name": "UCOM DNS 日本", "group": "国外", "v4": ["203.112.2.4"]},
    {"name": "DNS.WATCH", "group": "国外",
     "v4": ["84.200.69.80", "84.200.70.40"],
     "v6": ["2001:1608:10:25::1c04:b12f", "2001:1608:10:25::9249:d69b"]},
    {"name": "SafeDNS", "group": "国外", "v4": ["195.46.39.39", "195.46.39.40"]},
    {"name": "puntCAT DNS", "group": "国外", "v4": ["109.69.8.51"], "v6": ["2a00:1508:0:4::9"]},
    {"name": "UncensoredDNS", "group": "国外",
     "v4": ["91.239.100.100", "89.233.43.71"],
     "v6": ["2001:67c:28a4::", "2a01:3a0:53:53::"]},
    {"name": "GreenTeamDNS", "group": "国外", "v4": ["81.218.119.11", "209.88.198.133"]},
    {"name": "DNS.SB", "group": "国外",
     "v4": ["185.222.222.222", "45.11.45.11"], "v6": ["2a09::", "2a11::"],
     "dot": ["dot.sb"], "doh": ["https://doh.dns.sb/dns-query", "https://doh.sb/dns-query"]},
    {"name": "Hurricane Electric", "group": "国外", "v4": ["74.82.42.42", "66.220.18.42"]},
    {"name": "DNSReactor", "group": "国外", "v4": ["104.236.210.29", "45.55.155.25"]},
    {"name": "CleanBrowsing 安全过滤", "group": "国外",
     "v4": ["185.228.168.9", "185.228.169.9"],
     "v6": ["2a0d:2a00:1::2", "2a0d:2a00:2::2"]},
    {"name": "CleanBrowsing 成人过滤", "group": "国外",
     "v4": ["185.228.168.10", "185.228.169.11"],
     "v6": ["2a0d:2a00:1::1", "2a0d:2a00:2::1"]},
    {"name": "CleanBrowsing 家庭保护", "group": "国外",
     "v4": ["185.228.168.168", "185.228.169.168"],
     "v6": ["2a0d:2a00:1::", "2a0d:2a00:2::"],
     "dot": ["dns.cleanbrowsing.org"],
     "doh": ["https://doh.cleanbrowsing.org/doh/family-filter/"]},
    {"name": "PowerDNS", "group": "国外", "doh": ["https://doh.powerdns.org"]},
    {"name": "Worldlink DNS", "group": "国外", "v4": ["202.79.32.33", "202.79.32.34"]},
    {"name": "日本 IIJ DNS", "group": "国外", "doh": ["https://public.dns.iij.jp/dns-query"]},
    {"name": "Blahdns 日本", "group": "国外", "doh": ["https://doh-jp.blahdns.com/dns-query"]},
    {"name": "Mullvad DNS 常规", "group": "国外", "v4": ["194.242.2.2"],
     "doh": ["https://dns.mullvad.net/dns-query"]},
    {"name": "Mullvad DNS 去广告", "group": "国外", "v4": ["194.242.2.3"],
     "doh": ["https://adblock.dns.mullvad.net/dns-query"]},
    {"name": "Mullvad DNS 去广告+恶意", "group": "国外", "v4": ["194.242.2.4"],
     "doh": ["https://base.dns.mullvad.net/dns-query"]},
    {"name": "Mullvad DNS 完全", "group": "国外", "v4": ["194.242.2.9"],
     "doh": ["https://all.dns.mullvad.net/dns-query"]},
    {"name": "NTT DNS", "group": "国外", "v6": ["2001:418:3ff::53", "2001:418:3ff::1:53"]},

    # ---------------- 去广告 / 自建 ----------------
    {"name": "PdoMo DNS", "group": "去广告", "note": "原站标注已停服",
     "v4": ["101.132.183.99", "47.98.124.222"]},
    {"name": "Pure DNS", "group": "去广告", "note": "原站标注已停服",
     "v4": ["123.207.137.88", "115.159.220.214"]},
    {"name": "CuteDns", "group": "去广告", "note": "原站标注已停服",
     "v4": ["120.77.212.84", "101.236.28.23"]},
    {"name": "HI!XNS DNS", "group": "去广告", "v4": ["103.219.29.29"]},
    {"name": "不知名 DNS", "group": "去广告",
     "v4": ["180.97.235.30", "115.159.96.69", "123.207.137.88", "123.206.21.48"]},
    {"name": "骆驼云 DNS", "group": "去广告", "note": "原站标注已停服", "v4": ["63.223.94.66"]},
    {"name": "P站 DNS", "group": "去广告",
     "v4": ["123.207.137.88", "115.159.220.214", "115.159.146.99", "123.206.21.48"]},
    {"name": "红鱼 rubyfish", "group": "去广告",
     "dot": ["dns.rubyfish.cn", "v6.rubyfish.cn"],
     "doh": ["https://rubyfish.cn/dns-query", "https://dns.rubyfish.cn/dns-query",
             "https://v6.rubyfish.cn/dns-query"]},
    {"name": "Google hosts 防污染", "group": "去广告",
     "v4": ["113.205.16.215", "140.143.226.193"],
     "v6": ["2408:8262:12bd:1f22::2333", "2408:8262:12bd:1f22::3332"]},
    {"name": "Clean DNS 无污染", "group": "去广告", "port": 5353,
     "note": "监听 5353 端口", "v4": ["123.207.22.79"]},
    {"name": "Clean DNS 去广告", "group": "去广告", "v4": ["111.230.37.44"]},
    {"name": "RollingDNS 防污染", "group": "去广告", "v4": ["110.43.41.122", "150.242.98.63"]},
    {"name": "Geek DNS", "group": "去广告", "note": "支持 EDNS-Client-Subnet",
     "doh": ["https://i.233py.com/dns-query", "https://dns.233py.com/dns-query"]},
    {"name": "iQDNS", "group": "去广告",
     "dot": ["cn-east.iqiqzz.com", "cn-south.iqiqzz.com"],
     "doh": ["https://cn-east.iqiqzz.com/dns-query", "https://cn-south.iqiqzz.com/dns-query"]},
    {"name": "18bit DNS", "group": "去广告",
     "dot": ["dns.18bit.cn"], "doh": ["https://doh.18bit.cn/dns-query"]},
    {"name": "MoeDNS", "group": "去广告",
     "v4": ["221.131.165.165", "36.156.184.156"],
     "dot": ["pdns.itxe.net"], "doh": ["https://pdns.itxe.net/dns-query"]},
    {"name": "apad.pro 无污染", "group": "去广告", "doh": ["https://doh.apad.pro/dns-query"]},
    {"name": "清新云 DNS", "group": "去广告",
     "dot": ["dns.ipv4dns.com"], "doh": ["https://dns.ipv4dns.com/dns-query"]},
    {"name": "网友自建去广告（日本）", "group": "去广告",
     "v6": ["2001:19f0:7001:46b8:5400:01ff:feac:13a7"]},

    # ---------------- 高校 ----------------
    {"name": "中科大 DNS", "group": "高校",
     "v4": ["202.141.162.123", "202.38.93.153", "202.141.176.93"]},
    {"name": "清华大学 TUNA", "group": "高校", "v4": ["101.6.6.6"], "v6": ["2001:da8::666"]},
    {"name": "上海交大 IPv6", "group": "高校", "v6": ["2001:da8:8000:1:202:120:2:101"]},
    {"name": "北京邮电大学 IPv6", "group": "高校",
     "v6": ["2001:da8:202:10::36", "2001:da8:202:10::37"]},
    {"name": "北京科技大学 IPv6", "group": "高校", "v6": ["2001:da8:208:10::6"]},
    {"name": "中科大 IPv6", "group": "高校", "note": "原文与清华 TUNA 同地址，存疑",
     "v6": ["2001:da8::666"]},
    {"name": "浙江大学 IPv6", "group": "高校",
     "v6": ["2001:da8:e000:94::8", "2001:da8:e000:92::8"]},
    {"name": "南京大学 IPv6", "group": "高校", "v6": ["2001:da8:1007::8888"]},

    # ---------------- 电信 ----------------
    {"name": "中国电信 IPv6 通用", "group": "电信",
     "v6": ["240e:4c:4008::1", "240e:4c:4808::1"]},
    {"name": "安徽电信 DNS", "group": "电信", "v4": ["61.132.163.68", "202.102.213.68"]},
    {"name": "北京电信 DNS", "group": "电信", "v4": ["219.141.136.10", "219.141.140.10"]},
    {"name": "重庆电信 DNS", "group": "电信",
     "v4": ["61.128.192.68", "61.128.128.68"], "v6": ["240e:47:0:701::1"]},
    {"name": "福建电信 DNS", "group": "电信", "v4": ["218.85.152.99", "218.85.157.99"]},
    {"name": "甘肃电信 DNS", "group": "电信", "v4": ["202.100.64.68", "61.178.0.93"]},
    {"name": "广东电信 DNS", "group": "电信",
     "v4": ["202.96.128.86", "202.96.128.166", "202.96.134.33", "202.96.128.68"],
     "v6": ["240e:1f:1::1", "240e:1f:1::33"]},
    {"name": "广西电信 DNS", "group": "电信", "v4": ["202.103.225.68", "202.103.224.68"]},
    {"name": "贵州电信 DNS", "group": "电信", "v4": ["202.98.192.67", "202.98.198.167"]},
    {"name": "河南电信 DNS", "group": "电信", "v4": ["222.88.88.88", "222.85.85.85"]},
    {"name": "黑龙江电信 DNS", "group": "电信", "v4": ["219.147.198.230", "219.147.198.242"]},
    {"name": "湖北电信 DNS", "group": "电信", "v4": ["202.103.24.68", "202.103.0.68"]},
    {"name": "湖南电信 DNS", "group": "电信", "v4": ["222.246.129.80", "59.51.78.211"]},
    {"name": "江苏电信 DNS", "group": "电信",
     "v4": ["218.2.2.2", "218.4.4.4", "61.147.37.1", "218.2.135.1"],
     "v6": ["240e:5a::6666", "240e:5b::6666"]},
    {"name": "江西电信 DNS", "group": "电信", "v4": ["202.101.224.69", "202.101.226.68"]},
    {"name": "内蒙古电信 DNS", "group": "电信", "v4": ["219.148.162.31", "222.74.39.50"]},
    {"name": "山东电信 DNS", "group": "电信", "v4": ["219.146.1.66", "219.147.1.66"]},
    {"name": "陕西电信 DNS", "group": "电信", "v4": ["218.30.19.40", "61.134.1.4"]},
    {"name": "上海电信 DNS", "group": "电信",
     "v4": ["202.96.209.133", "116.228.111.118", "202.96.209.5", "108.168.255.118"]},
    {"name": "四川电信 DNS", "group": "电信",
     "v4": ["61.139.2.69", "218.6.200.139"],
     "v6": ["240e:56:4000:8000::69", "240e:56:4000::218"]},
    {"name": "天津电信 DNS", "group": "电信", "v4": ["219.150.32.132", "219.146.0.132"]},
    {"name": "云南电信 DNS", "group": "电信", "v4": ["222.172.200.68", "61.166.150.123"]},
    {"name": "浙江电信 DNS", "group": "电信",
     "v4": ["202.101.172.35", "61.153.177.196", "61.153.81.75", "60.191.244.5"],
     "v6": ["240e:1c:200::1", "240e:1c:200::2"]},
    {"name": "浙江嘉兴电信 DNS", "group": "电信", "v4": ["220.189.127.106", "220.189.127.107"]},

    # ---------------- 联通 ----------------
    {"name": "北京联通 DNS", "group": "联通",
     "v4": ["123.123.123.123", "123.123.123.124", "202.106.0.20", "202.106.195.68"]},
    {"name": "重庆联通 DNS", "group": "联通",
     "v4": ["221.5.203.98", "221.7.92.98"], "v6": ["2408:8663::2", "2408:8662::2"]},
    {"name": "广东联通 DNS", "group": "联通", "v4": ["210.21.196.6", "221.5.88.88"]},
    {"name": "河北联通 DNS", "group": "联通", "v4": ["202.99.160.68", "202.99.166.4"]},
    {"name": "河南联通 DNS", "group": "联通", "v4": ["202.102.224.68", "202.102.227.68"]},
    {"name": "黑龙江联通 DNS", "group": "联通",
     "v4": ["202.97.224.69", "202.97.224.68"], "v6": ["2408:8000::8", "2408:8888::8"]},
    {"name": "吉林联通 DNS", "group": "联通", "v4": ["202.98.0.68", "202.98.5.68"]},
    {"name": "江苏联通 DNS", "group": "联通",
     "v4": ["221.6.4.66", "221.6.4.67", "58.240.57.33"],
     "v6": ["2408:8000:aaaa::2", "2408:8888::8"]},
    {"name": "内蒙古联通 DNS", "group": "联通", "v4": ["202.99.224.68", "202.99.224.8"]},
    {"name": "山东联通 DNS", "group": "联通",
     "v4": ["202.102.128.68", "202.102.152.3", "202.102.134.68", "202.102.154.3"]},
    {"name": "山西联通 DNS", "group": "联通", "v4": ["202.99.192.66", "202.99.192.68"]},
    {"name": "陕西联通 DNS", "group": "联通", "v4": ["221.11.1.67", "221.11.1.68"]},
    {"name": "上海联通 DNS", "group": "联通", "v4": ["210.22.70.3", "210.22.84.3"]},
    {"name": "四川联通 DNS", "group": "联通", "v4": ["119.6.6.6", "124.161.87.155"]},
    {"name": "天津联通 DNS", "group": "联通", "v4": ["202.99.104.68", "202.99.96.68"]},
    {"name": "浙江联通 DNS", "group": "联通", "v4": ["221.12.1.227", "221.12.33.227"]},
    {"name": "辽宁联通 DNS", "group": "联通", "v4": ["202.96.69.38", "202.96.64.68"]},

    # ---------------- 移动 ----------------
    {"name": "江苏移动 DNS", "group": "移动", "v4": ["221.131.143.69", "112.4.0.55"]},
    {"name": "安徽移动 DNS", "group": "移动", "v4": ["211.138.180.2", "211.138.180.3"]},
    {"name": "山东移动 DNS", "group": "移动", "v4": ["218.201.96.130", "211.137.191.26"]},
    {"name": "四川移动 DNS", "group": "移动",
     "v4": ["223.87.238.22"], "v6": ["2409:8062:2000:1::1", "2409:8062:2000:1::2"]},
    {"name": "重庆移动 DNS", "group": "移动", "v4": ["183.230.98.97", "183.230.127.17"]},
    {"name": "浙江移动 IPv6", "group": "移动",
     "v6": ["2409:8028:2000::1111", "2409:8028:2000::2222"]},
]


# 污染 / 可达性检测的默认目标域名
DEFAULT_DOMAINS = [
    {"domain": "github.com", "tag": "GitHub"},
    {"domain": "raw.githubusercontent.com", "tag": "GitHub"},
    {"domain": "objects.githubusercontent.com", "tag": "GitHub"},
    {"domain": "codeload.github.com", "tag": "GitHub"},
    {"domain": "pypi.org", "tag": "PyPI"},
    {"domain": "files.pythonhosted.org", "tag": "PyPI"},
    {"domain": "store.steampowered.com", "tag": "Steam"},
    {"domain": "steamcommunity.com", "tag": "Steam"},
    {"domain": "api.steampowered.com", "tag": "Steam"},
    {"domain": "cdn.akamai.steamstatic.com", "tag": "Steam"},
    {"domain": "media.steampowered.com", "tag": "Steam"},
]


def iter_endpoints(entries):
    """把服务条目摊平成一堆可测试端点。

    返回 (key, kind, payload) 三元组：
        kind = udp4 / udp6 / tcp4 / tcp6 / dot / doh
        payload 是各通道需要的信息

    明文 TCP 与明文 UDP 并列成两条独立通道：国内实测存在「UDP:53 被封、
    TCP:53 还通」的服务器（如 8.8.8.8），只有两条都测才看得见。
    """
    for idx, e in enumerate(entries):
        name = e.get("name") or f"entry-{idx}"
        group = e.get("group") or "未分类"
        port = int(e.get("port") or 53)
        for ip in e.get("v4") or []:
            yield (f"{name}|udp4|{ip}", "udp4",
                   {"name": name, "group": group, "server": ip, "port": port,
                    "display": ip})
            yield (f"{name}|tcp4|{ip}", "tcp4",
                   {"name": name, "group": group, "server": ip, "port": port,
                    "display": ip})
        for ip in e.get("v6") or []:
            yield (f"{name}|udp6|{ip}", "udp6",
                   {"name": name, "group": group, "server": ip, "port": port,
                    "display": ip})
            yield (f"{name}|tcp6|{ip}", "tcp6",
                   {"name": name, "group": group, "server": ip, "port": port,
                    "display": ip})
        for host in e.get("dot") or []:
            yield (f"{name}|dot|{host}", "dot",
                   {"name": name, "group": group, "server": host, "port": 853,
                    "display": host})
        for url in e.get("doh") or []:
            yield (f"{name}|doh|{url}", "doh",
                   {"name": name, "group": group, "server": url, "port": 443,
                    "display": url})
