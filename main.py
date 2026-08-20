# -*- coding: utf-8 -*-
"""AFipScan 程序入口：启动 tkinter 主窗口。"""

import ctypes
import tkinter as tk


# 针对 Windows 8.1/10/11 的高DPI适配（必须在创建窗口之前调用，避免界面模糊）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from afipscan.ui import App


def main():
    """创建主窗口并进入事件循环。"""
    root = tk.Tk()
    root.withdraw()  # 先隐藏，尺寸定好后再显示，避免小窗口闪跳
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
