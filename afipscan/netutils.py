# -*- coding: utf-8 -*-
"""网络工具：候选列表拉取/解析、TCP+TLS 测速、本地/出口 IP 获取。"""

import socket
import ssl
import threading
import time
import urllib.request
import ipaddress
import random
import re

from .config import PROXY_URL, SNI


def _fetch_via(url, timeout, proxy=None):
    """用指定网络路径下载文本：proxy=None 走直连，否则走该代理。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    if proxy:
        ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    else:
        # 直连：显式忽略系统代理，避免"系统代理开着但 v2rayN 没启动"时的 10061 报错
        ph = urllib.request.ProxyHandler({})
    op = urllib.request.build_opener(ph)
    with op.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def sys_proxy_url():
    """读取 Windows 系统代理地址；未开启时返回空字符串。"""
    try:
        import winreg as _wr
        _k = _wr.OpenKey(_wr.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        if not _wr.QueryValueEx(_k, "ProxyEnable")[0]:
            return ""
        return str(_wr.QueryValueEx(_k, "ProxyServer")[0] or "")
    except Exception:
        return ""


def fetch(url, timeout=20):
    """下载远程文本（候选 IP 列表）。

    先直连；直连失败自动改走本地代理（config 里的 v2rayN 地址，再退到
    Windows 系统代理），兼顾"没开代理直连超时"与"开了代理但代理没启动"
    两种情况。测速本身仍走直连，不受影响。
    """
    errs = []
    try:
        return _fetch_via(url, timeout)
    except Exception as e:
        errs.append(e)
    for proxy in (PROXY_URL, sys_proxy_url()):
        if not proxy:
            continue
        try:
            return _fetch_via(url, timeout, proxy)
        except Exception as e:
            errs.append(e)
    raise OSError("直连与本地代理均拉取失败") from errs[0]


# Cloudflare 机房三字码 -> 中文名（用于把 /cdn-cgi/trace 查到的真实机房翻译成地区名）
AIRPORT_CODES = {
    "HKG": "香港", "TPE": "台北", "KHH": "高雄", "MFM": "澳门",
    "NRT": "东京", "HND": "东京", "KIX": "大阪", "NGO": "名古屋",
    "FUK": "福冈", "CTS": "札幌", "OKA": "冲绳",
    "ICN": "首尔", "GMP": "首尔", "PUS": "釜山",
    "SIN": "新加坡", "BKK": "曼谷", "DMK": "曼谷",
    "KUL": "吉隆坡", "HKT": "普吉岛",
    "MNL": "马尼拉", "CEB": "宿务",
    "HAN": "河内", "SGN": "胡志明市",
    "JKT": "雅加达", "DPS": "巴厘岛",
    "DEL": "德里", "BOM": "孟买", "MAA": "金奈",
    "DXB": "迪拜", "AUH": "阿布扎比",
    "SJC": "圣何塞", "LAX": "洛杉矶", "SFO": "旧金山",
    "SEA": "西雅图", "PDX": "波特兰",
    "LAS": "拉斯维加斯", "PHX": "菲尼克斯",
    "DEN": "丹佛", "DFW": "达拉斯", "IAH": "休斯顿",
    "ORD": "芝加哥", "MSP": "明尼阿波利斯",
    "ATL": "亚特兰大", "MIA": "迈阿密", "MCO": "奥兰多",
    "JFK": "纽约", "EWR": "纽约", "LGA": "纽约",
    "BOS": "波士顿", "PHL": "费城", "IAD": "华盛顿",
    "YYZ": "多伦多", "YVR": "温哥华", "YUL": "蒙特利尔",
    "LHR": "伦敦", "LGW": "伦敦", "STN": "伦敦",
    "CDG": "巴黎", "ORY": "巴黎",
    "FRA": "法兰克福", "MUC": "慕尼黑", "TXL": "柏林",
    "AMS": "阿姆斯特丹", "EIN": "埃因霍温",
    "MAD": "马德里", "BCN": "巴塞罗那",
    "FCO": "罗马", "MXP": "米兰", "LIN": "米兰",
    "ZRH": "苏黎世", "GVA": "日内瓦",
    "VIE": "维也纳", "PRG": "布拉格",
    "WAW": "华沙", "KRK": "克拉科夫",
    "HEL": "赫尔辛基", "OSL": "奥斯陆", "ARN": "斯德哥尔摩",
    "CPH": "哥本哈根",
    "SYD": "悉尼", "MEL": "墨尔本", "BNE": "布里斯班",
    "PER": "珀斯", "ADL": "阿德莱德",
    "AKL": "奥克兰", "WLG": "惠灵顿",
    "GRU": "圣保罗", "GIG": "里约热内卢", "EZE": "布宜诺斯艾利斯",
    "SCL": "圣地亚哥", "LIM": "利马", "BOG": "波哥大",
    "JNB": "约翰内斯堡", "CPT": "开普敦", "CAI": "开罗",
}

# CIDR 网段展开时每个 /24 子网最多采样的 IP 数量（官方 ips-v4 全量拆 /24 约 6k 个）
MAX_CIDR_SAMPLE = 6000


# 常见用户输入(国家/地区码、中文名) -> 对应的 Cloudflare 机房三字码集合
REGION_ALIASES = {
    "HK": {"HKG"}, "HONGKONG": {"HKG"}, "香港": {"HKG"},
    "TW": {"TPE", "KHH"}, "TAIWAN": {"TPE", "KHH"}, "台湾": {"TPE", "KHH"},
    "MO": {"MFM"}, "澳门": {"MFM"},
    "JP": {"NRT", "HND", "KIX", "NGO", "FUK", "CTS", "OKA"}, "JAPAN": {"NRT", "HND", "KIX"},
    "日本": {"NRT", "HND", "KIX", "NGO", "FUK", "CTS", "OKA"},
    "东京": {"NRT", "HND"}, "大阪": {"KIX"}, "名古屋": {"NGO"},
    "KR": {"ICN", "GMP", "PUS"}, "韩国": {"ICN", "GMP", "PUS"}, "首尔": {"ICN", "GMP"},
    "SG": {"SIN"}, "SINGAPORE": {"SIN"}, "新加坡": {"SIN"},
    "TH": {"BKK", "DMK"}, "泰国": {"BKK", "DMK"}, "曼谷": {"BKK"},
    "MY": {"KUL"}, "马来西亚": {"KUL"}, "吉隆坡": {"KUL"},
    "VN": {"HAN", "SGN"}, "越南": {"HAN", "SGN"},
    "PH": {"MNL", "CEB"}, "菲律宾": {"MNL", "CEB"},
    "ID": {"JKT", "DPS"}, "印尼": {"JKT", "DPS"}, "印度尼西亚": {"JKT", "DPS"},
    "IN": {"DEL", "BOM", "MAA"}, "印度": {"DEL", "BOM", "MAA"},
    "AE": {"DXB", "AUH"}, "阿联酋": {"DXB", "AUH"}, "迪拜": {"DXB"},
    "US": {"SJC", "LAX", "SFO", "SEA", "PDX", "LAS", "PHX", "DEN", "DFW", "IAH",
           "ORD", "MSP", "ATL", "MIA", "MCO", "JFK", "EWR", "LGA", "BOS", "PHL", "IAD"},
    "USA": {"SJC", "LAX", "SFO", "SEA", "PDX", "LAS", "PHX", "DEN", "DFW", "IAH",
           "ORD", "MSP", "ATL", "MIA", "MCO", "JFK", "EWR", "LGA", "BOS", "PHL", "IAD"},
    "美国": {"SJC", "LAX", "SFO", "SEA", "PDX", "LAS", "PHX", "DEN", "DFW", "IAH",
           "ORD", "MSP", "ATL", "MIA", "MCO", "JFK", "EWR", "LGA", "BOS", "PHL", "IAD"},
    "UK": {"LHR", "LGW", "STN"}, "GB": {"LHR", "LGW", "STN"}, "英国": {"LHR", "LGW", "STN"},
    "DE": {"FRA", "MUC", "TXL"}, "德国": {"FRA", "MUC", "TXL"}, "法兰克福": {"FRA"},
    "FR": {"CDG", "ORY"}, "法国": {"CDG", "ORY"}, "巴黎": {"CDG"},
    "NL": {"AMS", "EIN"}, "荷兰": {"AMS", "EIN"},
    "ES": {"MAD", "BCN"}, "西班牙": {"MAD", "BCN"},
    "IT": {"FCO", "MXP", "LIN"}, "意大利": {"FCO", "MXP", "LIN"},
    "CH": {"ZRH", "GVA"}, "瑞士": {"ZRH", "GVA"},
    "AT": {"VIE"}, "奥地利": {"VIE"},
    "CZ": {"PRG"}, "捷克": {"PRG"},
    "PL": {"WAW", "KRK"}, "波兰": {"WAW", "KRK"},
    "SE": {"ARN"}, "瑞典": {"ARN"},
    "FI": {"HEL"}, "芬兰": {"HEL"},
    "NO": {"OSL"}, "挪威": {"OSL"},
    "DK": {"CPH"}, "丹麦": {"CPH"},
    "AU": {"SYD", "MEL", "BNE", "PER", "ADL"}, "澳大利亚": {"SYD", "MEL", "BNE", "PER", "ADL"},
    "NZ": {"AKL", "WLG"}, "新西兰": {"AKL", "WLG"},
    "CA": {"YYZ", "YVR", "YUL"}, "加拿大": {"YYZ", "YVR", "YUL"},
    "BR": {"GRU", "GIG"}, "巴西": {"GRU", "GIG"},
    "AR": {"EZE"}, "阿根廷": {"EZE"},
    "CL": {"SCL"}, "智利": {"SCL"},
    "PE": {"LIM"}, "秘鲁": {"LIM"},
    "CO": {"BOG"}, "哥伦比亚": {"BOG"},
    "ZA": {"JNB", "CPT"}, "南非": {"JNB", "CPT"},
    "EG": {"CAI"}, "埃及": {"CAI"},
}


# 三字码(机房) -> 国家/地区二字码：用于 VPS 按地区文件命名、填地区码时直接拉对应文件
COUNTRY_OF = {}
for _c2, _colos in REGION_ALIASES.items():
    if len(_c2) == 2 and _c2.isalpha():
        for _c in _colos:
            COUNTRY_OF.setdefault(_c, _c2)
# 英国规范为 GB（UK 也归到 GB）
if "GB" in REGION_ALIASES:
    for _c in REGION_ALIASES["GB"]:
        COUNTRY_OF[_c] = "GB"


# 二字码 -> 中文地区名（弹窗勾选列表显示用）
COUNTRY_NAMES = {
    "HK": "香港", "TW": "台湾", "MO": "澳门", "JP": "日本", "KR": "韩国",
    "SG": "新加坡", "TH": "泰国", "MY": "马来西亚", "VN": "越南", "PH": "菲律宾",
    "ID": "印尼", "IN": "印度", "AE": "阿联酋", "US": "美国", "GB": "英国",
    "DE": "德国", "FR": "法国", "NL": "荷兰", "ES": "西班牙", "IT": "意大利",
    "CH": "瑞士", "AT": "奥地利", "CZ": "捷克", "PL": "波兰", "SE": "瑞典",
    "FI": "芬兰", "NO": "挪威", "DK": "丹麦", "AU": "澳大利亚", "NZ": "新西兰",
    "CA": "加拿大", "BR": "巴西", "AR": "阿根廷", "CL": "智利", "PE": "秘鲁",
    "CO": "哥伦比亚", "ZA": "南非", "EG": "埃及",
}


def canonical_region(needle):
    """把一个地区输入(如 HK/HKG/香港/东京/JP)归一到唯一二字码；多解或无法判断返回 None。"""
    n = (needle or "").strip().upper()
    if not n:
        return None
    if len(n) == 3 and n in COUNTRY_OF:
        return COUNTRY_OF[n]
    alias = REGION_ALIASES.get(n)
    if alias:
        codes = {COUNTRY_OF.get(c) for c in alias}
        codes.discard(None)
        return codes.pop() if len(codes) == 1 else None
    if len(n) == 2 and n in COUNTRY_OF:
        return n
    return None


def region_file(needles):
    """若多个地区输入都归一到同一个二字码，返回该二字码；否则返回 None(需拉全量本地筛)。"""
    out = set()
    for nd in needles:
        c = canonical_region(nd)
        if not c:
            return None
        out.add(c)
    return out.pop() if len(out) == 1 else None


def region_matches(needle, iata, chinese):
    """判断一个IP是否匹配用户输入的地区筛选条件。

    空输入 = 不过滤；支持国家/地区码(HK/SG/JP)、三字码前缀(HK匹配HKG)、
    完整三字码、或中文名(香港/日本/东京)。
    """
    n = (needle or "").strip().upper()
    if not n:
        return True
    alias = REGION_ALIASES.get(n)
    iata_u = (iata or "").strip().upper()
    if alias:
        if iata_u and iata_u in alias:
            return True
    if iata_u and (iata_u == n or iata_u.startswith(n)):
        return True
    if chinese and n in (chinese or ""):
        return True
    return False


def region_name(code):
    """三字码 -> 中文地区名；查不到返回原码。"""
    return AIRPORT_CODES.get(code.upper(), code.upper() if code else "未知地区")


def _expand_cidr_line(line, port_default):
    """若整行是 IPv4 网段(如 173.245.48.0/20)，展开成 (ip, port, '') 列表：每个 /24 抽 1 个 IP。"""
    if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", line.strip()):
        return None
    try:
        net = ipaddress.ip_network(line.strip(), strict=False)
    except Exception:
        return None
    out = []
    if net.prefixlen >= 24:
        hosts = list(net.hosts())
        if hosts:
            out.append((str(random.choice(hosts)), port_default, ""))
        return out
    for sub in net.subnets(new_prefix=24):
        hosts = list(sub.hosts())
        if hosts:
            out.append((str(random.choice(hosts)), port_default, ""))
    return out


def get_iata(ip, port=443, timeout=3):
    """直连 https://{ip}/cdn-cgi/trace 查真实机房三字码(colo)。

    不走 DNS、不校验证书(和延迟测速一致的直连方式)。查不到返回 None。
    """
    test_host = "speed.cloudflare.com"
    s = None
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ctx.wrap_socket(s, server_hostname=test_host) as ss:
            req = ("GET /cdn-cgi/trace HTTP/1.1\r\n"
                   "Host: %s\r\n"
                   "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36\r\n"
                   "Connection: close\r\n\r\n" % test_host).encode()
            ss.sendall(req)
            data = b""
            deadline = time.time() + timeout
            while time.time() < deadline:
                buf = ss.recv(4096)
                if not buf:
                    break
                data += buf
                if b"colo=" in data:
                    break
                if len(data) > 65536:
                    break
        text = data.decode("utf-8", "ignore")
        for line in text.splitlines():
            if line.startswith("colo="):
                code = line.split("=", 1)[1].strip().upper()
                if code and code != "UNKNOWN":
                    return code
        if "CF-RAY" in text:
            cf_ray = text.split("CF-RAY:", 1)[1].split("\r\n", 1)[0].strip()
            if "-" in cf_ray:
                for part in cf_ray.split("-")[-2:]:
                    if len(part) == 3 and part.isalpha():
                        return part.upper()
    except Exception:
        return None
    finally:
        try:
            if s:
                s.close()
        except Exception:
            pass
    return None


def parse_lines(text, port_default):
    """解析候选文本为 [(ip, port, 备注)]。

    支持 ip:port#备注 / ip#备注 / ip，也支持 IPv4 网段(x.x.x.x/xx，自动展开，
    每个 /24 抽 1 个 IP，方便直接用 cloudflare.com/ips-v4 这类官方网段源)。
    """
    out = []
    sampled = 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        # 网段行：直接展开（没有端口/备注）
        expanded = _expand_cidr_line(ln, port_default)
        if expanded is not None:
            for ip, port, tag in expanded:
                if sampled >= MAX_CIDR_SAMPLE:
                    break
                out.append((ip, port, tag))
                sampled += 1
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


def probe(ip, port, timeout=5, rounds=1):
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
