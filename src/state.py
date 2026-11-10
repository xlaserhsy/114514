# -*- coding: utf-8 -*-
"""
状态机：管理 中/英 模式、拼音编码缓冲、候选列表、连续选词。
与 UI 无关，便于单元测试。
"""
from engine import PinyinEngine


class InputState:
    CHINESE = "ch"
    ENGLISH = "en"

    def __init__(self, dict_path):
        self.engine = PinyinEngine(dict_path)
        self.mode = self.CHINESE          # 当前中英文模式
        self.composing = ""               # 拼音字母缓冲（用户已输入的原始字母）
        self.candidates = []              # [(word, full)]
        self.consumed = ""                # candidates 对应消费的拼音前缀
        self.page = 0                     # 翻页偏移
        self.page_size = 5
        self._dict_path = dict_path

    # ---------- 模式切换 ----------
    def toggle_mode(self):
        """Shift 键行为：切换中英文（微软拼音习惯）。
        若正在输入拼音，切到英文时把字母原样上屏；切回中文不受影响。"""
        if self.mode == self.CHINESE and self.composing:
            out = self.composing
            self._clear_composition()
            self.mode = self.ENGLISH
            self._emit()
            return out
        self.mode = self.ENGLISH if self.mode == self.CHINESE else self.CHINESE
        self._emit()
        return None

    def _clear_composition(self):
        self.composing = ""
        self.candidates = []
        self.consumed = ""
        self.page = 0

    # ---------- 候选窗口展示信息（UI 使用） ----------
    def display_info(self):
        """返回 (编码显示串, 当前页候选[(序号,词)])。
        Win10 微软拼音风格：
        - 若首选候选是词语，显示其对应拼音 + 剩余未消费字母；
        - 否则仅显示剩余未消费的原始字母。"""
        rest = self.composing[len(self.consumed):]
        enc = ""
        if self.consumed and self.candidates:
            w0, _ = self.candidates[0]
            if len(w0) > 1:                      # 词语：展示已匹配拼音
                segs = self.engine.segment(self.consumed) or []
                enc = " ".join(segs)
                if rest:
                    enc += " " + rest
            else:
                enc = rest if rest else self.composing
        else:
            enc = self.composing
        lst = self._page_list()
        items = [(i + 1, w) for i, (w, _f) in enumerate(lst)]
        return enc, items

    # ---------- 按键入口，返回需要"上屏"的文本（无则 None） ----------
    def on_key(self, key, text=None):
        """key: 'a'..'z' 字母 / 'space' / 'enter' / 'esc' / 'backspace' /
        'digit1'..'digit5' / 'minus' / 'equal' / 'pageup' / 'pagedown'
        text: 非字母输入(如中文模式下的标点、粘贴)，直接透传上屏。"""
        if self.mode == self.ENGLISH:
            return self._on_key_en(key, text)
        return self._on_key_ch(key, text)

    # ---------- 英文模式 ----------
    def _on_key_en(self, key, text):
        if text is not None and key == "text":
            return text
        if len(key) == 1:          # 字母、数字、标点原样上屏
            return key
        if key in ("space", "enter"):
            return key
        return None                # backspace/esc 等由 UI 直接处理

    # ---------- 中文模式 ----------
    def _on_key_ch(self, key, text):
        if text is not None and key == "text":
            if self.composing:
                self._commit_learning()
            return text

        if key == "backspace":
            if self.composing:
                self.composing = self.composing[:-1]
                self._refresh()
                return None
            return "<<BACKSPACE>>"   # 通知 UI 删除目标文档中的一个字符

        if key == "esc":
            out = self.composing if self.composing else None
            self._clear_composition()
            self._emit()
            return out

        if key == "enter":
            if self.composing:
                out = self.composing      # 回车直出字母
                self._clear_composition()
                self._emit()
                return out
            return None

        if key == "space":
            if self.candidates:
                w = self._page_list()[0][0]
                return self._pick(w)
            return " "             # 无候选时正常输出空格

        if key.startswith("digit"):
            idx = int(key[-1]) - 1
            lst = self._page_list()
            if 0 <= idx < len(lst):
                return self._pick(lst[idx][0])
            return key             # 无对应候选则直出数字

        if key in ("minus", "pageup"):
            if self.page > 0 and self.candidates:
                self.page -= 1
                self._emit()
                return None
            return "-" if key == "minus" else None
        if key in ("equal", "pagedown"):
            total_pages = (len(self.candidates) + self.page_size - 1) // self.page_size
            if self.candidates and self.page + 1 < total_pages:
                self.page += 1
                self._emit()
                return None
            return "=" if key == "equal" else None

        if len(key) == 1 and key.isalpha():
            self.composing += key.lower()
            self._refresh()
            return None

        if len(key) == 1:          # 中文模式下的标点/数字直接上屏（全角转换由 UI 处理）
            return key
        return None

    # ---------- 选词 / 连续选词 ----------
    def _pick(self, word):
        consumed = self.consumed or self.composing
        rest = self.composing[len(consumed):]
        self.engine.learn(consumed, word)
        self.engine.save_user_dict(self._dict_path)   # 即时持久化学习结果
        self.composing = rest
        self._refresh()
        return word

    def _commit_learning(self):
        pass

    # ---------- 候选刷新 ----------
    def _refresh(self):
        if not self.composing:
            self.candidates = []
            self.consumed = ""
            self.page = 0
        else:
            cands, consumed = self.engine.candidates(self.composing, max_n=25)
            self.candidates = cands
            self.consumed = consumed
            self.page = 0
        self._emit()

    def _page_list(self):
        s = self.page * self.page_size
        return self.candidates[s:s + self.page_size]

    # ---------- UI 回调钩子 ----------
    on_update = None

    def _emit(self):
        if self.on_update:
            self.on_update()

    def save_dict(self):
        self.engine.save_user_dict(self._dict_path)
