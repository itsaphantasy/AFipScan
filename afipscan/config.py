# -*- coding: utf-8 -*-
"""配置模块：读取/生成 config.json，提供全局常量与调试日志。"""

import ipaddress
import json
import os
import sys
import tempfile
import time
import __main__


# 默认配置：首次运行没有 config.json 时自动生成这份
# 推荐端口：端口留空时默认全部扫描
RECOMMEND_PORTS = [443, 8443, 2053, 2083, 2087, 2096]
RECOMMEND_PORTS_STR = ",".join(map(str, RECOMMEND_PORTS))
ALL_OPEN = "ALL OPEN"

# Cloudflare 官方 IPv4 段（https://www.cloudflare.com/ips-v4，内置避免每次拉取）
CLOUDFLARE_IPV4 = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
]
_CF_NETS = [ipaddress.ip_network(c) for c in CLOUDFLARE_IPV4]


def is_cloudflare_ip(ip):
    """判断 IP 是否属于 Cloudflare 官方 IPv4 段（非 CF 的中转机/云厂商节点排除）。"""
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except Exception:
        return False
    return any(addr in n for n in _CF_NETS)

DEFAULT_CONFIG = {
    "sni": "www.cloudflare.com",
    "panel": "",
    "admin_password": "",
    "port_default": "ALL OPEN",
    "top_default": 12,
    "workers_default": "12/3",
    "limit_default": 300,
    "region_filter_enabled": False,
    "region_filter": [],
    "proxy_url": "http://127.0.0.1:20808",
    "candidate_urls": [
        "https://raw.githubusercontent.com/HandsomeMJZ/cfip/refs/heads/main/best_ips.txt",
        "https://raw.githubusercontent.com/svip-s/cloudflare_ip/refs/heads/main/best_ips.txt",
        "https://cf.junzhen.qzz.io/best_ips_bj.txt",
    ],
    "subscription_url": "",
    "joey_panel": "",
    "joey_password": "",
    "joey_subscription_url": "",
    "builtin_ips": [
        "91.110.174.202:8443#HK", "91.110.174.205:8443#HK", "91.110.174.210:8443#HK",
        "43.129.195.232:443#HK", "54.64.78.192:443#JP", "52.77.54.144:443#SG",
        "207.57.134.29:443#HK", "54.95.106.234:443#HK", "57.180.60.121:443#HK",
        "38.55.195.57:443#HK", "150.109.11.223:443#SG", "198.20.153.247:443#HK",
    ],
}

# VPS 总源（程序强制默认源）：本地识别地区分类后上传 VPS，程序填地区码时直接拉对应地区文件
VPS_ALL_URL = "https://vps.example.com/ALLIP/all.txt"
VPS_BASE = "https://vps.example.com/ALLIP/"


def vps_region_url(code):
    """按地区二字码返回 VPS 对应文件地址(如 HK -> .../HK.txt)。"""
    return "%s%s.txt" % (VPS_BASE, (code or "").strip().upper())



# 源友好名称（弹窗列表显示用；未登记的直接显示文件名）
SOURCE_NAMES = {
    "https://vps.example.com/ALLIP/all.txt":
        "【AF_ipscan源】",
    "https://www.cloudflare.com/ips-v4":
        "【官方】Cloudflare 官方IPv4网段（约5956条真实CF节点，扫描时实时识别机房地区）",
    "https://raw.githubusercontent.com/HandsomeMJZ/cfip/refs/heads/main/best_ips.txt":
        "【高速优选】HandsomeMJZ 高速IP（18条）",
    "https://raw.githubusercontent.com/svip-s/cloudflare_ip/refs/heads/main/best_ips.txt":
        "【带速度】svip-s 陕西移动优选（62条，含速度标注）",
    "https://cf.junzhen.qzz.io/best_ips_bj.txt":
        "【高速优选】junzhen 北京电信高速IP（29条）",
    "https://cf.junzhen.qzz.io/best_ips.txt":
        "junzhen 四川联通优选IP（18条）",
    "https://cf.junzhen.qzz.io/full_ips.txt":
        "junzhen 全量IP-四川联通（489条）",
    "https://cf.junzhen.qzz.io/full_ips_bj.txt":
        "junzhen 全量IP-北京电信（517条）",
    "https://raw.githubusercontent.com/HandsomeMJZ/cfip/refs/heads/main/full_ips.txt":
        "HandsomeMJZ 全量IP-GitHub镜像（489条）",
    "https://raw.githubusercontent.com/yuanxiawan/cfipv4db/refs/heads/main/high_score_ips.txt":
        "yuanxiawan 韩国高分IP（15条）",
    "https://raw.githubusercontent.com/ZZY202203/Worker-Vless-3-USB/main/addressesapi.txt":
        "ZZY202203 多端口节点（30条）",
    "https://raw.githubusercontent.com/cmliu/WorkerVless2sub/main/addressesapi.txt":
        "cmliu 备用节点（4条）",
}


def get_base_dir():
    """返回程序所在目录：打包后=exe目录；源码运行=入口脚本目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    main_path = getattr(__main__, "__file__", None)
    if main_path:
        return os.path.dirname(os.path.abspath(main_path))
    return os.getcwd()


def get_config_dir():
    """返回可写配置目录：%APPDATA%/AFipScan（打包后不污染程序目录，也不在程序目录单独显示）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "AFipScan")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def bundled_path(name):
    """打包后返回 _MEIPASS 内嵌资源路径；不存在返回 None（源码运行无内嵌）。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            pp = os.path.join(base, name)
            if os.path.exists(pp):
                return pp
    return None


def debug_log(msg):
    """写调试日志到系统临时目录 scan_debug.log（排查问题用）。"""
    try:
        p = os.path.join(tempfile.gettempdir(), "scan_debug.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write("[" + time.strftime("%H:%M:%S") + "] " + msg + "\n")
    except Exception:
        pass


def load_config():
    """读取可写目录 config.json；没有则用 exe 内置/默认配置生成（程序目录不再单独放 config）。"""
    path = os.path.join(get_config_dir(), "config.json")
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                user = json.load(f)
            for k in cfg:
                if k in user:
                    cfg[k] = user[k]
        except Exception:
            pass
    else:
        # 首次运行：优先用 exe 内置 config.json 作种子（config.py 默认值兜底）
        seed = bundled_path("config.json")
        if seed:
            try:
                with open(seed, encoding="utf-8") as f:
                    embedded = json.load(f)
                for k in cfg:
                    if k in embedded:
                        cfg[k] = embedded[k]
            except Exception:
                pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    # 迁移：默认候选源改为 VPS 地区分类总源(强制第一)，移除旧的官方默认源
    urls = [u for u in cfg.get("candidate_urls", []) if u and u != "https://www.cloudflare.com/ips-v4"]
    if VPS_ALL_URL not in urls:
        urls = [VPS_ALL_URL] + urls
    if urls != cfg.get("candidate_urls"):
        cfg["candidate_urls"] = urls
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return cfg, path


# 加载配置并导出全局常量（供其他模块使用）
CFG, CONFIG_PATH = load_config()
SNI = CFG["sni"]
PANEL = CFG["panel"]
ADMIN_PASSWORD = CFG["admin_password"]
PORT_DEFAULT = str(CFG.get("port_default", "")).strip() or ALL_OPEN
TOP_DEFAULT = int(CFG.get("top_default", 12))
_wd = CFG.get("workers_default", "12/3")
if isinstance(_wd, int) or (isinstance(_wd, str) and _wd.strip().isdigit()):
    WORKERS_DEFAULT = "%s/%s" % (_wd, _wd)
else:
    WORKERS_DEFAULT = str(_wd)
LIMIT_DEFAULT = int(CFG.get("limit_default", 300))
PROXY_URL = CFG.get("proxy_url", "http://127.0.0.1:20808")
CANDIDATE_URLS = CFG["candidate_urls"]
BUILTIN = CFG["builtin_ips"]
SUB_URL = CFG.get("subscription_url", "")
JOEY_PANEL = CFG.get("joey_panel", "")
JOEY_PASSWORD = CFG.get("joey_password", "")
JOEY_SUB_URL = CFG.get("joey_subscription_url", "")
REGION_FILTER_ENABLED = bool(CFG.get("region_filter_enabled", False))
REGION_FILTER = list(CFG.get("region_filter", []) or [])
SOURCE_NAMES = dict(SOURCE_NAMES)


def update_config(patch):
    """把窗口里填写的配置合并写回 config.json，并同步内存全局。"""
    global CFG
    path = os.path.join(get_config_dir(), "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = dict(DEFAULT_CONFIG)
    cfg.update(patch)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    CFG.update(patch)



def save_region_filter(enabled, regions):
    """保存区域筛选状态到 config.json，并同步内存全局。"""
    global REGION_FILTER_ENABLED, REGION_FILTER
    update_config({"region_filter_enabled": bool(enabled), "region_filter": list(regions)})
    REGION_FILTER_ENABLED = bool(enabled)
    REGION_FILTER = list(regions)


def save_candidate_urls(urls):
    """保存候选IP地址源列表到 config.json，并同步更新内存中的全局常量。"""
    global CANDIDATE_URLS
    update_config({"candidate_urls": list(urls)})
    CANDIDATE_URLS = list(urls)


# 候选IP内容缓存：成功拉取一次后本地保存，之后扫描时断网/关代理也能直接用缓存
CACHE_FILE = os.path.join(get_config_dir(), "candidate_cache.json")


def load_candidate_cache():
    """读取本地候选IP缓存，返回 {源URL: 原始文本}；无缓存/损坏返回空 dict。"""
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("sources"), dict):
            return data["sources"]
    except Exception:
        pass
    return {}


def save_candidate_cache(cache):
    """把候选IP缓存写盘：按源URL保存原始文本，供扫描时拉取失败兜底使用。"""
    try:
        payload = {"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "sources": cache}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    except Exception:
        pass



