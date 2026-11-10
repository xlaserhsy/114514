# -*- coding: utf-8 -*-
"""
ui.py —— Windows 10 微软拼音风格的输入界面（tkinter 实现）。
包含三个部分：
  1. 编辑区（模拟目标应用文本框，带光标）
  2. 内联组合显示（拼音编码跟随文字流显示，类似 Win10 行内候选）
  3. 候选词窗口 + 语言栏（中/英 模式指示，点击或 Shift 切换）
外观尽量贴近 Win10：浅色卡片、蓝色高亮首选、Segoe/雅黑字体、细边框阴影。
"""
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import InputState  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DICT_PATH = os.path.normpath(os.path.join(DATA_DIR, "dict.json"))

# ---- Win10 配色 ----
ACCENT = "#0078D7"          # 任务栏蓝
ACCENT_LIGHT = "#E5F1FB"    # 候选选中底色
CARD_BG = "#F9F9F9"
CARD_BORDER = "#CCCCCC"
TEXT_MAIN = "#1F1F1F"
TEXT_GRAY = "#5F5F5F"


class CandidateWindow:
    """独立无边框候选窗口，跟随编辑区光标位置。"""

    def __init__(self, master, app):
        self.app = app
        self.top = tk.Toplevel(master)
        self.top.overrideredirect(True)      # 无系统边框，自绘
        self.top.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.top, highlightthickness=0, bg=CARD_BG)
        self.canvas.pack()
        self._h = 46
        self.top.withdraw()

    def show(self, x, y, enc, items, mode_cn):
        self.top.deiconify()
        self.top.geometry(f"+{int(x)}+{int(y)}")
        c = self.canvas
        c.delete("all")
        row_h = 26
        w = max(240, min(560, 90 + sum(len(t) * 15 for _, t in items)))
        h = row_h * 2
        c.config(width=w, height=h, bg="white",
                 highlightbackground=CARD_BORDER, highlightcolor=CARD_BORDER,
                 highlightthickness=1)
        # 顶行：拼音编码
        c.create_rectangle(0, 0, w, row_h, fill="white", outline="")
        if enc:
            c.create_text(10, row_h / 2, anchor="w", text=enc,
                          font=self.app.font_enc, fill=ACCENT)
        # 分隔线
        c.create_line(0, row_h, w, row_h, fill="#EDEDED")
        # 底行：候选词
        c.create_rectangle(0, row_h, w, h, fill="white", outline="")
        xoff = 6
        for i, (num, word) in enumerate(items):
            label = f"{num}.{word}"
            tw = self.app.font_cand.measure(label) + 16
            if i == 0:
                c.create_rectangle(xoff - 2, row_h + 2, xoff + tw - 2, h - 2,
                                   fill=ACCENT_LIGHT, outline="")
            c.create_text(xoff + 8, row_h + row_h / 2, anchor="w", text=label,
                          font=self.app.font_cand, fill=TEXT_MAIN)
            xoff += tw
        # 翻页提示
        more = "…" if len(self.app.state.candidates) > self.app.state.page_size \
            * (self.app.state.page + 1) else ""
        if more:
            c.create_text(w - 10, row_h + row_h / 2, anchor="e", text=more,
                          font=self.app.font_cand, fill=TEXT_GRAY)

    def hide(self):
        self.top.withdraw()


class LanguageBar:
    """右下角语言栏样式的模式指示器：中 / 英 图标按钮。"""

    def __init__(self, master, app):
        self.app = app
        self.frame = tk.Frame(master, bg="#F3F3F3", highlightthickness=1,
                              highlightbackground="#D5D5D5")
        self.btn = tk.Label(self.frame, text="中", width=3, cursor="hand2",
                            font=("Microsoft YaHei UI", 11, "bold"),
                            fg=ACCENT, bg="#F3F3F3")
        self.btn.pack(side="left", padx=4, pady=2)
        self.btn.bind("<Button-1>", lambda e: app.toggle_mode())
        self.hint = tk.Label(self.frame, text="Shift 切换中英文",
                             font=("Microsoft YaHei UI", 8),
                             fg=TEXT_GRAY, bg="#F3F3F3")
        self.hint.pack(side="left", padx=(0, 6))

    def update(self, mode_cn):
        self.btn.config(text="中" if mode_cn else "英",
                        fg=ACCENT if mode_cn else TEXT_GRAY)


class IMApp:
    def __init__(self, root):
        self.root = root
        root.title("Win10 风格拼音输入法（演示宿主）")
        root.geometry("760x520+120+80")
        root.configure(bg="white")

        base_font = ("Microsoft YaHei UI", 12)
        try:
            tkfont.nametofont("TkDefaultFont").configure(family="Microsoft YaHei UI", size=10)
        except Exception:
            pass
        self.font_enc = ("Microsoft YaHei UI", 11)
        self.font_cand = ("Microsoft YaHei UI", 13)

        # 状态机
        self.state = InputState(DICT_PATH)
        self.state.on_update = self.refresh

        # 顶部标题条（仿 Win10 白底黑字）
        header = tk.Frame(root, bg="white")
        header.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(header, text="Windows 10 风格输入法 Demo",
                 font=("Microsoft YaHei UI", 14, "bold"),
                 bg="white", fg=TEXT_MAIN).pack(side="left")
        self.langbar_frame = tk.Frame(header, bg="white")
        self.langbar_frame.pack(side="right")
        self.langbar = LanguageBar(self.langbar_frame, self)
        self.langbar.frame.pack()

        tip = tk.Label(root, text="在此输入：中文模式下打拼音（如 nihao），空格选首词，"
                                  "1-5 按序号选词，- / = 翻页，Esc 退出，Shift 切换中英文",
                       font=("Microsoft YaHei UI", 9), bg="white", fg=TEXT_GRAY,
                       anchor="w")
        tip.pack(fill="x", padx=16)

        # 编辑区：用 Text 模拟目标文档
        wrap = tk.Frame(root, bg="white")
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.editor = tk.Text(wrap, font=base_font, wrap="word", undo=True,
                              bg="white", fg=TEXT_MAIN, insertbackground=ACCENT,
                              relief="solid", bd=1, highlightthickness=1,
                              highlightbackground="#C8C8C8", padx=10, pady=8)
        self.editor.pack(fill="both", expand=True)

        # 内联组合显示（在文本流尾部画一个下划线拼音）
        self.inline_tag = "composing"
        self.editor.tag_configure(self.inline_tag, underline=True, foreground=ACCENT)

        # 候选窗口
        self.cand_win = CandidateWindow(root, self)

        # 键盘事件
        root.bind_all("<KeyPress>", self.on_keypress)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._composing_marker_len = 0   # 编辑器里临时显示的拼音长度
        self.refresh()

    # ---------- 按键分发 ----------
    def on_keypress(self, ev):
        keysym, ch = ev.keysym, ev.char
        st = self.state

        # Shift 松开且期间没有其它按键 -> 视为"单击 Shift"，切换中英文
        if keysym in ("Shift_L", "Shift_R"):
            self._shift_down = True
            return
        if keysym == "Shift-L":          # tkinter 在部分平台上用大写名表示按下
            self._shift_down = True
            return
        if keysym.endswith("Release") and "Shift" in keysym:
            if getattr(self, "_shift_down", False) and \
                    not getattr(self, "_other_key_since_shift", False):
                self.toggle_mode()
            self._shift_down = False
            self._other_key_since_shift = False
            return
        if keysym == "Release":
            return
        # 记录 shift 按住期间是否按了其它键（避免与 Caps/大小写输入冲突）
        if getattr(self, "_shift_down", False):
            self._other_key_since_shift = True

        # Ctrl/Alt 组合键放行给编辑器
        if ev.state & 0x0004 or ev.state & 0x0008:  # ctrl / alt
            return

        key = None
        if keysym == "space":
            key = "space"
        elif keysym == "Return":
            key = "enter"
        elif keysym == "Escape":
            key = "esc"
        elif keysym == "BackSpace":
            key = "backspace"
        elif keysym in ("minus", "underscore"):
            key = "minus"
        elif keysym in ("equal", "plus"):
            key = "equal"
        elif keysym in ("Page_Up",):
            key = "pageup"
        elif keysym in ("Page_Down",):
            key = "pagedown"
        elif keysym.startswith("KP_") and keysym[3:].isdigit():
            key = "digit" + keysym[3:]
        elif len(ch) == 1 and ch.isdigit():
            key = "digit" + ch
        elif len(ch) == 1 and ch.isalpha():
            key = ch.lower()
        elif len(ch) == 1:
            key = ch
        if key is None:
            return

        out = st.on_key(key)
        if out == "<<BACKSPACE>>":
            self._delete_char()
        elif out is not None:
            self._insert_text(out)
        ev.widget.after_idle(self._sync_inline)

    def toggle_mode(self):
        out = self.state.toggle_mode()
        if out:
            self._insert_text(out)
        self.refresh()

    # ---------- 编辑器操作 ----------
    def _insert_text(self, s):
        self.editor.insert("insert", s)
        self.editor.see("insert")

    def _delete_char(self):
        if self.editor.compare("insert > 1.0", "true"):
            self.editor.delete("insert-1c", "insert")

    # ---------- 刷新 ----------
    def refresh(self):
        self.langbar.update(self.state.mode == InputState.CHINESE)
        self.root.after_idle(self._sync_inline)

    def _sync_inline(self):
        """把当前拼音编码以内联下划线方式显示在光标处，并定位候选窗。"""
        # 移除旧的 inline 标记内容
        if self._composing_marker_len:
            self.editor.delete(f"insert-{self._composing_marker_len}c", "insert")
            self._composing_marker_len = 0
        enc, items = self.state.display_info()
        if self.state.composing and items:
            # 在光标处插入灰色下划线拼音作为内联显示
            marker = enc
            self.editor.insert("insert", marker)
            self.editor.tag_add(self.inline_tag, f"insert-{len(marker)}c", "insert")
            self._composing_marker_len = len(marker)
            # 候选窗定位到光标下方
            try:
                bbox = self.editor.bbox("insert")
            except tk.TclError:
                bbox = None
            if bbox:
                gx = self.editor.winfo_rootx() + bbox[0]
                gy = self.editor.winfo_rooty() + bbox[3] + 4
                self.cand_win.show(gx, gy, "", items,
                                   self.state.mode == InputState.CHINESE)
            self.cand_win.top.lift()
        else:
            self.cand_win.hide()

    def on_close(self):
        self.state.save_dict()
        self.root.destroy()


def main():
    root = tk.Tk()
    IMApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
