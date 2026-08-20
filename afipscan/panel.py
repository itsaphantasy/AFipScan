# -*- coding: utf-8 -*-
"""面板写入模块：把优选结果写入 edgetunnel 面板并保存配置。"""

import http.cookiejar
import json
import urllib.request

from .config import debug_log


def write_panel(base, pwd, ip_list, first_port):
    """把优选 IP 列表写入面板，返回 (成功?, 提示文字)。"""
    try:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
        op.open(base + "/login", data=b"password=" + pwd.encode(), timeout=30).read()
        debug_log("面板登录成功")

        # 写入优选 IP 列表
        req = urllib.request.Request(base + "/admin/ADD.txt",
                                     data="\n".join(ip_list).encode(), method="POST")
        r = op.open(req, timeout=30).read().decode("utf-8", "ignore")
        debug_log("ADD.txt 写入响应: " + r[:80])

        # 更新配置：本地 IP 库 + 指定端口
        cfg = json.loads(op.open(base + "/admin/config.json", timeout=30).read())
        cfg["优选订阅生成"]["local"] = True
        cfg["优选订阅生成"]["本地IP库"]["随机IP"] = False
        cfg["优选订阅生成"]["本地IP库"]["指定端口"] = first_port
        req = urllib.request.Request(base + "/admin/config.json",
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
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
        op.open(base + "/login", data=b"password=" + pwd.encode(), timeout=15).read()
        # 登录后能读到 config.json 说明密码正确、有权限
        json.loads(op.open(base + "/admin/config.json", timeout=15).read())
        return True, "面板在线，登录成功"
    except Exception as e:
        debug_log("面板检测失败: " + str(e)[:80])
        return False, str(e)[:80]
