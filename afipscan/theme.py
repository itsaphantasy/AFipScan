# -*- coding: utf-8 -*-
"""主题模块：全局配色常量与 ttk 样式，统一管理界面外观。"""

from tkinter import ttk


# ===== 配色常量（白色主色调 + 绿色强调） =====
BG = "#ffffff"        # 窗口背景
CARD = "#ffffff"      # 卡片背景
ACCENT = "#0e9f6e"    # 主色（绿色）
ACCENT_H = "#0b8058"  # 主色悬停
ACCENT_D = "#0a6f4d"  # 主色按下
SUCCESS = "#34C759"   # 成功绿（本地IP/写入成功）
SUCCESS_D = "#2db84f"  # 成功绿按下
DANGER = "#FF3B30"    # 危险红（停止/代理IP）
DANGER_D = "#e02e24"  # 红按下
TEXT = "#1f2937"      # 正文
MUTED = "#6b7280"     # 次要说明文字
LABEL = "#374151"     # 字段标签（gray-700，弱于正文、强于提示）
BORDER = "#e5e7eb"    # 边框
HOVER = "#f5f7fa"     # 普通按钮悬停
PRESSED = "#e8eaed"   # 普通按钮按下
FONT = "Microsoft YaHei UI"  # 全局字体（Windows 系统 UI 字体，中文显示最佳）
FONT_SIZE = 12               # 全局字号（高清屏加大，避免过小发虚）


def apply_style(root):
    """给 ttk 控件套用统一样式（ttkbootstrap flatly 主题 + 绿色强调）。

    优先加载 ttkbootstrap flatly（浅色现代）主题；缺失时自动回退 clam 主题。
    """
    use_tb = False
    try:
        import ttkbootstrap as tb
        style = tb.Style(theme="flatly")
        use_tb = True
    except Exception:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
    root.configure(bg=BG)
    style.configure(".", font=(FONT, FONT_SIZE), foreground=TEXT)
    style.configure("TLabel", background=CARD, foreground=LABEL)
    style.configure("TLabelframe", background=CARD, bordercolor=BORDER,
                    relief="solid", borderwidth=1, padding=8)
    style.configure("TLabelframe.Label", background=CARD, foreground=ACCENT,
                    font=(FONT, FONT_SIZE, "bold"))
    style.configure("TEntry", fieldbackground="#ffffff", bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, padding=5,
                    foreground=TEXT, insertcolor=TEXT)
    style.map("TEntry",
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])
    style.configure("TButton", background=CARD, foreground=TEXT, bordercolor=BORDER,
                    borderwidth=1, padding=(14, 8), font=(FONT, FONT_SIZE))
    style.map("TButton",
              background=[("active", HOVER), ("pressed", PRESSED), ("disabled", "#f1f2f4")],
              bordercolor=[("active", "#c8d0da"), ("pressed", "#b7c0ca"), ("focus", ACCENT)],
              foreground=[("disabled", "#9ca3af")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    borderwidth=0, padding=(20, 9), font=(FONT, FONT_SIZE, "bold"))
    style.map("Accent.TButton",
              background=[("active", ACCENT_H), ("pressed", ACCENT_D), ("disabled", "#a7d8c4"), ("focus", ACCENT_D)],
              foreground=[("disabled", "#f0fdf9")])
    style.configure("Success.TButton", background=SUCCESS, foreground="#ffffff",
                    borderwidth=0, padding=(18, 9), font=(FONT, FONT_SIZE, "bold"))
    style.map("Success.TButton",
              background=[("active", SUCCESS_D), ("pressed", SUCCESS_D), ("disabled", "#9ce6b2"), ("focus", SUCCESS_D)],
              foreground=[("disabled", "#f0fdf9")])
    style.configure("Danger.TButton", background=DANGER, foreground="#ffffff",
                    borderwidth=0, padding=(14, 9), font=(FONT, FONT_SIZE, "bold"))
    style.map("Danger.TButton",
              background=[("active", DANGER_D), ("pressed", DANGER_D), ("disabled", "#f1b6b8"), ("focus", DANGER_D)],
              foreground=[("disabled", "#ffffff")])
    style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff",
                    foreground=TEXT, rowheight=30, borderwidth=0)
    style.configure("Treeview.Heading", background="#f5f7fa", foreground="#374151",
                    font=(FONT, FONT_SIZE-2, "bold"), padding=6,
                    borderwidth=1, relief="solid")
    style.map("Treeview", background=[("selected", "#d1fae5")], foreground=[("selected", TEXT)])
    style.configure("TCombobox", fieldbackground="#ffffff", background=CARD,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=4,
                    arrowcolor=TEXT)
