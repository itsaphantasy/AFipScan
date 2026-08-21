# -*- coding: utf-8 -*-
"""配置模块：读取/生成 config.json，提供全局常量与调试日志。"""

import json
import os
import sys
import tempfile
import time
import __main__


# 默认配置：首次运行没有 config.json 时自动生成这份
DEFAULT_CONFIG = {
    "sni": "www.cloudflare.com",
    "panel": "",
    "admin_password": "",
    "port_default": 443,
    "top_default": 12,
    "workers_default": 24,
    "limit_default": 300,
    "proxy_url": "http://127.0.0.1:20808",
    "candidate_urls": [
        "https://raw.githubusercontent.com/HandsomeMJZ/cfip/refs/heads/main/best_ips.txt",
        "https://raw.githubusercontent.com/svip-s/cloudflare_ip/refs/heads/main/best_ips.txt",
        "https://cf.junzhen.qzz.io/best_ips_bj.txt",
    ],
    "subscription_url": "",
    "builtin_ips": [
        "91.110.174.202:8443#HK", "91.110.174.205:8443#HK", "91.110.174.210:8443#HK",
        "43.129.195.232:443#HK", "54.64.78.192:443#JP", "52.77.54.144:443#SG",
        "207.57.134.29:443#HK", "54.95.106.234:443#HK", "57.180.60.121:443#HK",
        "38.55.195.57:443#HK", "150.109.11.223:443#SG", "198.20.153.247:443#HK",
    ],
}


# 更多候选源池：弹窗点「获取更多源地址」后追加显示（默认不勾选）
DEFAULT_MORE_URLS = [
    "https://cf.junzhen.qzz.io/best_ips.txt",
    "https://cf.junzhen.qzz.io/full_ips.txt",
    "https://cf.junzhen.qzz.io/full_ips_bj.txt",
    "https://raw.githubusercontent.com/HandsomeMJZ/cfip/refs/heads/main/full_ips.txt",
    "https://raw.githubusercontent.com/yuanxiawan/cfipv4db/refs/heads/main/high_score_ips.txt",
    "https://raw.githubusercontent.com/ZZY202203/Worker-Vless-3-USB/main/addressesapi.txt",
    "https://raw.githubusercontent.com/cmliu/WorkerVless2sub/main/addressesapi.txt",
]


# 源友好名称（弹窗列表显示用；未登记的直接显示文件名）
SOURCE_NAMES = {
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


def debug_log(msg):
    """写调试日志到系统临时目录 scan_debug.log（排查问题用）。"""
    try:
        p = os.path.join(tempfile.gettempdir(), "scan_debug.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write("[" + time.strftime("%H:%M:%S") + "] " + msg + "\n")
    except Exception:
        pass


def load_config():
    """读取同目录 config.json；没有则自动创建默认配置。"""
    path = os.path.join(get_base_dir(), "config.json")
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
PORT_DEFAULT = int(CFG["port_default"])
TOP_DEFAULT = int(CFG.get("top_default", 12))
WORKERS_DEFAULT = int(CFG.get("workers_default", 24))
LIMIT_DEFAULT = int(CFG.get("limit_default", 300))
PROXY_URL = CFG.get("proxy_url", "http://127.0.0.1:20808")
CANDIDATE_URLS = CFG["candidate_urls"]
BUILTIN = CFG["builtin_ips"]
SUB_URL = CFG.get("subscription_url", "")
MORE_URLS = list(DEFAULT_MORE_URLS)
SOURCE_NAMES = dict(SOURCE_NAMES)

# Cloudflare 常用入站端口：443/8443 是 TLS 标准，2053/2083/2087/2096 是 HTTP/3 常用
RECOMMEND_PORTS = ["443", "8443", "2053", "2083", "2087", "2096"]


def update_config(patch):
    """把窗口里填写的配置合并写回 config.json，并同步内存全局。"""
    global CFG
    path = os.path.join(get_base_dir(), "config.json")
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


def save_candidate_urls(urls):
    """保存候选IP地址源列表到 config.json，并同步更新内存中的全局常量。"""
    global CANDIDATE_URLS
    path = os.path.join(get_base_dir(), "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = dict(DEFAULT_CONFIG)
    cfg["candidate_urls"] = list(urls)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    CFG["candidate_urls"] = list(urls)
    CANDIDATE_URLS = list(urls)


# 候选IP内容缓存：成功拉取一次后本地保存，之后扫描时断网/关代理也能直接用缓存
CACHE_FILE = os.path.join(get_base_dir(), "candidate_cache.json")


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
