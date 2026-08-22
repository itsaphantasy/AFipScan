# -*- coding: utf-8 -*-
"""面板写入模块：把优选结果写入 edgetunnel 面板并保存配置。"""

import http.cookiejar
import json
import urllib.request
import urllib.error

from .config import debug_log


def _resolve(base):
    """把用户填的面板地址拆成 (站点根路径, admin目录路径)。

    兼容两种填法：
      'https://cmliu.afcx.cc'         -> ('https://cmliu.afcx.cc', 'https://cmliu.afcx.cc/admin')
      'https://cmliu.afcx.cc/admin'   -> ('https://cmliu.afcx.cc', 'https://cmliu.afcx.cc/admin')
    登录接口在根路径 /login，配置接口在 /admin 下，两者不能混用。
    """
    base = (base or "").strip().rstrip("/")
    if base.endswith("/admin"):
        root = base[: -len("/admin")].rstrip("/")
    else:
        root = base
    return root, root + "/admin"


def write_panel(base, pwd, ip_list, first_port):
    """把优选 IP 列表写入面板，返回 (成功?, 提示文字)。"""
    try:
        root, admin = _resolve(base)
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
        op.open(root + "/login", data=b"password=" + pwd.encode(), timeout=30).read()
        debug_log("面板登录成功")

        # 写入优选 IP 列表
        req = urllib.request.Request(admin + "/ADD.txt",
                                     data="\n".join(ip_list).encode(), method="POST")
        r = op.open(req, timeout=30).read().decode("utf-8", "ignore")
        debug_log("ADD.txt 写入响应: " + r[:80])

        # 更新配置：本地 IP 库 + 指定端口
        cfg = json.loads(op.open(admin + "/config.json", timeout=30).read())
        cfg["优选订阅生成"]["local"] = True
        cfg["优选订阅生成"]["本地IP库"]["随机IP"] = False
        cfg["优选订阅生成"]["本地IP库"]["指定端口"] = first_port
        req = urllib.request.Request(admin + "/config.json",
                                     data=json.dumps(cfg, ensure_ascii=False).encode(),
                                     method="POST")
        req.add_header("Content-Type", "application/json")
        r = op.open(req, timeout=30).read().decode("utf-8", "ignore")
        debug_log("config 保存响应: " + r[:80])
        return True, "面板已更新！去 v2rayN 更新订阅即可"
    except Exception as e:
        debug_log("填面板失败: " + str(e)[:100])
        return False, str(e)[:100]


def check_panel(base, pwd):
    """检测面板是否在线、登录密码是否正确，返回 (成功?, 提示文字)。"""
    try:
        root, admin = _resolve(base)
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
        op.open(root + "/login", data=b"password=" + pwd.encode(), timeout=15).read()
        # 登录后能读到 config.json 说明密码正确、有权限
        json.loads(op.open(admin + "/config.json", timeout=15).read())
        return True, "面板在线，登录成功"
    except Exception as e:
        debug_log("面板检测失败: " + str(e)[:80])
        return False, str(e)[:80]


def _enable_cfnew_api(base, uuid):
    """开启 CFnew 面板「允许API管理」(ae=yes)，供 preferred-ips 接口使用。"""
    url = (base.rstrip("/") + "/" + uuid + "/api/config")
    req = urllib.request.Request(url, data=json.dumps({"ae": "yes"}).encode(),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    urllib.request.urlopen(req, timeout=20).read()


def write_cfnew(base, uuid, ip_list):
    """把优选 IP 列表写入 CFnew 面板（preferred-ips API），返回 (成功?, 提示)。

    CFnew = byJoey/cfnew（Cloudflare Worker + KV），写入无需登录：
      POST https://{base}/{uuid}/api/preferred-ips
      body: [{"ip":"1.2.3.4","port":443,"name":"节点1"}, ...]
    若返回 404，先自动开启面板「允许API管理」(ae=yes) 再重试一次。
    """
    try:
        base = (base or "").strip().rstrip("/")
        uuid = (uuid or "").strip().rstrip("/")

        nodes = []
        for line in ip_list:
            line = line.strip()
            if not line:
                continue
            hostport, _, name = line.partition("#")
            ip, _, port = hostport.partition(":")
            nodes.append({"ip": ip, "port": int(port or 443), "name": name or "优选"})

        url = base + "/" + uuid + "/api/preferred-ips"

        def _post():
            req = urllib.request.Request(url, data=json.dumps(nodes).encode(),
                                         method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            return urllib.request.urlopen(req, timeout=30).read()

        try:
            resp = _post()
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            debug_log("CFnew 返回404，尝试开启API管理后重试")
            _enable_cfnew_api(base, uuid)
            resp = _post()

        text = resp.decode("utf-8", "ignore")
        debug_log("CFnew preferred-ips 响应: " + text[:200])
        return True, "CFnew 面板已更新！去 v2rayN 更新订阅即可"
    except Exception as e:
        debug_log("CFnew 写入失败: " + str(e)[:120])
        return False, str(e)[:120]

