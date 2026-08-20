# -*- coding: utf-8 -*-
"""网络工具：候选列表拉取/解析、TCP+TLS 测速、本地/出口 IP 获取。"""

import socket
import ssl
import threading
import time
import urllib.request

from .config import SNI


def fetch(url, timeout=20):
    """下载远程文本（候选 IP 列表）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def parse_lines(text, port_default):
    """解析候选文本为 [(ip, port, 备注)]，支持 ip:port#备注 / ip#备注 / ip。"""
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        tag = ""
        if "#" in ln:
            ln, tag = ln.split("#", 1)
        core = ln.strip().split("[")[0].strip()
        if ":" in core and core.count(":") == 1:
            ip, port = core.rsplit(":", 1)
            if not port.isdigit():
                continue
            port = int(port)
        else:
            ip, port = core, port_default
        if ":" in ip:  # 跳过 IPv6
            continue
        out.append((ip, port, tag.strip()))
    return out


def probe(ip, port, timeout=5, rounds=2):
    """测单个 IP 的 TCP+TLS 延迟（连目标域名握手），返回最快一次毫秒数。"""
    ts = []
    for _ in range(rounds):
        s = None
        try:
            t0 = time.time()
            s = socket.create_connection((ip, port), timeout=timeout)
            t1 = time.time()
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with ctx.wrap_socket(s, server_hostname=SNI) as ss:
                t2 = time.time()
            ts.append((t1 - t0) * 1000 + (t2 - t1) * 1000)
        except Exception:
            return None
        finally:
            try:
                if s:
                    s.close()
            except Exception:
                pass
    return min(ts) if ts else None


def get_lan_ip():
    """获取局域网 IP；失败返回 None。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def get_wan_ip(proxy=None, timeout=3):
    """并行请求多个公网 IP 服务，返回最快成功的一个；失败返回空字符串。"""
    urls = ("https://ifconfig.me/ip", "https://api.ipify.org", "https://ipinfo.io/ip")
    results = []
    lock = threading.Lock()
    done = threading.Event()

    def one(url):
        """单个 IP 服务请求：成功则记录并唤醒等待者。"""
        try:
            if proxy:
                ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                op = urllib.request.build_opener(ph)
            else:
                op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
            val = op.open(url, timeout=timeout).read().decode("utf-8", "ignore").strip()
            if val:
                with lock:
                    results.append(val)
                done.set()
        except Exception:
            pass

    ts = [threading.Thread(target=one, args=(u,), daemon=True) for u in urls]
    for t in ts:
        t.start()
    done.wait(timeout=timeout + 1)  # 等到第一个成功；全部失败则等约 timeout+1 秒
    return results[0] if results else ""


def check_sys_proxy():
    """读取 Windows 系统代理开关；返回 True/False。"""
    try:
        import winreg as _wr
        _k = _wr.OpenKey(_wr.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        return bool(_wr.QueryValueEx(_k, "ProxyEnable")[0])
    except Exception:
        return False
