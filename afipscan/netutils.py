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


def speed_probe(ip, port, timeout=8, max_sec=2.5, bytes_target=20 * 1024 * 1024):
    """测单个 IP 的下载速度(Mbps)：TLS 握手后拉取 Cloudflare 测速文件。

    返回 Mbps（浮点）或 None（连接失败/非 200/没测到数据）。
    只读 max_sec 秒就断开，避免浪费流量和时间。
    注意：speed.cloudflare.com 对 UA 有校验，必须带完整浏览器 UA + Sec-Fetch 头，
    否则返回 403。
    """
    s = None
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ctx.wrap_socket(s, server_hostname="speed.cloudflare.com") as ss:
            req = ("GET /__down?bytes=%d HTTP/1.1\r\n"
                   "Host: speed.cloudflare.com\r\n"
                   "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36\r\n"
                   "Accept: */*\r\n"
                   "Accept-Language: zh-CN,zh;q=0.9\r\n"
                   "Accept-Encoding: identity\r\n"
                   "Sec-Fetch-Dest: empty\r\n"
                   "Sec-Fetch-Mode: cors\r\n"
                   "Sec-Fetch-Site: same-origin\r\n"
                   "Connection: close\r\n\r\n" % bytes_target).encode()
            ss.sendall(req)
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = ss.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 65536:
                    break
            if b"\r\n\r\n" not in buf:
                return None
            status = buf.split(b"\r\n", 1)[0]
            if b"200" not in status:
                return None
            total = len(buf.split(b"\r\n\r\n", 1)[1])
            t1 = time.time()
            while time.time() - t1 < max_sec:
                chunk = ss.recv(65536)
                if not chunk:
                    break
                total += len(chunk)
            dt = time.time() - t1
            if dt <= 0:
                return None
            mbps = total * 8 / dt / 1e6
            return mbps if mbps > 0 else None
    except Exception:
        return None
    finally:
        try:
            if s:
                s.close()
        except Exception:
            pass


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
