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
from .config import (ADMIN_PASSWORD, BUILTIN, JOEY_PANEL,
                     JOEY_PASSWORD, JOEY_SUB_URL, LIMIT_DEFAULT,
                     PANEL, PORT_DEFAULT, PROXY_URL,
                     SUB_URL,
                     TOP_DEFAULT, WORKERS_DEFAULT, debug_log, get_base_dir)
from .panel import check_panel, write_panel, write_cfnew
from .theme import ACCENT, FONT, MUTED, apply_style
from .widgets import RoundedButton, RoundedEntry, Tooltip


def parse_workers(text, default_scan=120, default_speed=24):
    """解析并发线程双值，如 "120/24" → (扫描120, 测速24)。只填一个数如 "24" → (24,24)。"""
    vals = []
    for part in re.split(r"[/,，\s]+", (text or "").strip()):
        if part.isdigit() and int(part) > 0:
            vals.append(int(part))
    if not vals:
        return default_scan, default_speed
    scan_w = vals[0]
    speed_w = vals[1] if len(vals) > 1 else vals[0]
    return scan_w, speed_w

class App:
    """AFipScan 主窗口。"""

    def __init__(self, root):
        self.root = root
        root.title("AF_ipscan — CF 优选 IP 工具")
        apply_style(root)
        try:
            icon_path = config.bundled_path("app_icon.ico") or os.path.join(get_base_dir(), "app_icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass
        self.running = False
        self.active_mode = None      # 当前运行的模式: scan / speed / None
        self.scanned = []            # 扫描IP段留下的合规存量IP
        self.msgq = queue.Queue()
        self.best = []
        # 按钮图标资源（保持引用，防止被 GC 回收）
        self.icons = {
            "start": icons.icon_photo("start"),
            "export": icons.icon_photo("export"),
            "env": icons.icon_photo("env"),
            "write": icons.icon_photo("write"),
            "gear": icons.icon_photo("gear"),
            "check": icons.icon_photo("check", color="green"),
            "arrow": icons.icon_photo("arrow"),
        }
        # 彩色按钮用白色图标（绿/红底上对比清晰，Tabler 22x22）
        self.icons_white = {
            "start": icons.icon_photo("start", color="white"),
            "export": icons.icon_photo("export", color="white"),
            "env": icons.icon_photo("env", color="white"),
        }
        # 白底彩色文字按钮用彩色图标（绿色=开始，红色=停止）
        self.icons_green = {
            "start": icons.icon_photo("start", color="green"),
            "export": icons.icon_photo("export", color="green"),
            "env": icons.icon_photo("env", color="green"),
        }
        # 白底红字按钮用红色图标（停止扫码/停止测速）
        self.icons_red = {
            "stop": icons.icon_photo("stop", color="red"),
        }

        self._build_header(root)
        self._build_params(root)
        self._build_edgetunnel(root)
        self._build_joey(root)
        self._build_buttons(root)
        self._build_results(root)
        self._build_log(root)

        self.log("就绪！")
        self.log("点【扫描IP段】留下合规IP → 点【开始测速】实测带宽 → 点【一键写入】→ v2rayN 更新订阅。")
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
        tk.Label(head, text="AF_ipscan", bg="#ffffff", fg=ACCENT,
                 font=(FONT, 16, "bold")).pack(side="left", pady=6)
        tk.Label(head, text="扫描IP段 → 开始测速 → 写入到项目 → v2rayN 更新订阅",
                 bg="#ffffff", fg=MUTED, font=(FONT, 9)).pack(side="left", padx=6, pady=6)
        # 分隔线 + 增加功能联系 + 箭头 + GitHub 图标（点击打开仓库）
        tk.Label(head, text="|", bg="#ffffff", fg=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=(0, 4), pady=6)
        def _open_repo(e=None):
            webbrowser.open("https://github.com/itsaphantasy/AFipScan")
        _contact = tk.Label(head, text="增加功能联系", bg="#ffffff", fg=MUTED,
                            font=(FONT, 9), cursor="hand2")
        _contact.pack(side="left", padx=(0, 2), pady=6)
        _contact.bind("<Button-1>", _open_repo)
        _arrow = tk.Label(head, text="→", bg="#ffffff", fg=MUTED,
                          font=(FONT, 9), cursor="hand2")
        _arrow.pack(side="left", padx=(0, 4), pady=6)
        _arrow.bind("<Button-1>", _open_repo)
        self.gh_icon = icons.github_photo()
        gh_icon = tk.Label(head, image=self.gh_icon, bg="#ffffff", cursor="hand2")
        gh_icon.pack(side="left", padx=(0, 8), pady=6)
        gh_icon.bind("<Button-1>", _open_repo)
        # 绿色细线分隔标题与内容
        tk.Frame(root, bg="#0e9f6e", height=2).pack(fill="x")

    def _build_params(self, root):
        """参数设置区：第一行四个参数 + 获取IP，第二行推荐端口提示。"""
        top = ttk.LabelFrame(root, text=" ① 参数设置(鼠标悬停看说明) ")
        top.pack(fill="x", padx=12, pady=6)
        ttk.Label(top, text="端口:").grid(row=0, column=0, padx=(12,2), pady=(8,2), sticky="e")
        self.port_var = tk.StringVar(value=str(config.PORT_DEFAULT))
        e = RoundedEntry(top, textvariable=self.port_var, width=9)
        e.grid(row=0, column=1, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "ALL OPEN=全部推荐端口(443/8443/2053/2083/2087/2096)\n要改端口就删掉，直接填数字，多个用逗号分隔(如 443,8443,2053)")
        ttk.Label(top, text="测速数量:").grid(row=0, column=2, padx=(12,2), pady=(8,2), sticky="e")
        self.top_var = tk.StringVar(value=str(TOP_DEFAULT))
        e = RoundedEntry(top, textvariable=self.top_var, width=5)
        e.grid(row=0, column=3, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "保留前 N 个最快 IP(默认12)")
        ttk.Label(top, text="并发线程:").grid(row=0, column=4, padx=(12,2), pady=(8,2), sticky="e")
        self.workers_var = tk.StringVar(value=str(WORKERS_DEFAULT))
        e = RoundedEntry(top, textvariable=self.workers_var, width=7)
        e.grid(row=0, column=5, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "双功能并发：前面=扫描IP段并发(默认120)，后面=开始测速并发(默认3)\n格式 12/3；只填一个数则扫描和测速都用它")
        ttk.Label(top, text="延迟上限(ms):").grid(row=0, column=6, padx=(12,2), pady=(8,2), sticky="e")
        self.limit_var = tk.StringVar(value=str(LIMIT_DEFAULT))
        e = RoundedEntry(top, textvariable=self.limit_var, width=5)
        e.grid(row=0, column=7, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "只保留低于该延迟的结果(默认300;扫不到调600)")
        # IP源和区域设置：打开候选源 + 地区筛选弹窗（原底部按钮移到这里）
        b = RoundedButton(top, text="IP源和区域设置", command=self.import_ips,
                          style="default", width=140, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["gear"],
                          autofit=True,
                          tooltip="选择候选IP源 + 勾选要优选的地区(可多选；不勾=扫描全部)")
        b.grid(row=0, column=8, padx=(12,12), pady=(8,2), sticky="e")
        # 推荐端口提示(占满整行)
        ttk.Label(top,
                  text="框内 ALL OPEN = 全部推荐端口（443/8443/2053/2083/2087/2096），要改就删掉自填端口",
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

    def _build_joey(self, root):
        """CFnew 设置区：与 edgetunnel 类似，接口/密码/订阅 + 一键写入。"""
        joey = ttk.LabelFrame(root, text=" ③ CFnew 设置(接口/密码/订阅) ")
        joey.pack(fill="x", padx=12, pady=6)
        ttk.Label(joey, text="接口:").grid(row=0, column=0, padx=(12,2), pady=(8,2), sticky="e")
        self.joey_panel_var = tk.StringVar(value=str(JOEY_PANEL or ""))
        e = RoundedEntry(joey, textvariable=self.joey_panel_var, width=22)
        e.grid(row=0, column=1, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "CFnew 面板地址(登录后台用)")
        ttk.Label(joey, text="密码:").grid(row=0, column=2, padx=(12,2), pady=(8,2), sticky="e")
        self.joey_pwd_var = tk.StringVar(value=str(JOEY_PASSWORD or ""))
        e = RoundedEntry(joey, textvariable=self.joey_pwd_var, width=12, show="*")
        e.grid(row=0, column=3, padx=4, pady=(8,2), sticky="w")
        Tooltip(e.entry, "CFnew 面板登录密码")
        ttk.Label(joey, text="订阅地址:").grid(row=0, column=4, padx=(12,2), pady=(8,2), sticky="e")
        self.joey_sub_var = tk.StringVar(value=str(JOEY_SUB_URL or ""))
        e = RoundedEntry(joey, textvariable=self.joey_sub_var, width=24)
        e.grid(row=0, column=5, padx=4, pady=(8,2), sticky="w")
        e.entry.bind("<Double-Button-1>",
                     lambda ev: self.sub_dbl_click(ev, self.joey_sub_var))
        Tooltip(e.entry, "CFnew 订阅链接(双击框内自动复制, 去 v2rayN 添加订阅)")
        # 一键写入按钮：默认白，写入成功变绿
        self.joey_write_btn = RoundedButton(joey, text="一键写入", command=self.apply_joey,
                                            style="default", width=150, height=38,
                                            canvas_bg="#ffffff",
                                            image=self.icons["write"],
                                            tooltip="把测速结果自动写入 CFnew 面板(用上面填的接口和密码)\n写入成功按钮变绿色\n然后去 v2rayN 更新订阅")
        self.joey_write_btn.grid(row=0, column=6, padx=(12,12), pady=(8,2), sticky="e")
        # 操作说明
        ttk.Label(joey, text="先测速，填入CFnew项目地址密码和订阅地址，可以一键写入到项目后台。",
                  foreground="#6b7280", font=(FONT, 11)).grid(row=1, column=0, columnspan=7,
                                                              padx=(12,4), pady=(2,10), sticky="w")

    def _build_buttons(self, root):
        """按钮区：开始测速/停止/导出结果/一键复制/清空日志。"""
        btns = tk.Frame(root, bg="#ffffff")
        btns.pack(fill="x", padx=12, pady=4)
        # 扫描IP段：只测延迟，留下延迟合规的IP
        self.scan_btn = RoundedButton(btns, text="扫描IP段", command=self.toggle_scan,
                                      style="accent_light", width=124, height=40,
                                      canvas_bg="#ffffff",
                                      image=self.icons["start"],
                                      image_on_color=self.icons_white["start"],
                                      image_light=self.icons_green["start"],
                                      tooltip="扫描IP段：拉取候选IP → 测延迟 → 留下延迟合规的IP\n运行中再点一次=停止")
        self.scan_btn.pack(side="left", padx=4)
        # 开始测速：对扫描留下的合规IP实测下载速度
        self.speed_btn = RoundedButton(btns, text="开始测速", command=self.toggle_speed,
                                       style="accent_light", width=124, height=40,
                                       canvas_bg="#ffffff",
                                       image=self.icons["start"],
                                       image_on_color=self.icons_white["start"],
                                       image_light=self.icons_green["start"],
                                       tooltip="开始测速：对扫描留下的合规IP实测下载速度，按速度从高到低\n需要先点【扫描IP段】；运行中再点一次=停止")
        self.speed_btn.pack(side="left", padx=4)
        b = RoundedButton(btns, text="导出结果", command=self.export,
                          style="accent_light", width=112, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["export"],
                          image_on_color=self.icons_white["export"],
                          image_light=self.icons_green["export"],
                          autofit=True,
                          tooltip="把结果保存成 txt(可手动粘贴到面板)")
        b.pack(side="left", padx=4)
        b = RoundedButton(btns, text="环境检测", command=self.env_check,
                          style="accent_light", width=132, height=40,
                          canvas_bg="#ffffff",
                          image=self.icons["env"],
                          image_on_color=self.icons_white["env"],
                          image_light=self.icons_green["env"],
                          autofit=True,
                          tooltip="一键检测本机网络/系统代理/v2rayN代理/面板/候选IP源是否正常")
        b.pack(side="left", padx=4)

    def _build_results(self, root):
        """测速结果表格：速度从高到低。"""
        res = ttk.LabelFrame(root, text=" ④ 测速结果(速度从高到低) ")
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
        self.res_vsb = ttk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.res_vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        self.res_vsb.pack(side="right", fill="y", pady=4)
        self.tree.bind("<Configure>", lambda e: self._sync_res_vsb())
        self._sync_res_vsb()
        # 右键菜单：复制优选IP（替代原一键复制按钮）
        self.tree_menu = tk.Menu(root, tearoff=0)
        self.tree_menu.add_command(label="📋 复制优选IP", command=self.copy_all)
        self.tree.bind("<Button-3>", self._tree_menu_popup)

    def _sync_res_vsb(self):
        # 结果表格滚动条：仅在行数超过可视行数时显示，避免空表出现多余竖条
        if not hasattr(self, "res_vsb"):
            return
        try:
            visible = max(1, int(self.tree.cget("height")))
        except Exception:
            visible = 5
        show = len(self.tree.get_children()) > visible
        if show and self.res_vsb.winfo_manager() != "pack":
            self.res_vsb.pack(side="right", fill="y", pady=4)
        elif not show and self.res_vsb.winfo_manager() == "pack":
            self.res_vsb.pack_forget()

    def _build_log(self, root):
        """日志区：默认高度较大，便于查看扫描进度。"""
        logf = ttk.LabelFrame(root, text=" ⑤ 日志(扫描进度/结果) ")
        logf.pack(fill="both", expand=True, padx=12, pady=6)
        self.log_text = tk.Text(logf, height=7, bg="#0b1e33", fg="#e8f1ff",
                                font=("Consolas", 11), relief="flat",
                                insertbackground="#e8f1ff")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=3)
        self.log_text.tag_configure("ok", foreground="#3ddc84")
        self.log_text.tag_configure("err", foreground="#ff6b6b")
        self.log_text.tag_configure("info", foreground="#7dd3fc")
        # 右键菜单：清空日志（替代原清空日志按钮）
        self.log_menu = tk.Menu(root, tearoff=0)
        self.log_menu.add_command(label="🧹 清空日志",
                                  command=lambda: self.log_text.delete("1.0", "end"))
        self.log_text.bind("<Button-3>", self._log_menu_popup)

    # ==================== 界面反馈 ====================

    def log(self, msg):
        """往日志区追加一行并自动滚到底部（状态前缀按绿/红/信息着色）。"""
        tag = None
        head = msg[:6]
        if head.startswith("[✓]") or head.startswith("[OK]"):
            tag = "ok"
        elif head.startswith("[✗]") or head.startswith("[!]"):
            tag = "err"
        elif head.startswith("[*]") or head.startswith("[i]"):
            tag = "info"
        if tag:
            end = msg.find("]") + 1
            self.log_text.insert("end", msg[:end], tag)
            self.log_text.insert("end", msg[end:] + "\n")
        else:
            self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def poll_queue(self):
        """主线程轮询子线程消息，刷新界面。"""
        try:
            while True:
                msg = self.msgq.get_nowait()
                if msg[0] == "log":
                    self.log(msg[1])
                elif msg[0] == "done_scan":
                    self.scan_done(msg[1])
                elif msg[0] == "done_speed":
                    self.speed_done(msg[1])
                elif msg[0] in ("writeok", "joeyok"):
                    try:
                        (self.write_btn if msg[0] == "writeok"
                         else self.joey_write_btn).config(
                            text="写入成功", style="Success.TButton")
                    except Exception:
                        pass
                elif msg[0] == "save_state":
                    self.save_ui_state()
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
                "joey_panel": self.joey_panel_var.get().strip(),
                "joey_password": self.joey_pwd_var.get().strip(),
                "joey_subscription_url": self.joey_sub_var.get().strip(),
                "port_default": self.port_var.get().strip(),
                "top_default": _int(self.top_var.get(), 12),
                "workers_default": (self.workers_var.get().strip() or "12/3"),
                "limit_default": _int(self.limit_var.get(), 300),
            })
            debug_log("UI 状态已写入 config.json")
        except Exception as e:
            debug_log("保存 UI 状态失败: " + str(e)[:80])

    def on_close(self):
        """关闭窗口：先保存当前填写的内容，再退出。"""
        self.save_ui_state()
        self.root.destroy()

    # ==================== 扫描 / 测速 ====================

    def _reset_buttons(self):
        """恢复两个按钮到未运行状态：白底绿字，全部可点。"""
        self.scan_btn.set_state("normal")
        self.scan_btn.set_content("扫描IP段", style="accent_light",
                                  image=self.icons["start"],
                                  image_on_color=self.icons_white["start"],
                                  image_light=self.icons_green["start"])
        self.speed_btn.set_state("normal")
        self.speed_btn.set_content("开始测速", style="accent_light",
                                   image=self.icons["start"],
                                   image_on_color=self.icons_white["start"],
                                   image_light=self.icons_green["start"])

    def toggle_scan(self):
        """扫描IP段：未运行=开始扫描，运行中=停止。"""
        if self.running:
            if self.active_mode == "scan":
                self.stop_scan()
            else:
                self.msgq.put(("log", "[!] 正在测速中，请先点【开始测速】停止"))
        else:
            self.start_scan()

    def toggle_speed(self):
        """开始测速：未运行=开始测速，运行中=停止。"""
        if self.running:
            if self.active_mode == "speed":
                self.stop_speed()
            else:
                self.msgq.put(("log", "[!] 正在扫描中，请先点【扫描IP段】停止"))
        else:
            self.start_speed()

    def start_scan(self):
        """开始扫描IP段：按钮变"停止扫描"(红)、测速按钮禁用、清空表格与存量。"""
        debug_log("start_scan 被调用")
        if self.running:
            return
        self.running = True
        self.active_mode = "scan"
        self.save_ui_state()  # 记录当前参数到 config.json
        self.scan_btn.set_content("停止扫描", style="danger_light",
                                  image=None, image_on_color=None,
                                  image_light=self.icons_red["stop"])
        self.speed_btn.set_state("disabled")
        self.write_btn.config(text="一键写入", style="default")
        self.joey_write_btn.config(text="一键写入", style="default")
        self.tree.delete(*self.tree.get_children())
        self._sync_res_vsb()
        self.scanned = []  # 清空上一轮的合规存量IP
        threading.Thread(target=self.scan_worker,
                         args=(self.top_var.get(), self.limit_var.get(),
                               self.workers_var.get(), self.port_var.get()),
                         daemon=True).start()

    def stop_scan(self):
        """请求停止扫描：按钮恢复，当前批次结束后停下。"""
        debug_log("stop_scan 被调用")
        self.running = False
        self.active_mode = None
        self._reset_buttons()
        self.msgq.put(("log", "[*] 已请求停止(等当前批次结束)"))

    def start_speed(self):
        """开始测速：对扫描留下的合规IP实测下载速度。"""
        debug_log("start_speed 被调用")
        if self.running:
            return
        if not getattr(self, "scanned", None):
            self.msgq.put(("log", "[!] 还没有扫描结果，请先点【扫描IP段】留下合规IP"))
            return
        self.running = True
        self.active_mode = "speed"
        self.save_ui_state()
        self.speed_btn.set_content("停止测速", style="danger_light",
                                   image=None, image_on_color=None,
                                   image_light=self.icons_red["stop"])
        self.scan_btn.set_state("disabled")
        self.write_btn.config(text="一键写入", style="default")
        self.joey_write_btn.config(text="一键写入", style="default")
        self.tree.delete(*self.tree.get_children())
        self._sync_res_vsb()
        threading.Thread(target=self.speed_worker,
                         args=(self.top_var.get(), self.workers_var.get()),
                         daemon=True).start()

    def stop_speed(self):
        """请求停止测速：按钮恢复，当前批次结束后停下。"""
        debug_log("stop_speed 被调用")
        self.running = False
        self.active_mode = None
        self._reset_buttons()
        self.msgq.put(("log", "[*] 已请求停止(等当前批次结束))"))

    def scan_worker(self, top_raw, limit_raw, workers_raw, port_raw):
        """测速线程：拉候选 → 并发测速 → 排序 → 回传结果。"""
        try:
            top = int(top_raw)
            limit = int(limit_raw)
        except ValueError:
            self.msgq.put(("log", "[!] 参数必须是数字"))
            self.running = False
            self.msgq.put(("done_scan", []))
            return
        scan_workers, _ = parse_workers(workers_raw)
        raw = port_raw.strip()
        is_all_open = raw.upper().replace(" ", "") in ("ALLOPEN", "ALL", "ALL_OPEN")
        ports = []
        if not is_all_open:
            for part in re.split(r"[,，\s]+", raw):
                if part.isdigit() and 1 <= int(part) <= 65535:
                    ports.append(int(part))
        if not raw or is_all_open:
            ports = list(config.RECOMMEND_PORTS)
            self.msgq.put(("log", "[*] ALL OPEN，默认扫描全部推荐端口：%s" % config.RECOMMEND_PORTS_STR))
        elif not ports:
            self.msgq.put(("log", "[!] 端口必须是数字(可逗号分隔多个, 如 443,8443)，或填 ALL OPEN 全开"))
            self.running = False
            self.msgq.put(("done_scan", []))
            return
        self.current_ports = ports
        # 地区筛选：从「导入更多优选IP」勾选的地区来（可多选；不勾=扫描全部）
        needles = [x for x in config.REGION_FILTER if x]
        region_target = netutils.region_file(needles) if needles else None
        region_desc = "、".join(needles) if needles else "全部"
        if region_target:
            self.msgq.put(("log", "[*] 正在拉取候选 IP 列表 ...（筛选地区 %s，直接拉 %s 地区文件）" % (region_desc, region_target)))
        elif needles:
            self.msgq.put(("log", "[*] 正在拉取候选 IP 列表 ...（筛选地区 %s，VPS已分类）" % region_desc))
        else:
            self.msgq.put(("log", "[*] 正在拉取候选 IP 列表 ..."))
        debug_log("scan_worker 启动, ports=%s top=%s scan_workers=%s limit=%s region=%s target=%s"
                  % (ports, top, scan_workers, limit, region_desc, region_target))
        # 并行拉取多个候选源，谁先到先用；拉取失败自动用上次成功的本地缓存兜底
        import concurrent.futures
        fetch_urls = list(config.CANDIDATE_URLS)
        if region_target:
            fetch_urls = [config.vps_region_url(region_target) if u == config.VPS_ALL_URL else u for u in fetch_urls]
        cands = []
        cache = config.load_candidate_cache()
        cache_dirty = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(fetch_urls) or 1) as fex:
            futs = {fex.submit(netutils.fetch, url): url for url in fetch_urls}
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
        # ---- 过滤非 Cloudflare 官方 IP：中转机/AWS/腾讯云节点不能作为 CF 优选节点 ----
        cf_cands = [c for c in cands if config.is_cloudflare_ip(c[0])]
        skipped = len(cands) - len(cf_cands)
        if skipped:
            self.msgq.put(("log", f"[i] 已过滤 {skipped} 个非Cloudflare官方IP（中转机），保留 {len(cf_cands)} 个候选"))
        cands = cf_cands
        if not cands:
            self.msgq.put(("log", "[!] 没有属于Cloudflare官方IP的候选，无法扫描"))
            self.running = False
            self.msgq.put(("done_scan", []))
            return
        # ---- 地区预筛：填了地区码就按 VPS 已标注地区筛出目标IP(无需现场识别) ----
        pre_ip_code = {}
        if needles:
            def _in_region(c):
                tag = (c[2] or '').strip().upper()
                return any(netutils.region_matches(nd, tag, netutils.region_name(tag) if tag else '') for nd in needles)
            matched = [c for c in cands if _in_region(c)]
            if not matched:
                self.msgq.put(("log", "[!] 该地区没有匹配的IP（确认已勾选VPS总源并成功拉取）"))
                self.running = False
                self.msgq.put(("done_scan", []))
                return
            pre_ip_code = {c[0]: c[2] for c in matched if c[2]}
            self.msgq.put(("log", f"[*] 地区 {region_desc}：{len(cands)} 个候选中筛出 {len(matched)} 个（VPS已分类，无需现场识别）"))
            cands = matched
            try:
                config.save_region_filter(True, needles)
            except Exception:
                pass
        # 多端口时每个 IP × 每个端口各测一遍
        if len(ports) > 1:
            cands = [(ip, p, tag) for ip, _p, tag in cands for p in ports]
            debug_log("候选总数 %d (IP %d × 端口 %s), 开始测速" % (len(cands), len(uniq), ports))
            self.msgq.put(("log", f"[*] 测速 {len(uniq)} 个IP × {len(ports)} 个端口 = {len(cands)} 组 ..."))
        else:
            debug_log("候选总数 %d, 开始测速" % len(cands))
            self.msgq.put(("log", f"[*] 开始测速，共 {len(cands)} 个候选 ..."))
        results = []
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=scan_workers)
        try:
            futs = {ex.submit(netutils.probe, c[0], c[1], 3): c for c in cands}
            done = 0
            _prog_t = time.time()
            for f in concurrent.futures.as_completed(futs):
                done += 1
                c = futs[f]
                ms = f.result()
                if ms is not None and ms <= limit:
                    results.append((ms, c[0], c[1], c[2]))
                _now = time.time()
                if _now - _prog_t >= 1.0 or done == len(cands):
                    _prog_t = _now
                    self.msgq.put(("log", f"    已测 {done}/{len(cands)} ..."))
                if not self.running:
                    break
        finally:
            # 停止时不等待在测任务，立即返回，UI 快速恢复
            ex.shutdown(wait=False, cancel_futures=True)

        # ---- 识别真实机房地区：优先用 VPS 自带标注，缺的才对达标IP现场查地区 ----
        region_map = {(ip, port): tag for _ms, ip, port, tag in results if tag}
        todo_ips = [(ip, port) for _ms, ip, port, tag in results if not tag]
        if pre_ip_code:
            for _ms, ip, port, _t in results:
                code = pre_ip_code.get(ip)
                if code:
                    region_map[(ip, port)] = code
            todo_ips = [(ip, port) for _ms, ip, port, _t in results
                        if not region_map.get((ip, port))]
        if self.running and todo_ips:
            results.sort(key=lambda r: r[0])  # 延迟低在前
            cap = min(len(todo_ips), 400)     # 最多查 400 个，避免太慢
            region_list = todo_ips[:cap]
            self.msgq.put(("log", f"[*] 正在识别 {cap} 个IP的真实机房地区 ..."))
            rex = concurrent.futures.ThreadPoolExecutor(max_workers=min(scan_workers, 16))
            try:
                rfuts = {rex.submit(netutils.get_iata, ip, port): (ip, port)
                         for ip, port in region_list}
                for rf in concurrent.futures.as_completed(rfuts):
                    if not self.running:
                        break
                    ip, port = rfuts[rf]
                    try:
                        code = rf.result()
                        if code:
                            region_map[(ip, port)] = code
                    except Exception:
                        pass
            finally:
                rex.shutdown(wait=False, cancel_futures=True)

        # 给结果补真实地区：iata 三字码 + 中文名
        tagged = []
        for ms, ip, port, tag in results:
            code = region_map.get((ip, port)) or ""
            chinese = netutils.region_name(code) if code else (tag if tag else "未知")
            tagged.append((ms, ip, port, code, chinese))

        # ---- 扫描完成：合规存量IP存下来，供【开始测速】实测带宽 ----
        tagged.sort(key=lambda r: r[0])          # 延迟低在前
        self.scanned = tagged
        debug_log("扫描完成, 合规IP %d 个" % len(tagged))
        self.msgq.put(("done_scan", tagged))

    def speed_worker(self, top_raw, workers_raw):
        """测速线程：对扫描留下的合规IP实测下载速度，按速度从高到低排序。"""
        try:
            top = int(top_raw)
        except ValueError:
            self.msgq.put(("log", "[!] 参数必须是数字"))
            self.running = False
            self.active_mode = None
            self.msgq.put(("done_speed", []))
            return
        _sc, speed_workers = parse_workers(workers_raw)
        tagged = getattr(self, "scanned", None) or []
        if not tagged:
            self.msgq.put(("log", "[!] 还没有扫描结果，请先点【扫描IP段】留下合规IP"))
            self.running = False
            self.active_mode = None
            self.msgq.put(("done_speed", []))
            return
        import concurrent.futures
        self.msgq.put(("log", f"[*] 正在实测 {len(tagged)} 个合规IP的下载速度 ..."))
        speed_map = {}
        sex = concurrent.futures.ThreadPoolExecutor(max_workers=min(speed_workers, 24))
        try:
            sfuts = {sex.submit(netutils.speed_probe, ip, port): (ip, port)
                     for ms, ip, port, _code, _cn in tagged}
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
        for ms, ip, port, _code, chinese in tagged:
            final.append((ms, ip, port, chinese, speed_map.get((ip, port))))
        # 速度高在前；没测到速度的按延迟排在最前（也算有结果）
        final.sort(key=lambda r: (-(r[4] or 0), r[0]))
        debug_log("测速完成, 测到速度 %d 个, 取前 %d" % (len(speed_map), top))
        self.msgq.put(("done_speed", final[:top]))

    def scan_done(self, best):
        """扫描完成：恢复按钮，表格显示合规IP(按延迟)，日志提示去测速。"""
        self.running = False
        self.active_mode = None
        self._reset_buttons()
        if not best:
            self.log("[!] 没扫到合规IP，把【延迟上限】调高(如600)再试")
            return
        self.log(f"\n===== 扫描完成：{len(best)} 个合规IP(按延迟) =====")
        for i, (ms, ip, port, _code, chinese) in enumerate(best):
            tagname = "odd" if i % 2 else "even"
            self.tree.insert("", "end",
                             values=(f"{ip}:{port}", f"{ms:.0f}", "-", chinese or "优选"),
                             tags=(tagname,))
        self.log(f"[*] 共 {len(best)} 个合规IP，点【开始测速】实测下载带宽")
        self._sync_res_vsb()

    def speed_done(self, best):
        """测速完成：恢复按钮，表格按速度从高到低显示，日志提示写入。"""
        self.running = False
        self.active_mode = None
        self._reset_buttons()
        self.best = best
        if not best:
            self.log("[!] 没测到速度，可再点【开始测速】重试")
            return
        self.log("\n===== 测速结果(按速度) =====")
        for i, (ms, ip, port, chinese, speed) in enumerate(best):
            tagname = "odd" if i % 2 else "even"
            sp = f"{speed:.0f}" if speed else "-"
            self.tree.insert("", "end",
                             values=(f"{ip}:{port}", f"{ms:.0f}", sp, chinese or "优选"),
                             tags=(tagname,))
            self.log(f"  {ip}:{port}  {ms:.0f}ms  {sp}Mbps")
        self.log("[*] 测速完成！点【一键写入】写入配置，然后去 v2rayN 更新订阅")
        self._sync_res_vsb()

    # ==================== 获取 IP ====================

    def import_ips(self):
        """打开弹窗：勾选要使用的优选IP源；点「获取更多源地址」可追加更多源。

        列表区做成固定高度 + 滚动条，源再多也不会把底部按钮挤出屏幕；
        按钮栏固定在窗口底部，始终可见。
        """
        win = tk.Toplevel(self.root)
        win.title("导入更多优选IP地址")
        win.configure(bg="#ffffff")
        win.resizable(False, False)
        # ---- 可滚动列表区：内容超出固定高度时用滚轮/滚动条查看 ----
        list_area = tk.Frame(win, bg="#ffffff")
        list_area.pack(fill="both", expand=True, padx=14, pady=(14, 0))
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
            """鼠标滚轮：内容完整显示时固定不滚，只有下方有内容显示不全时才滚动。"""
            try:
                bb = canvas.bbox("all")
                content_h = (bb[3] - bb[1]) if bb and bb[3] > bb[1] else 0
                if content_h <= canvas.winfo_height() + 1:
                    return
            except Exception:
                pass
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 初始列表 = 已保存源 ∪ 默认 3 个高速源，全部勾选（不丢用户已有配置）
        saved = [u for u in config.CANDIDATE_URLS if u]
        defaults = [u for u in config.DEFAULT_CONFIG["candidate_urls"] if u not in saved]
        vars_ = {}

        def add_row(url, checked):
            """在弹窗列表里加一行：默认总源用绿色对勾+单行地址；其它源用勾选框。"""
            var = tk.BooleanVar(value=checked)
            vars_[url] = var
            row = tk.Frame(source_content, bg="#ffffff")
            row.pack(fill="x", pady=2)
            name = config.SOURCE_NAMES.get(url, url.split("/")[-1])
            if url == config.VPS_ALL_URL:
                # 默认总源：常开不勾选，用绿色对勾图标，地址跟在名称后面同一行
                tk.Label(row, image=self.icons["check"], bg="#ffffff").pack(
                    side="left", anchor="center", padx=(0, 6))
                tk.Label(row, text=f"{name} {url}", bg="#ffffff",
                         fg="#374151", font=("Microsoft YaHei UI", 9),
                         anchor="w", justify="left").pack(
                    side="left", fill="x", expand=True)
            else:
                tk.Checkbutton(row, variable=var, bg="#ffffff",
                               activebackground="#ffffff", bd=0,
                               highlightthickness=0).pack(side="left", anchor="center")
                tk.Label(row, text=f"{name}\n{url}", bg="#ffffff",
                         fg="#374151", font=("Microsoft YaHei UI", 9),
                         anchor="w", justify="left", wraplength=600).pack(
                    side="left", fill="x", expand=True)

        # ---- 地区筛选：前两行常显，点击「地区筛选」展开/收起其它地区 ----
        region_header = tk.Label(body, text="▸ 地区筛选（点我展开其它地区，可多选；不勾=扫描全部）",
                                 bg="#ffffff", fg="#0e9f6e", font=("Microsoft YaHei UI", 9),
                                 cursor="hand2", anchor="w")
        region_header.pack(anchor="w", pady=(10, 2))
        region_content = tk.Frame(body, bg="#ffffff")   # 地区勾选内容区：前两行常显
        avail = {}
        try:
            vtext = config.load_candidate_cache().get(config.VPS_ALL_URL, "")
        except Exception:
            vtext = ""
        if vtext:
            for _ip, _p, tag in netutils.parse_lines(vtext, 443):
                c2 = netutils.COUNTRY_OF.get((tag or "").strip().upper(), "")
                if c2 and c2 in netutils.COUNTRY_NAMES:
                    avail.setdefault(c2, netutils.COUNTRY_NAMES[c2])
        if not avail:
            avail = dict(netutils.COUNTRY_NAMES)  # 无缓存时直接用全部标准地区，秒开不卡
        _prio = ["HK", "TW", "JP", "KR", "SG", "US", "DE", "NL", "GB", "AU", "CA", "IN", "AE", "BR"]
        codes = sorted(avail, key=lambda c: (_prio.index(c) if c in _prio else 99, c))
        cur = list(config.REGION_FILTER)
        region_vars = {}
        _per_row = 4
        _show_n = _per_row * 2          # 默认常显前 2 行

        def _mk_checks(frame, clist, start_row):
            for _i, _c in enumerate(clist):
                v = tk.BooleanVar(value=_c in cur)
                region_vars[_c] = v
                tk.Checkbutton(frame, variable=v, text="%s(%s)" % (avail[_c], _c),
                               bg="#ffffff", activebackground="#ffffff", bd=0,
                               highlightthickness=0, font=("Microsoft YaHei UI", 9)
                               ).grid(row=start_row + _i // _per_row, column=_i % _per_row,
                                      sticky="w", padx=(0, 14), pady=2)

        region_content.pack(fill="x", pady=(0, 2))
        _mk_checks(region_content, codes, 0)               # 全部放进同一网格，列自动对齐
        # 第2行及之后的勾选框默认隐藏，点「地区筛选」再展开/收起
        _more_widgets = []
        for _r in range(2, (len(codes) - 1) // _per_row + 1):
            _more_widgets.extend(region_content.grid_slaves(row=_r))
        for w in _more_widgets:
            w.grid_remove()
        _more_shown = [False]

        def _toggle_region(e=None):
            if _more_shown[0]:
                for w in _more_widgets: w.grid_remove()
                _more_shown[0] = False
                region_header.config(text="▸ 地区筛选（点我展开其它地区，可多选；不勾=扫描全部）")
            else:
                for w in _more_widgets: w.grid()
                _more_shown[0] = True
                region_header.config(text="▾ 地区筛选（点我收起）")
            recenter()
        region_header.bind("<Button-1>", _toggle_region)
        # ---- 优选IP源筛选：可折叠导航（类似地区筛选） ----
        source_header = tk.Label(body, text="▸ 优选IP源筛选（点我展开/收起）",
                                 bg="#ffffff", fg="#0e9f6e", font=("Microsoft YaHei UI", 9),
                                 cursor="hand2", anchor="w")
        source_header.pack(anchor="w", pady=(10, 2))
        source_content = tk.Frame(body, bg="#ffffff")
        source_content.pack(fill="x", pady=(0, 2))
        source_shown = [True]

        def _toggle_source(e=None):
            if source_shown[0]:
                source_content.pack_forget()
                source_shown[0] = False
                source_header.config(text="▸ 优选IP源筛选（点我展开）")
            else:
                source_content.pack(fill="x", pady=(0, 2))
                source_shown[0] = True
                source_header.config(text="▾ 优选IP源筛选（点我收起）")
            recenter()
        source_header.bind("<Button-1>", _toggle_source)

        for url in saved + defaults:
            add_row(url, True)


        # 自定义源输入框（源列表下方）：箭头内嵌右侧，触碰/点击有反馈，回车或点箭头=添加
        cbar = tk.Frame(win, bg="#ffffff")
        cbar.pack(fill="x", padx=14, pady=(6, 14))
        custom_var = tk.StringVar()
        custom_entry = RoundedEntry(cbar, textvariable=custom_var, width=48,
                                    placeholder="添加自定义源地址",
                                    right_icon=self.icons["arrow"],
                                    stretch=True)
        custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 14))

        def _add_custom():
            text = custom_var.get().strip()
            urls = [u.strip() for u in re.split(r"[,，\s\n]+", text) if u.strip()]
            urls = [u for u in urls if u.startswith("http")]
            if not urls:
                self.log("[!] 自定义源地址需以 http:// 或 https:// 开头")
                return
            added = 0
            for u in urls:
                if u not in vars_:
                    add_row(u, True)
                    added += 1
            if added:
                self.log(f"[*] 已添加 {added} 个自定义IP源地址（可取消勾选）")
            custom_var.set("")
            recenter()

        custom_entry.set_right_cmd(_add_custom)
        custom_entry.entry.bind("<Return>", lambda e: _add_custom())

        def _save_and_close():
            """保存源勾选 + 地区勾选到配置，再关窗。"""
            try:
                srcs = [u for u, v in vars_.items() if v.get()]
                if not srcs:
                    srcs = [config.VPS_ALL_URL]
                config.save_candidate_urls(srcs)
                regs = [c for c, v in region_vars.items() if v.get()]
                config.save_region_filter(bool(regs), regs)
            except Exception as e:
                self.log("[!] 保存失败: " + str(e))
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _save_and_close)

        def recenter():
            """窗口打开后锁定固定大小，展开/收起地区筛选不再改变窗口；内容多时在弹窗内滚动。"""
            win.update_idletasks()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            canvas.update_idletasks()
            bb = canvas.bbox("all")
            content_h = (bb[3] - bb[1]) if bb and bb[3] > bb[1] else 0
            max_canvas = max(220, int(sh * 0.72) - 210)
            if not getattr(win, "_locked", False):
                canvas_h = min(content_h + 20, max_canvas)
                canvas.configure(height=canvas_h)
                w = 760
                h = min(int((canvas_h + 190) * 1.25), int(sh * 0.92))
                win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")
                win._locked = True
                win._avail = max(220, h - 190)   # 之后内容区域高度不再超过这个值
            else:
                canvas_h = min(content_h + 20, max_canvas, win._avail)
                canvas.configure(height=canvas_h)
            # 内容超高才显示滚动条，否则隐藏（避免出现多余竖线）
            if content_h > canvas_h:
                if vsb.winfo_manager() != "pack":
                    vsb.pack(side="right", fill="y")
            else:
                if vsb.winfo_manager() == "pack":
                    vsb.pack_forget()
            canvas.yview_moveto(0)


        RoundedButton(cbar, text="确定", command=_save_and_close, style="accent_light",
                      width=88, height=42, canvas_bg="#ffffff").pack(side="right")
        recenter()
        canvas.focus_set()

    def env_check(self):
        """一键环境检测：后台线程逐项检查并输出到日志。"""
        self.log("[*] 开始一键环境检测 ...")
        threading.Thread(target=self.env_check_worker,
                         args=(self.panel_var.get().strip().rstrip("/"),
                               self.pwd_var.get().strip()),
                         daemon=True).start()

    def env_check_worker(self, base, pwd):
        """逐项检测：系统代理/局域网/公网/本地代理/面板/候选源。"""
        import socket as _socket
        import subprocess
        # 2. 系统代理
        sys_proxy = netutils.check_sys_proxy()
        self.msgq.put(("log", f"[{'✗' if sys_proxy else '✓'}] 系统代理: {'已开启(建议优选前关闭)' if sys_proxy else '未开启(正常)'}"))
        # 3. 局域网 IP
        lan = netutils.get_lan_ip()
        self.msgq.put(("log", f"[{'✓' if lan else '✗'}] 局域网 IP: {lan or '获取失败'}"))
        # 4. 公网直连（判断能否上外网）
        direct = netutils.get_wan_ip(None)
        self.msgq.put(("log", f"[{'✓' if direct else '✗'}] 公网直连: {direct or '获取失败(可能断网/被墙)'}"))
        # 5. v2rayN 本地代理连通性
        proxy_ok = False
        try:
            host, port = PROXY_URL.split("://")[1].rsplit(":", 1)
            s = _socket.create_connection((host, int(port)), timeout=3)
            s.close()
            proxy_ok = True
        except Exception:
            pass
        self.msgq.put(("log", f"[{'✓' if proxy_ok else '✗'}] v2rayN 本地代理({PROXY_URL}): {'可连接' if proxy_ok else '连不上(先启动v2rayN)'}"))
        # 6. 代理出口 IP
        if proxy_ok:
            p_ip = netutils.get_wan_ip(PROXY_URL)
            self.msgq.put(("log", f"[{'✓' if p_ip else '✗'}] 代理出口 IP: {p_ip or '获取失败'}"))
        # 7. edgetunnel 面板
        ok, msg = check_panel(base, pwd)
        self.msgq.put(("log", f"[{'✓' if ok else '✗'}] edgetunnel 面板: {msg}"))
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
                self.msgq.put(("log", f"[✗] 候选源 {url.split('/')[-1]}: 拉取失败 {str(e)[:40]}{tip}"))
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
        self.msgq.put(("log", f"[{'✓' if fw_ok == 3 else '✗'}] Windows 防火墙: {fw_ok}/3 个配置开启({fw_tip})"))
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
            self.msgq.put(("log", f"[{'✓' if v2ray else '✗'}] v2rayN 内核防火墙规则: {v_tip}"))
            self.msgq.put(("log", f"[✓] AF_ipscan 防火墙规则: {c_tip}"))
        except Exception as e:
            self.msgq.put(("log", f"[✗] 防火墙规则检测失败: {str(e)[:50]}"))
        self.msgq.put(("log", "[OK] 环境检测完成"))

    def sub_dbl_click(self, e=None, var=None):
        """双击订阅地址框：复制订阅链接到剪贴板。"""
        url = (var or self.sub_var).get().strip()
        if not url:
            self.log("[!] 订阅地址为空")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.log(f"[OK] 订阅地址已双击复制: {url}")

    # ==================== 写入面板 ====================

    def apply_panel(self):
        """一键写入 edgetunnel 面板：后台线程写入。"""
        if not self.best:
            messagebox.showinfo("提示", "请先测速")
            return
        self.log("[*] 正在写入面板 ...")
        threading.Thread(target=self.run_apply_worker,
                         args=(self.panel_var.get().strip().rstrip("/"),
                               self.pwd_var.get().strip(), "writeok", "edgetunnel"),
                         daemon=True).start()

    def apply_joey(self):
        """一键写入 CFnew 面板：后台线程写入。"""
        if not self.best:
            messagebox.showinfo("提示", "请先测速")
            return
        self.log("[*] 正在写入 CFnew 面板 ...")
        threading.Thread(target=self.run_apply_worker,
                         args=(self.joey_panel_var.get().strip().rstrip("/"),
                               self.joey_pwd_var.get().strip(), "joeyok", "cfnew"),
                         daemon=True).start()

    def run_apply_worker(self, base, pwd, ok_msg, target="edgetunnel"):
        """组装优选结果并调用面板写入模块，回传结果。"""
        # 写入前按 IP 查重（保留排在最前=速度最快的），避免面板出现重复节点
        dedup = {}
        for item in self.best:
            if item[1] not in dedup:
                dedup[item[1]] = item
        ip_list = [f"{ip}:{port}#{tag if tag else '优选'}"
                   for _ms, ip, port, tag, _speed in dedup.values()]
        first_port = getattr(self, "current_ports", [443])[0]
        if target == "cfnew":
            ok, msg = write_cfnew(base, pwd, ip_list)
        else:
            ok, msg = write_panel(base, pwd, ip_list, first_port)
        if ok and len(ip_list) != len(self.best):
            self.log(f"[i] 已去重：{len(self.best)} -> {len(ip_list)} 个")
        self.msgq.put(("log", f"[*] 写入IP: {msg}" if not ok else "[OK] " + msg))
        if ok:
            self.msgq.put(("save_state",))  # 主线程把当前填写写入 config.json
            self.msgq.put((ok_msg,))
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


