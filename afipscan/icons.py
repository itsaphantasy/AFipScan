# -*- coding: utf-8 -*-
"""图标模块：Tabler 图标库 22x22（base64 内嵌，打包无需外部文件）。

ICONS        深灰 #475569 —— 白底按钮
ICONS_WHITE  纯白 #ffffff —— 彩色底按钮
ICONS_GREEN  绿   #0e9f6e —— 白底绿字按钮 / 标题闪电
ICONS_RED    红   #FF3B30 —— 白底红字按钮
"""

import tkinter as tk

from .icon_assets import ICONS, ICONS_GREEN, ICONS_RED, ICONS_WHITE


def icon_photo(name, color="gray"):
    """返回按钮图标 tk.PhotoImage（22x22）。

    name  : 图标名（start/stop/export/env/import/getip/write/bolt/github）
    color : gray=深灰(白底按钮) / white=纯白(彩色底按钮)
            green=绿(白底绿字/标题闪电) / red=红(白底红字)
    """
    pool = {"gray": ICONS, "white": ICONS_WHITE,
            "green": ICONS_GREEN, "red": ICONS_RED}[color]
    return tk.PhotoImage(data=pool[name])


def github_photo():
    """返回头部 GitHub 图标 tk.PhotoImage（Tabler brand-github，深灰 22x22）。"""
    return tk.PhotoImage(data=ICONS["github"])


def bolt_photo():
    """返回顶部标题闪电图标 tk.PhotoImage（主题绿 #0e9f6e，22x22）。"""
    return tk.PhotoImage(data=ICONS_GREEN["bolt"])
