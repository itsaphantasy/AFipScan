# -*- coding: utf-8 -*-
"""UI 模块：AFipScan 主窗口与全部交互逻辑（测速/写面板/复制/导出）。"""

import queue
import re
import threading
import time
import tkinter as tk
import webbrowser
import os
from tkinter import filedialog, messagebox, ttk

from . import config
from . import icons
from . import netutils
from .config import (ADMIN_PASSWORD, BUILTIN, CONFIG_PATH, LIMIT_DEFAULT,
                     PANEL, PORT_DEFAULT, PROXY_URL, SUB_URL,
                     TOP_DEFAULT, WORKERS_DEFAULT, debug_log, get_base_dir)
from .panel import check_panel, write_panel
from .theme import ACCENT, FONT, MUTED, apply_style
from .widgets import RoundedButton, RoundedEntry, Tooltip


class App:
    """AFipScan 主窗口。"""

    def __init__(self, root):
        self.root = root
        root.title("AFipScan — CF 优选 IP 工具")
        apply_style(root)
        try:
            icon_path = os.path.join(get_base_dir(), "app_icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass
        self.running = False
        self.msgq = queue.Queue()
        self.best = []
        # 按钮图标资源（保持引用，防止被 GC 回收）
        self.icons = {
            "start": icons.icon_photo("start"),
            "stop": icons.icon_photo("stop"),
            "export": icons.icon_photo("export"),
            "env": icons.icon_photo("env"),
            "import": icons.icon_photo("import"),
            "getip": icons.icon_photo("getip"),
            "write": icons.icon_photo("write"),
        }
        # 彩色按钮用白色图标（绿/红底上对比清晰，Tabler 22x22）
        self.icons_white = {
            "start": icons.icon_photo("start", color="white"),
            "stop": icons.icon_photo("stop", color="white"),
            "export": icons.icon_photo("export", color="white"),
            "env": icons.icon_photo("env", color="white"),
            "import": icons.icon_photo("import", color="white"),
            "getip": icons.icon_photo("getip", color="white"),
            "write": icons.icon_photo("write", color="white"),
        }
        # 白底彩色文字按钮用彩色图标（绿色=开始，红色=停止）
        self.icons_green = {
            "start": icons.icon_photo("start", color="green"),
            "stop": icons.icon_photo("stop", color="green"),
        }

        self._build_header(root)
        self._build_params(root)
        self._build_edgetunnel(root)
        self._build_buttons(root)
        self._build_results(root)
        self._build_log(root)

        self.log("就绪！配置来自: " + CONFIG_PATH)
        self.log("点【开始测速】→ 出结果后点【一键写入】→ v2rayN 更新订阅。")
        debug_log("App 初始化完成, 窗口已创建")
        root.update_idletasks()
        # 窗口一次性按内容尺寸打开（可拉大，最小=内容完整显示，避免先大后小跳变）
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        root.minsize(w, h)
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.deiconify()  # 尺寸已定，一次显示为正常窗口（无小窗闪跳）
        root.protocol("WM_DELETE_WINDOW", self.on_close)  # 关闭前保存窗口内容到 config.json
        self.poll_queue()

    # ==================== 界面构建 ====================

    def _build_header(self, root):
        """顶部标题栏：AFipScan 大标题 + 副标题 + GitHub 开源仓库链接。"""
        head = tk.Frame(root, bg="#ffffff")
        head.pack(fill="x")
        # 标题：矢量闪电图标(绿) + AFipScan，替代 emoji 保证像素清晰
        self.bolt_icon = icons.bolt_photo()
        tk.Label(head, image=self.bolt_icon, bg="#ffffff").pack(side="left", padx=(12, 5), pady=6)
        tk.Label(head, text="AFipScan", bg="#ffffff", fg=ACCENT,
                 font=(FONT, 16, "bold")).pack(side="left", pady=6)
        tk.Label(head, text="CF 优选 IP 测速 → 一键写入 → v2rayN 更新订阅  |  配置在 config.json",
                 bg="#ffffff", fg=MUTED, font=(FONT, 9)).pack(side="left", padx=6, pady=6)
        # 分隔线 + GitHub 图标（跟在副标题后面，点击打开仓库）
        tk.Label(head, text="|", bg="#ffffff", fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=(0, 4), pady=6)
        self.gh_icon = icons.github_photo()
        gh_icon = tk.Label(head, image=self.gh_icon, bg="#ffffff", cursor="hand2")
        gh_icon.pack(side="left", padx=(0, 8), pady=6)
        gh_icon.bind("<Button-1>", lambda e: webbrowser.open(
            "https://github.com/itsaphantasy/AFipScan"))
        # 绿色细线分隔标题与内容
        tk.Frame(root, bg="#0e9f6e", height=2).pack(fill="x")

    def _build_params(self, root):
        """参数设置区：第一行四个参数 + 获取IP，第二行推荐端口提示。"""
        top = ttk.LabelFrame(root, text=" ① 参数设置(鼠标悬停看说明) ")
        top.pack(fill="x", padx=12, pady=6)
        ttk.Label(top, text="端口:").grid(row=0, column=0, padx=(12,2), pady=(8,2), sticky="e")
        self.port_var = tk.StringVar(value=str(PORT_DEFAULT))
        e = RoundedEntry(top, textvariable=self.port_var, width=8)
        e.grid(row=0, column=1, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "测速端口，支持多个用逗号分隔(如 443,8443,2053)\n每个端口都会测一遍对比\n= 面板'指定端口'的数值")
        ttk.Label(top, text="测速数量:").grid(row=0, column=2, padx=(12,2), pady=(8,2), sticky="e")
        self.top_var = tk.StringVar(value=str(TOP_DEFAULT))
        e = RoundedEntry(top, textvariable=self.top_var, width=6)
        e.grid(row=0, column=3, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "保留前 N 个最快 IP(默认12)")
        ttk.Label(top, text="并发线程:").grid(row=0, column=4, padx=(12,2), pady=(8,2), sticky="e")
        self.workers_var = tk.StringVar(value=str(WORKERS_DEFAULT))
        e = RoundedEntry(top, textvariable=self.workers_var, width=6)
        e.grid(row=0, column=5, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "同时测多少个 IP(默认24;网络卡调小到10)")
        ttk.Label(top, text="延迟上限(ms):").grid(row=0, column=6, padx=(12,2), pady=(8,2), sticky="e")
        self.limit_var = tk.StringVar(value=str(LIMIT_DEFAULT))
        e = RoundedEntry(top, textvariable=self.limit_var, width=8)
        e.grid(row=0, column=7, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "只保留低于该延迟的结果(默认300;扫不到调600)")
        # 获取本地IP按钮：默认白，检测后本地=绿 / 代理=红（字体统一 11 号）
        self.ip_btn = RoundedButton(top, text="获取本地IP", command=self.get_ip,
                                    style="default", width=260, height=38,
                                    canvas_bg="#ffffff",
                                    image=self.icons["getip"],
                                    tooltip="点击获取当前出口IP\n绿色=本地直连\n红色=已开代理，为了准确获取优选IP，建议关闭代理")
        self.ip_btn.grid(row=0, column=8, padx=(12,12), pady=(8,2), sticky="e")
        # 推荐端口提示(占满整行)
        ttk.Label(top,
                  text="推荐端口: 443/8443/2053/2083/2087/2096（多个用逗号分隔,如443,8443）",
                  foreground="#6b7280", font=(FONT, 11)).grid(row=1, column=0, columnspan=9,
                                                              padx=(12,4), pady=(2,10), sticky="w")

    def _build_edgetunnel(self, root):
        """edgetunnel 设置区：第一行接口/密码/订阅地址 + 一键写入，第二行操作说明。"""
        ed = ttk.LabelFrame(root, text=" ② edgetunnel 设置(接口/密码/订阅) ")
        ed.pack(fill="x", padx=12, pady=6)
        ttk.Label(ed, text="接口:").grid(row=0, column=0, padx=(12,2), pady=(8,2), sticky="e")
        self.panel_var = tk.StringVar(value=str(PANEL or ""))
        e = RoundedEntry(ed, textvariable=self.panel_var, width=22)
        e.grid(row=0, column=1, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "edgetunnel 面板地址(登录后台用)")
        ttk.Label(ed, text="密码:").grid(row=0, column=2, padx=(12,2), pady=(8,2), sticky="e")
        self.pwd_var = tk.StringVar(value=str(ADMIN_PASSWORD or ""))
        e = RoundedEntry(ed, textvariable=self.pwd_var, width=12, show="*")
        e.grid(row=0, column=3, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "edgetunnel 面板登录密码")
        ttk.Label(ed, text="订阅地址:").grid(row=0, column=4, padx=(12,2), pady=(8,2), sticky="e")
        self.sub_var = tk.StringVar(value=str(SUB_URL or ""))
        e = RoundedEntry(ed, textvariable=self.sub_var, width=24)
        e.grid(row=0, column=5, padx=4, pady=(8,2), sticky="w")
        e.entry.bind("<Double-Button-1>", self.sub_dbl_click)
        Tooltip(e.entry, "edgetunnel 订阅链接(双击框内自动复制, 去 v2rayN 添加订阅)")
        # 一键写入按钮：默认白，写入成功变绿
        self.write_btn = RoundedButton(ed, text="一键写入", command=self.apply_panel,
                                       style="default", width=150, height=38,
                                       canvas_bg="#ffffff",
                                       image=self.icons["write"],
                                       tooltip="把测速结果自动写入 edgetunnel 面板(用上面填的接口和密码)\n写入成功按钮变绿色\n然后去 v2rayN 更新订阅")
        self.write_btn.grid(row=0, column=6, padx=(12,12), pady=(8,2), sticky="e")
        # 操作说明
        ttk.Label(ed, text="先测速，填入edgetunnel项目地址密码和订阅地址，可以一键写入到项目后台。",
                  foreground="#6b7280", font=(FONT, 11)).grid(row=1, column=0, columnspan=7,
                                                              padx=(12,4), pady=(2,10), sticky="w")

    def _build_buttons(self, root):
        """按钮区：开始测速/停止/导出结果/一键复制/清空日志。"""
        btns = tk.Frame(root, bg="#ffffff")
        btns.pack(fill="x", padx=12, pady=4)
        # 开始/停止 切换按钮：白底统一，未运行=绿字"开始测速"，运行中=红字"停止"
        self.start_btn = RoundedButton(btns, text="开始测速", command=self.toggle_scan,
                                       style="accent_light", width=132, height=40,
                                       canvas_bg="#ffffff",
                                       image=self.icons["start"],
                                       image_on_color=self.icons_white["start"],
                                       image_light=self.icons_green["start"],
                                       tooltip="点击开始测速；运行中再点一次=停止")
        self.start_btn.pack(side="left", padx=4)
        b = RoundedButton(btns, text="导出结果", command=self.export,
                          style="default", width=112, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["export"],
                          autofit=True,
                          tooltip="把结果保存成 txt(可手动粘贴到面板)")
        b.pack(side="left", padx=4)
        b = RoundedButton(btns, text="更多优选IP源", command=self.import_ips,
                          style="default", width=140, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["import"],
                          autofit=True,
                          tooltip="自定义测速用的候选IP地址源(每行一个网址)\n默认有2个，可增删改")
        b.pack(side="left", padx=4)
        b = RoundedButton(btns, text="环境检测", command=self.env_check,
                          style="default", width=132, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["env"],
                          autofit=True,
                          tooltip="一键检测本机网络/系统代理/v2rayN代理/面板/候选IP源是否正常")
        b.pack(side="left", padx=4)

    def _build_results(self, root):
        """测速结果表格：速度从高到低。"""
        res = ttk.LabelFrame(root, text=" ③ 测速结果(速度从高到低) ")
        res.pack(fill="both", expand=True, padx=12, pady=6)
        cols = ("ip", "ms", "speed", "region")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=5)
        self.tree.heading("ip", text="IP:端口")
        self.tree.heading("ms", text="延迟(ms)")
        self.tree.heading("speed", text="速度(Mbps)")
        self.tree.heading("region", text="备注")
        self.tree.column("ip", width=230)
        self.tree.column("ms", width=90, anchor="center")
        self.tree.column("speed", width=100, anchor="center")
        self.tree.column("region", width=280)
        self.tree.tag_configure("odd", background="#f8faf8")
        self.tree.tag_configure("even", background="#ffffff")
        vsb = ttk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)
        # 右键菜单：复制优选IP（替代原一键复制按钮）
        self.tree_menu = tk.Menu(root, tearoff=0)
        self.tree_menu.add_command(label="📋 复制优选IP", command=self.copy_all)
        self.tree.bind("<Button-3>", self._tree_menu_popup)

    def _build_log(self, root):
        """日志区：默认高度较大，便于查看扫描进度。"""
        logf = ttk.LabelFrame(root, text=" ④ 日志(扫描进度/结果) ")
        logf.pack(fill="both", expand=True, padx=12, pady=6)
        self.log_text = tk.Text(logf, height=7, bg="#0b1e33", fg="#e8f1ff",
                                font=("Consolas", 11), relief="flat",
                                insertbackground="#e8f1ff")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=3)
        # 右键菜单：清空日志（替代原清空日志按钮）
        self.log_menu = tk.Menu(root, tearoff=0)
        self.log_menu.add_command(label="🧹 清空日志",
                                  command=lambda: self.log_text.delete("1.0", "end"))
        self.log_text.bind("<Button-3>", self._log_menu_popup)

    # ==================== 界面反馈 ====================

    def log(self, msg):
        """往日志区追加一行并自动滚到底部。"""
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def poll_queue(self):
        """主线程轮询子线程消息，刷新界面。"""
        try:
            while True:
                msg = self.msgq.get_nowait()
                if msg[0] == "log":
                    self.log(msg[1])
                elif msg[0] == "done":
                    self.scan_done(msg[1])
                elif msg[0] == "ipresult":
                    is_proxy, ip = msg[1], msg[2]
                    try:
                        # 结果状态只留文字（绿=本地IP / 红=代理IP），去掉前缀图标
                        self.ip_btn.set_content(
                            text=(f"代理IP {ip}" if is_proxy else f"本地IP {ip}"),
                            style=("danger" if is_proxy else "success"))
                    except Exception:
                        pass
                elif msg[0] == "writeok":
                    try:
                        self.write_btn.config(text="✓ 写入成功", style="Success.TButton")
                    except Exception:
                        pass
                elif msg[0] == "msgbox":
                    # 弹窗必须在主线程调用；子线程只投递消息，避免 tkinter 线程安全问题
                    try:
                        messagebox.showinfo(msg[1], msg[2])
                    except Exception:
                        pass
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    # ==================== 配置持久化 ====================

    def save_ui_state(self):
        """把窗口里填的接口/密码/订阅/测速参数写回 config.json，下次打开自动恢复。"""
        try:
            def _int(v, d):
                """数字框容错：空或非数字时回退默认值，不让单个坏值连累整个保存。"""
                try:
                    return int(str(v).strip()) or d
                except Exception:
                    return d
            config.update_config({
                "panel": self.panel_var.get().strip(),
                "admin_password": self.pwd_var.get().strip(),
                "subscription_url": self.sub_var.get().strip(),
                "port_default": _int(self.port_var.get(), config.PORT_DEFAULT),
                "top_default": _int(self.top_var.get(), 12),
                "workers_default": _int(self.workers_var.get(), 24),
                "limit_default": _int(self.limit_var.get(), 300),
            })
            debug_log("UI 状态已写入 config.json")
        except Exception as e:
            debug_log("保存 UI 状态失败: " + str(e)[:80])

    def on_close(self):
        """关闭窗口：先保存当前填写的内容，再退出。"""
        self.save_ui_state()
        self.root.destroy()

    # ==================== 测速 ====================

    def toggle_scan(self):
        """开始/停止切换：未运行=开始测速，运行中=停止。"""
        if self.running:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        """开始测速：切换按钮变为"停止"(红)、恢复写入按钮为白、清空表格。"""
        debug_log("start_scan 被调用")
        if self.running:
            return
        self.running = True
        self.save_ui_state()  # 记录当前测速参数到 config.json
        self.start_btn.set_content("停止", style="danger_light",
                                   image=None, image_on_color=None,
                                   image_light=None)
        self.write_btn.config(text="一键写入", style="default")
        self.tree.delete(*self.tree.get_children())
        threading.Thread(target=self.scan_worker, daemon=True).start()

    def stop_scan(self):
        """请求停止：按钮立即恢复为"开始测速"，当前批次结束后停下。"""
        debug_log("stop_scan 被调用")
        self.running = False
        self.start_btn.set_content("开始测速", style="accent_light",
                                   image=self.icons["start"],
                                   image_on_color=self.icons_white["start"],
                                   image_light=self.icons_green["start"])
        self.msgq.put(("log", "[*] 已请求停止(等当前批次结束)"))

    def scan_worker(self):
        """测速线程：拉候选 → 并发测速 → 排序 → 回传结果。"""
        try:
            top = int(self.top_var.get())
            workers = int(self.workers_var.get())
            limit = int(self.limit_var.get())
        except ValueError:
            self.msgq.put(("log", "[!] 参数必须是数字"))
            self.running = False
            self.msgq.put(("done", []))
            return
        ports = []
        for part in re.split(r"[,，\s]+", self.port_var.get().strip()):
            if part.isdigit() and 1 <= int(part) <= 65535:
                ports.append(int(part))
        if not ports:
            self.msgq.put(("log", "[!] 端口必须是数字(可逗号分隔多个, 如 443,8443)"))
            self.running = False
            self.msgq.put(("done", []))
            return
        self.current_ports = ports
        self.msgq.put(("log", "[*] 正在拉取候选 IP 列表 ..."))
        debug_log("scan_worker 启动, ports=%s top=%s workers=%s limit=%s" % (ports, top, workers, limit))
        # 并行拉取多个候选源，谁先到先用；拉取失败自动用上次成功的本地缓存兜底
        import concurrent.futures
        cands = []
        cache = config.load_candidate_cache()
        cache_dirty = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(config.CANDIDATE_URLS) or 1) as fex:
            futs = {fex.submit(netutils.fetch, url): url for url in config.CANDIDATE_URLS}
            for f in concurrent.futures.as_completed(futs):
                url = futs[f]
                name = url.split("/")[-1]
                try:
                    text = f.result()
                    cache[url] = text  # 成功拉取 -> 更新本地缓存，之后关代理也能扫
                    cache_dirty = True
                    got = netutils.parse_lines(text, ports[0])
                    debug_log("拉取成功 %s -> %d 条" % (name, len(got)))
                    cands += got
                    self.msgq.put(("log", f"[*] 拉取 {name} -> {len(got)} 条"))
                except Exception as e:
                    cached = cache.get(url, "")
                    if cached:
                        got = netutils.parse_lines(cached, ports[0])
                        cands += got
                        self.msgq.put(("log", f"[i] {name} 拉取失败({str(e)[:18]})，使用本地缓存 {len(got)} 条"))
                    else:
                        self.msgq.put(("log", f"[!] {name} 拉取失败：{str(e)[:40]}（无本地缓存，可开v2rayN拉一次后关掉）"))
        if cache_dirty:
            config.save_candidate_cache(cache)
        cands += netutils.parse_lines("\n".join(BUILTIN), ports[0])
        seen, uniq = set(), []
        for c in cands:
            key = (c[0], c[1])  # IP+端口 去重，避免全量源覆盖高速源的端口
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        cands = uniq
        # 多端口时每个 IP × 每个端口各测一遍
        if len(ports) > 1:
            cands = [(ip, p, tag) for ip, _p, tag in cands for p in ports]
            debug_log("候选总数 %d (IP %d × 端口 %s), 开始测速" % (len(cands), len(uniq), ports))
            self.msgq.put(("log", f"[*] 测速 {len(uniq)} 个IP × {len(ports)} 个端口 = {len(cands)} 组 ..."))
        else:
            debug_log("候选总数 %d, 开始测速" % len(cands))
            self.msgq.put(("log", f"[*] 开始测速，共 {len(cands)} 个候选 ..."))
        results = []
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        try:
            futs = {ex.submit(netutils.probe, c[0], c[1]): c for c in cands}
            done = 0
            for f in concurrent.futures.as_completed(futs):
                done += 1
                c = futs[f]
                ms = f.result()
                if ms is not None and ms <= limit:
                    results.append((ms, c[0], c[1], c[2]))
                if done % 10 == 0:
                    self.msgq.put(("log", f"    已测 {done}/{len(cands)} ..."))
                if not self.running:
                    break
        finally:
            # 停止时不等待在测任务，立即返回，UI 快速恢复
            ex.shutdown(wait=False, cancel_futures=True)
        # ---- 带宽测速：对延迟达标 IP 实测下载速度，按速度从高到低排序 ----
        if self.running and results:
            self.msgq.put(("log", f"[*] 延迟达标 {len(results)} 个，正在实测下载速度 ..."))
            speed_map = {}
            sex = concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, 8))
            try:
                sfuts = {sex.submit(netutils.speed_probe, ip, port): (ip, port)
                         for _ms, ip, port, _tag in results}
                sdone = 0
                for sf in concurrent.futures.as_completed(sfuts):
                    if not self.running:
                        break
                    sdone += 1
                    k = sfuts[sf]
                    try:
                        v = sf.result()
                        if v:
                            speed_map[k] = v
                    except Exception:
                        pass
                    if sdone % 10 == 0:
                        self.msgq.put(("log", f"    已测速度 {sdone}/{len(sfuts)} ..."))
            finally:
                sex.shutdown(wait=False, cancel_futures=True)
        final = []
        for ms, ip, port, tag in results:
            final.append((ms, ip, port, tag, speed_map.get((ip, port))))
        # 速度高在前；没测到速度的按延迟排在最前（也算有结果）
        final.sort(key=lambda r: (-(r[4] or 0), r[0]))
        debug_log("测速完成, 达标 %d 个, 测到速度 %d 个, 取前 %d"
                  % (len(results), len(speed_map), top))
        self.msgq.put(("done", final[:top]))

    def scan_done(self, best):
        """测速完成：恢复按钮、填充表格与日志。"""
        self.running = False
        self.start_btn.set_content("开始测速", style="accent_light",
                                   image=self.icons["start"],
                                   image_on_color=self.icons_white["start"],
                                   image_light=self.icons_green["start"])
        self.best = best
        if not best:
            self.log("[!] 没测到符合条件的结果，把【延迟上限】调高(如600)再试")
            return
        self.log("\n===== 最快结果(按速度) =====")
        for i, (ms, ip, port, tag, speed) in enumerate(best):
            region = tag if tag else "优选"
            tagname = "odd" if i % 2 else "even"
            sp = f"{speed:.0f}" if speed else "-"
            self.tree.insert("", "end",
                             values=(f"{ip}:{port}", f"{ms:.0f}", sp, region),
                             tags=(tagname,))
            self.log(f"  {ip}:{port}  {ms:.0f}ms  {sp}Mbps")
        self.log("[*] 测速完成！点【一键写入】写入配置，然后去 v2rayN 更新订阅")

    # ==================== 获取 IP ====================

    def get_ip(self):
        """点击获取IP：后台线程判断本地直连还是代理。"""
        self.log("[*] 正在获取本地 IP ...")
        threading.Thread(target=self.ip_worker, daemon=True).start()

    def import_ips(self):
        """打开弹窗：勾选要使用的优选IP源；点「获取更多源地址」可追加更多源。

        列表区做成固定高度 + 滚动条，源再多也不会把底部按钮挤出屏幕；
        按钮栏固定在窗口底部，始终可见。
        """
        win = tk.Toplevel(self.root)
        win.title("导入更多优选IP地址")
        win.configure(bg="#ffffff")
        win.resizable(False, False)
        tk.Label(win, text="勾选要使用的优选IP源（默认已选 3 个高速优选源）：",
                 bg="#ffffff", fg="#6b7280",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=14, pady=(14, 6))
        tk.Label(win, text="提示：成功拉取过的源会自动缓存到本地，之后关代理扫描也会自动用缓存，测速仍走真实直连。",
                 bg="#ffffff", fg="#0e9f6e",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=14, pady=(0, 4))

        # ---- 可滚动列表区：内容超出固定高度时用滚轮/滚动条查看 ----
        list_area = tk.Frame(win, bg="#ffffff")
        list_area.pack(fill="both", expand=True, padx=14)
        canvas = tk.Canvas(list_area, bg="#ffffff", highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(list_area, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg="#ffffff")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _on_wheel(e):
            """鼠标滚轮滚动源列表。"""
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 初始列表 = 已保存源 ∪ 默认 3 个高速源，全部勾选（不丢用户已有配置）
        saved = [u for u in config.CANDIDATE_URLS if u]
        defaults = [u for u in config.DEFAULT_CONFIG["candidate_urls"] if u not in saved]
        vars_ = {}

        def add_row(url, checked):
            """在弹窗列表里加一行：复选框 + 友好名称/完整地址。"""
            var = tk.BooleanVar(value=checked)
            vars_[url] = var
            row = tk.Frame(body, bg="#ffffff")
            row.pack(fill="x", pady=2)
            tk.Checkbutton(row, variable=var, bg="#ffffff",
                           activebackground="#ffffff", bd=0,
                           highlightthickness=0).pack(side="left", anchor="n")
            name = config.SOURCE_NAMES.get(url, url.split("/")[-1])
            tk.Label(row, text=f"{name}\n{url}", bg="#ffffff",
                     fg="#374151", font=("Microsoft YaHei UI", 9),
                     anchor="w", justify="left", wraplength=600).pack(
                side="left", fill="x", expand=True)

        for url in saved + defaults:
            add_row(url, True)

        bar = tk.Frame(win, bg="#ffffff")
        bar.pack(fill="x", padx=14, pady=(8, 14))

        def recenter():
            """列表高度封顶 + 窗口居中，保证按钮栏一定在屏幕内。"""
            win.update_idletasks()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            content_h = len(vars_) * 46 + 8     # 估算源列表总高
            max_canvas = max(180, int(sh * 0.7) - 170)
            canvas_h = min(content_h, max_canvas)
            canvas.configure(height=canvas_h)
            w = 720                             # 固定窗口宽
            h = min(canvas_h + 170, int(sh * 0.92))  # 显式计算总高，不依赖 reqheight
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            win.geometry(f"{w}x{h}+{x}+{y}")
            canvas.yview_moveto(0)

        def load_more():
            """点击「获取更多源地址」：追加更多源（默认不勾选），并禁用按钮。"""
            added = 0
            for url in config.MORE_URLS:
                if url not in vars_:
                    add_row(url, False)
                    added += 1
            if added:
                self.log(f"[*] 已追加 {added} 个更多源地址（未勾选，需要手动勾选）")
            more_btn.set_state("disabled")
            more_btn.set_text("已加载全部")
            recenter()

        def do_save():
            """保存：收集勾选的网址 → 写回配置并刷新内存。"""
            urls = [u for u, v in vars_.items() if v.get()]
            config.save_candidate_urls(urls)
            self.log(f"[OK] 已保存 {len(urls)} 个候选IP地址源")
            win.destroy()

        RoundedButton(bar, text="保存", command=do_save,
                      style="accent", width=96, height=38,
                      canvas_bg="#ffffff").pack(side="left", padx=(0, 8))
        RoundedButton(bar, text="取消", command=win.destroy,
                      style="default", width=88, height=38, outline=2,
                      canvas_bg="#ffffff").pack(side="left", padx=(0, 8))
        more_btn = RoundedButton(bar, text="获取更多源地址",
                                 command=load_more, style="accent_light",
                                 width=160, height=38, outline=2,
                                 canvas_bg="#ffffff")
        more_btn.pack(side="left")
        recenter()
        canvas.focus_set()

    def env_check(self):
        """一键环境检测：后台线程逐项检查并输出到日志。"""
        self.log("[*] 开始一键环境检测 ...")
        threading.Thread(target=self.env_check_worker, daemon=True).start()

    def env_check_worker(self):
        """逐项检测：配置文件/系统代理/局域网/公网/本地代理/面板/候选源。"""
        import os
        import socket as _socket
        import subprocess
        from .config import get_base_dir
        # 1. 配置文件
        p = os.path.join(get_base_dir(), "config.json")
        self.msgq.put(("log", f"[{'✓' if os.path.exists(p) else '!'}] 配置文件: {'存在 ' + p if os.path.exists(p) else '缺失(将自动生成)'}"))
        # 2. 系统代理
        sys_proxy = netutils.check_sys_proxy()
        self.msgq.put(("log", f"[{'!' if sys_proxy else '✓'}] 系统代理: {'已开启(建议优选前关闭)' if sys_proxy else '未开启(正常)'}"))
        # 3. 局域网 IP
        lan = netutils.get_lan_ip()
        self.msgq.put(("log", f"[{'✓' if lan else '!'}] 局域网 IP: {lan or '获取失败'}"))
        # 4. 公网直连（判断能否上外网）
        direct = netutils.get_wan_ip(None)
        self.msgq.put(("log", f"[{'✓' if direct else '!'}] 公网直连: {direct or '获取失败(可能断网/被墙)'}"))
        # 5. v2rayN 本地代理连通性
        proxy_ok = False
        try:
            host, port = PROXY_URL.split("://")[1].rsplit(":", 1)
            s = _socket.create_connection((host, int(port)), timeout=3)
            s.close()
            proxy_ok = True
        except Exception:
            pass
        self.msgq.put(("log", f"[{'✓' if proxy_ok else '!'}] v2rayN 本地代理({PROXY_URL}): {'可连接' if proxy_ok else '连不上(先启动v2rayN)'}"))
        # 6. 代理出口 IP
        if proxy_ok:
            p_ip = netutils.get_wan_ip(PROXY_URL)
            self.msgq.put(("log", f"[{'✓' if p_ip else '!'}] 代理出口 IP: {p_ip or '获取失败'}"))
        # 7. edgetunnel 面板
        base = self.panel_var.get().strip().rstrip("/")
        pwd = self.pwd_var.get().strip()
        ok, msg = check_panel(base, pwd)
        self.msgq.put(("log", f"[{'✓' if ok else '!'}] edgetunnel 面板: {msg}"))
        # 8. 候选 IP 源（拉取失败时提示是否有本地缓存可用）
        cache = config.load_candidate_cache()
        for url in config.CANDIDATE_URLS:
            try:
                got = netutils.parse_lines(netutils.fetch(url, timeout=10), 443)
                self.msgq.put(("log", f"[✓] 候选源 {url.split('/')[-1]}: 拉取 {len(got)} 条"))
            except Exception as e:
                cached = cache.get(url, "")
                tip = (f"，有本地缓存 {len(netutils.parse_lines(cached, 443))} 条(扫描自动用)"
                       if cached else "，无本地缓存")
                self.msgq.put(("log", f"[!] 候选源 {url.split('/')[-1]}: 拉取失败 {str(e)[:40]}{tip}"))
        # 9. Windows 防火墙状态（3 个配置文件）
        fw_ok = 0
        try:
            ps = "(Get-NetFirewallProfile | Where-Object Enabled).Count"
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="ignore", timeout=15,
                               creationflags=0x08000000)  # CREATE_NO_WINDOW 防止弹黑框
            fw_ok = int(r.stdout.strip() or 0)
        except Exception:
            pass
        fw_tip = "正常" if fw_ok == 3 else "有配置被关闭"
        self.msgq.put(("log", f"[{'✓' if fw_ok == 3 else '!'}] Windows 防火墙: {fw_ok}/3 个配置开启({fw_tip})"))
        # 10. 关键程序防火墙放行规则（v2rayN 内核 / AFipScan 自身）
        try:
            ps = ("Get-NetFirewallApplicationFilter -Program '*xray*','*sing-box*','*mihomo*',"
                  "'*AFipScan*' | Select-Object -ExpandProperty Program")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="ignore", timeout=20,
                               creationflags=0x08000000)
            progs = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            v2ray = [p for p in progs if any(k in p.lower() for k in ("xray", "sing-box", "mihomo"))]
            cf = [p for p in progs if "afipscan" in p.lower()]
            v_tip = f"已放行 {len(v2ray)} 个" if v2ray else "未找到(连不上时手动添加放行)"
            c_tip = "已放行" if cf else "未找到(通常不需要,出站默认放行)"
            self.msgq.put(("log", f"[{'✓' if v2ray else '!'}] v2rayN 内核防火墙规则: {v_tip}"))
            self.msgq.put(("log", f"[{'✓' if cf else '!'}] AFipScan 防火墙规则: {c_tip}"))
        except Exception as e:
            self.msgq.put(("log", f"[!] 防火墙规则检测失败: {str(e)[:50]}"))
        self.msgq.put(("log", "[OK] 环境检测完成"))

    def ip_worker(self):
        """获取局域网 IP + 判断当前出口是本地直连还是代理。"""
        lan = netutils.get_lan_ip() or "获取失败"
        # 直连与代理并行探测，节省一半时间
        direct_box, proxy_box = {}, {}
        t1 = threading.Thread(target=lambda: direct_box.update(v=netutils.get_wan_ip(None)), daemon=True)
        t2 = threading.Thread(target=lambda: proxy_box.update(v=netutils.get_wan_ip(PROXY_URL)), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        direct = direct_box.get("v", "")  # 本地直连出口 IP
        proxy_ip = proxy_box.get("v", "")  # 走本地代理(v2rayN)的出口 IP
        sys_proxy = netutils.check_sys_proxy()
        if not direct:
            direct = "获取失败"
        is_proxy = bool(sys_proxy) and bool(proxy_ip) and proxy_ip != direct
        debug_log("IP检测: 局域网=%s 直连=%s 代理=%s 系统代理=%s -> %s" %
                  (lan, direct, proxy_ip or "-", sys_proxy, "代理" if is_proxy else "本地"))
        self.msgq.put(("log", f"[OK] 局域网 IP: {lan}"))
        if is_proxy:
            self.msgq.put(("log", f"[!] 代理已开启：出口 IP {proxy_ip}（≠ 本地直连 {direct}）"))
            self.msgq.put(("ipresult", True, proxy_ip))
        else:
            tip = "（系统代理未开启）" if not sys_proxy else "（代理未生效或出口相同）"
            self.msgq.put(("log", f"[OK] 本地直连：出口 IP {direct} {tip}"))
            self.msgq.put(("ipresult", False, direct))

    def sub_dbl_click(self, e=None):
        """双击订阅地址框：复制订阅链接到剪贴板。"""
        url = self.sub_var.get().strip()
        if not url:
            self.log("[!] 订阅地址为空")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.log(f"[OK] 订阅地址已双击复制: {url}")

    # ==================== 写入面板 ====================

    def apply_panel(self):
        """一键写入：后台线程写入面板。"""
        if not self.best:
            messagebox.showinfo("提示", "请先测速")
            return
        self.log("[*] 正在写入面板 ...")
        threading.Thread(target=self.apply_worker, daemon=True).start()

    def apply_worker(self):
        """组装优选结果并调用面板写入模块，回传结果。"""
        # 写入前按 IP 查重（保留排在最前=速度最快的），避免面板出现重复节点
        dedup = {}
        for item in self.best:
            if item[1] not in dedup:
                dedup[item[1]] = item
        ip_list = [f"{ip}:{port}#{tag if tag else '优选'}"
                   for _ms, ip, port, tag, _speed in dedup.values()]
        first_port = getattr(self, "current_ports", [443])[0]
        base = self.panel_var.get().strip().rstrip("/")
        pwd = self.pwd_var.get().strip()
        ok, msg = write_panel(base, pwd, ip_list, first_port)
        if ok and len(ip_list) != len(self.best):
            self.log(f"[i] 已去重：{len(self.best)} -> {len(ip_list)} 个")
        self.msgq.put(("log", f"[*] 写入IP: {msg}" if not ok else "[OK] " + msg))
        if ok:
            self.save_ui_state()  # 写入成功，把接口/密码/订阅存进 config.json
            self.msgq.put(("writeok",))
            self.msgq.put(("msgbox", "完成", msg))
        else:
            self.msgq.put(("log", f"[!] 填面板失败: {msg}"))

    # ==================== 导出 / 复制 ====================

    def export(self):
        """导出结果到 txt 文件。"""
        if not self.best:
            messagebox.showinfo("提示", "请先测速")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile=f"优选结果_{time.strftime('%Y%m%d_%H%M')}.txt",
                                            filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"{ip}:{port}#{tag if tag else '优选'}"
                              for _ms, ip, port, tag, _speed in self.best))
        self.log(f"[*] 已导出: {path}")

    def copy_all(self):
        """复制所有结果的 IP:端口 到剪贴板（每行一个，不含延迟/备注）。"""
        if not self.best:
            messagebox.showinfo("提示", "请先测速")
            return
        lines = [f"{ip}:{port}" for _ms, ip, port, _tag, _speed in self.best]
        text = "\r\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"[OK] 已复制 {len(lines)} 个 IP:端口 到剪贴板(纯IP:端口)")

    def _tree_menu_popup(self, e):
        """结果表格右键菜单。"""
        try:
            self.tree_menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.tree_menu.grab_release()

    def _log_menu_popup(self, e):
        """日志窗口右键菜单。"""
        try:
            self.log_menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.log_menu.grab_release()
