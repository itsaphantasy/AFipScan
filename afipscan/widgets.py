# -*- coding: utf-8 -*-
"""控件模块：悬停提示 Tooltip 与圆角按钮 RoundedButton。"""

import math
import tkinter as tk
import tkinter.font as tkfont

from .config import debug_log


def _rounded_rect(x0, y0, x1, y1, r):
    """生成圆角矩形顶点：每角用多段直线近似圆弧，四角对称稳定。"""
    r = max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    pts = []
    steps = 5  # 每个 90° 角用 5 段直线近似
    # 上边 + 右上角
    pts += [x0 + r, y0, x1 - r, y0]
    for i in range(steps + 1):
        a = math.pi * 0.5 * i / steps - math.pi / 2
        pts += [x1 - r + r * math.cos(a), y0 + r + r * math.sin(a)]
    # 右边 + 右下角
    pts += [x1, y0 + r, x1, y1 - r]
    for i in range(steps + 1):
        a = math.pi * 0.5 * i / steps
        pts += [x1 - r + r * math.cos(a), y1 - r + r * math.sin(a)]
    # 下边 + 左下角
    pts += [x1 - r, y1, x0 + r, y1]
    for i in range(steps + 1):
        a = math.pi * 0.5 * i / steps + math.pi / 2
        pts += [x0 + r + r * math.cos(a), y1 - r + r * math.sin(a)]
    # 左边 + 左上角
    pts += [x0, y1 - r, x0, y0 + r]
    for i in range(steps + 1):
        a = math.pi * 0.5 * i / steps + math.pi
        pts += [x0 + r + r * math.cos(a), y0 + r + r * math.sin(a)]
    return pts


class Tooltip:
    """悬停提示：延迟显示在控件下方，点击时自动隐藏。"""

    def __init__(self, widget, text, delay=500):
        self.widget, self.text, self.tip = widget, text, None
        self.delay = delay
        self.after_id = None
        # add="+" 追加绑定，避免覆盖控件自身的 Enter/Leave（如 RoundedButton 悬停反馈）
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, e=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.show)

    def show(self):
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        lab = tk.Label(self.tip, text=self.text, justify="left", bg="#2d2d2d", fg="#f5f5f7",
                       relief="solid", borderwidth=1, highlightthickness=1,
                       highlightbackground="#555555", font=("Microsoft YaHei UI", 9),
                       padx=6, pady=4)
        lab.pack()

    def hide(self, e=None):
        self.cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def cancel(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None


class RoundedButton(tk.Canvas):
    """圆角按钮：圆角矩形 + 悬停变色 + 按下加深 + 禁用置灰。

    支持 style: default(白底灰边) / accent(绿) / danger(红) / success(成功绿)
    兼容旧调用: config(text=..., style="Accent.TButton", state="disabled")
    立体感：正常/悬停时右下带投影(凸出)，按下时投影消失(按下去)。
    """

    _STYLES = {
        "default": dict(bg="#ffffff", fg="#1f2937", border="#d1d5db",
                        hover="#f3f4f6", press="#e5e7eb",
                        dis_bg="#f1f2f4", dis_fg="#9ca3af"),
        "accent":  dict(bg="#0e9f6e", fg="#ffffff", border="",
                        hover="#0b8058", press="#0a6f4d",
                        dis_bg="#a7d8c4", dis_fg="#f0fdf9"),
        "danger":  dict(bg="#FF3B30", fg="#ffffff", border="",
                        hover="#e02e24", press="#c92c22",
                        dis_bg="#f1b6b8", dis_fg="#ffffff"),
        "success": dict(bg="#34C759", fg="#ffffff", border="",
                        hover="#2db84f", press="#28a648",
                        dis_bg="#9ce6b2", dis_fg="#f0fdf9"),
        "accent_light": dict(bg="#ffffff", fg="#0e9f6e", border="#d1d5db",
                             hover="#e8f5ef", press="#d1fae5",
                             dis_bg="#f1f2f4", dis_fg="#a7d8c4"),
        "danger_light": dict(bg="#ffffff", fg="#FF3B30", border="#d1d5db",
                             hover="#fdecec", press="#f9d5d3",
                             dis_bg="#f1f2f4", dis_fg="#f1b6b8"),
    }

    _PAD_X = 20  # 图标/文字与按钮圆角框的左右安全间距(px)

    def __init__(self, master, text="", command=None, style="default",
                 width=120, height=38, font=None, tooltip=None,
                 canvas_bg=None, state="normal",
                 image=None, image_on_color=None, image_light=None,
                 autofit=False, outline=1):
        # autofit=True：内容(图标+文字)太宽时自动撑大按钮，防止超出圆角框
        self._autofit = autofit
        self._outline = outline  # 边框粗细(px)，默认 1；弹窗等场景可传 2 让边框更明显
        bg = canvas_bg or "#ffffff"
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, bg=bg, cursor="hand2")
        self._cfg_w, self._cfg_h = width, height
        self._canvas_bg = bg
        self.command = command
        self.style_name = style
        self.text = text
        self.state = state
        self._hover = False
        self._pressed = False
        self._font = font or ("Microsoft YaHei UI", 12, "bold")
        self._shape = None
        self._label = None
        self._icon = None
        self._font_obj = None
        # 图标：image=白底按钮(深灰图标)，image_on_color=彩色按钮(白色图标)
        self._image = image
        self._image_on_color = image_on_color
        # image_light=白底彩色文字按钮(绿/红图标)
        self._image_light = image_light
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())
        if tooltip:
            Tooltip(self, tooltip)
        self._draw()

    # ---- 兼容 ttk.Button 的 config 调用 ----
    def config(self, **kw):
        if "text" in kw:
            self.text = kw.pop("text")
        if "style" in kw:
            s = str(kw.pop("style")).replace(".TButton", "").lower()
            self.style_name = s if s in self._STYLES else "default"
        if "state" in kw:
            self.state = kw.pop("state")
        if kw:
            super().config(**kw)
        self._draw()

    def set_state(self, state):
        self.state = state
        self._draw()

    def set_text(self, text, style=None):
        self.text = text
        if style:
            self.style_name = style
        self._draw()

    def set_content(self, text, style=None, image=None, image_on_color=None,
                    image_light=None):
        """一键切换按钮的文字/样式/图标（用于开始<->停止 切换按钮）。"""
        self.text = text
        if style:
            self.style_name = style
        # 直接赋值：传 None 表示清除该图标（"停止"状态只留红字）
        self._image = image
        self._image_on_color = image_on_color
        self._image_light = image_light
        self._draw()

    # ---- 交互反馈 ----
    def _on_enter(self, e=None):
        debug_log("RB enter: %s" % self.text)
        self._hover = True
        self._draw()

    def _on_leave(self, e=None):
        debug_log("RB leave: %s" % self.text)
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, e=None):
        if self.state == "disabled":
            return
        self._pressed = True
        self._draw()

    def _on_release(self, e=None):
        if self.state == "disabled":
            return
        was = self._pressed
        self._pressed = False
        self._draw()
        if was and self.command:
            try:
                self.command()
            except Exception:
                pass

    def _colors(self):
        st = self._STYLES.get(self.style_name, self._STYLES["default"])
        if self.state == "disabled":
            return dict(bg=st["dis_bg"], fg=st["dis_fg"], border="")
        if self._pressed:
            return dict(bg=st["press"], fg=st["fg"], border=st["border"])
        if self._hover:
            return dict(bg=st["hover"], fg=st["fg"], border=st["border"])
        return dict(bg=st["bg"], fg=st["fg"], border=st["border"])

    def _shadow_color(self):
        """投影颜色：悬停时略深，让按钮更"浮起来"。"""
        return "#b9c0c8" if self._hover else "#cdd3d9"

    def _font_measure(self, text):
        """测量文字宽度(px)，用于图标+文字整体居中。"""
        if self._font_obj is None:
            self._font_obj = tkfont.Font(font=self._font)
        return self._font_obj.measure(text)

    def _current_image(self):
        """按当前样式选择图标：彩色按钮用白色图标，白底按钮用深灰图标。"""
        if self.style_name in ("accent_light", "danger_light"):
            return self._image_light or self._image_on_color or self._image
        if self.style_name in ("accent", "danger", "success"):
            return self._image_on_color or self._image
        return self._image

    @staticmethod
    def _rrect(x0, y0, x1, y1, r):
        return _rounded_rect(x0, y0, x1, y1, r)

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self._cfg_w, self._cfg_h
        c = self._colors()
        r = 8  # 统一圆角 8px（Tabler 圆润风格）
        if self._pressed or self.state == "disabled":
            # 按下/禁用：无投影，按钮平贴
            pts = self._rrect(0, 0, w, h, r)
            self._shape = self.create_polygon(pts, smooth=False,
                                              fill=c["bg"],
                                              outline=c["border"] or c["bg"],
                                              width=self._outline)
            cx, cy, dy = w // 2, h // 2, 1
        else:
            # 正常/悬停：右下偏移投影 + 主体，形成凸出感
            shx, shy = 2, 3
            pts = self._rrect(shx, shy, w, h, r)
            self._shadow = self.create_polygon(pts, smooth=False,
                                               fill=self._shadow_color(), outline="")
            pts = self._rrect(0, 0, w - shx, h - shy, r)
            self._shape = self.create_polygon(pts, smooth=False,
                                              fill=c["bg"],
                                              outline=c["border"] or c["bg"],
                                              width=self._outline)
            cx, cy, dy = (w - shx) // 2, (h - shy) // 2, 0
        # 图标+文字整体居中；按下时向下偏移1px模拟按压
        img = self._current_image()
        gap = 6
        if img is not None and self.text:
            iw = img.width()
            tw = self._font_measure(self.text)
            content_w = iw + gap + tw
        elif img is not None:
            iw = img.width()
            content_w = iw
        else:
            content_w = self._font_measure(self.text)
        # 自适应宽度：内容太宽时自动撑大按钮，防止图标/文字超出圆角框
        if self._autofit:
            need = content_w + self._PAD_X * 2 + 3
            if need > w:
                self._cfg_w = need
                self.configure(width=need)
                return
        if img is not None and self.text:
            ix = cx - content_w // 2
            self._icon = self.create_image(ix + iw // 2, cy + dy, image=img)
            self._label = self.create_text(ix + iw + gap, cy + dy,
                                           text=self.text, fill=c["fg"],
                                           font=self._font, justify="left",
                                           anchor="w")
        elif img is not None:
            self._icon = self.create_image(cx, cy + dy, image=img)
        else:
            self._label = self.create_text(cx, cy + dy,
                                           text=self.text, fill=c["fg"],
                                           font=self._font, justify="center")


class RoundedEntry(tk.Canvas):
    """圆角输入框：Canvas 画圆角矩形底 + 内嵌 tk.Entry，聚焦边框变绿。

    用法与 ttk.Entry 类似：RoundedEntry(master, textvariable=var, width=8, show="*")
    对外暴露 .entry（真正的输入控件），Tooltip/事件绑定请用 .entry。
    """

    RADIUS = 6          # 圆角半径
    PADX = 10           # 左右内边距
    ENTRY_HEIGHT = 44   # 统一输入框高度(比原45px小1px)

    def __init__(self, master, textvariable=None, width=10, show=None,
                 font=None, canvas_bg="#ffffff"):
        font = font or ("Microsoft YaHei UI", 12)
        self._font = font
        self._focused = False
        super().__init__(master, width=1, height=1,
                         highlightthickness=0, bd=0, bg=canvas_bg, cursor="xterm")
        self.entry = tk.Entry(self, textvariable=textvariable, show=show,
                              font=font, bd=0, relief="flat", bg="#ffffff",
                              fg="#1f2937", insertbackground="#1f2937",
                              highlightthickness=0, width=width)
        # 宽度按内容自适应，高度固定统一（不受字体影响）
        ew = self.entry.winfo_reqwidth()
        eh = self.entry.winfo_reqheight()
        self._cfg_w = ew + self.PADX * 2 + 2
        self._cfg_h = self.ENTRY_HEIGHT
        self.configure(width=self._cfg_w, height=self._cfg_h)
        py = max(4, (self._cfg_h - eh) // 2)  # 内嵌输入框垂直居中
        self._entry_win = self.create_window(self.PADX + 1, py + 1,
                                             window=self.entry, anchor="nw")
        self._draw()
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: self._set_focus(True))
        self.entry.bind("<FocusOut>", lambda e: self._set_focus(False))

    def _set_focus(self, on):
        self._focused = on
        self._draw()

    def _draw(self):
        self.delete("rounded_bg")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self._cfg_w, self._cfg_h
        border = "#0e9f6e" if self._focused else "#d1d5db"
        pts = _rounded_rect(1, 1, w - 1, h - 1, self.RADIUS)
        self.create_polygon(pts, smooth=False, fill="#ffffff",
                            outline=border, tags="rounded_bg")
        self.tag_raise(self._entry_win)
