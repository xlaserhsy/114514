# -*- coding: utf-8 -*-
"""
pinyin_engine.py —— 拼音输入核心引擎（Windows 10 微软拼音风格模拟）
负责：拼音切分、前缀匹配候选词、用户词频学习。
纯 Python 实现，无任何第三方依赖。
"""
import json
import os
import re


class PinyinEngine:
    def __init__(self, dict_path):
        self.single = {}          # 拼音 -> [单字(按频率排序)]
        self.phrases = {}         # 拼音串(用'连接) -> [词语]
        self.user_freq = {}       # (pinyin, word) -> 用户选择次数
        self._all_py = set()
        self.load(dict_path)

    # ---------- 词典加载 ----------
    def load(self, path):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for py, chars in data.get("single", {}).items():
            self.single[py] = list(chars)
        for py, words in data.get("phrases", {}).items():
            self.phrases[py] = list(words)
        self.user_freq = {tuple(k.split("\x01")): v
                          for k, v in data.get("user", {}).items()}
        self._rebuild_index()

    def _rebuild_index(self):
        self._all_py = set(self.single) | set(self.phrases)
        # 预排序短语键，供最长前缀匹配
        self._phrase_keys = sorted(self.phrases.keys(), key=len, reverse=True)

    # ---------- 用户词频保存 ----------
    def save_user_dict(self, path):
        out = {
            "single": self.single,
            "phrases": self.phrases,
            "user": {f"{k[0]}\x01{k[1]}": v for k, v in self.user_freq.items()},
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        os.replace(tmp, path)

    # ---------- 拼音切分（音节贪心 + 回溯） ----------
    _SYL_MAX = 6

    def _is_syllable(self, s):
        return s in self.single

    def segment(self, text):
        """把 'nihao' 切成 ['ni','hao']；切不开时返回 None。"""
        n = len(text)
        memo = {}

        def dfs(i):
            if i == n:
                return []
            if i in memo:
                return memo[i]
            best = None
            for ln in range(min(self._SYL_MAX, n - i), 0, -1):
                syl = text[i:i + ln]
                if self._is_syllable(syl):
                    rest = dfs(i + ln)
                    if rest is not None:
                        cand = [syl] + rest
                        if best is None or len(cand) < len(best):
                            best = cand
            memo[i] = best
            return best

        return dfs(0)

    # ---------- 候选生成 ----------
    def candidates(self, pinyin, max_n=5):
        """返回 (候选列表, 已消费拼音串)。
        候选列表 = [(显示文本, 是否完整匹配)]，模拟 Win10 微软拼音：
        优先输出能"吃掉"最长拼音前缀的词语，剩余拼音继续留作编码。"""
        if not pinyin:
            return [], ""
        segs = self.segment(pinyin)
        result = []          # (word, full, consumed_len)
        seen = set()

        def add(word, full, consumed):
            if word and word not in seen:
                seen.add(word)
                result.append((word, full, consumed))

        if segs:
            # 1) 从最长前缀开始找词语（贪心覆盖）
            for k in range(len(segs), 0, -1):
                pre = ".".join(segs[:k])
                cons = len("".join(segs[:k]))
                words = self.phrases.get(pre, [])
                if words:
                    for w in words:
                        add(w, k == len(segs), cons)
                    break
            # 2) 若词库只覆盖了部分拼音，把剩余拼音的首音节单字也放进来
            covered = result[0][2] if result else 0
            rest_segs = []
            acc = 0
            for s in segs:
                if acc >= covered:
                    rest_segs.append(s)
                acc += len(s)
            if rest_segs:
                for ch in self.single.get(rest_segs[0], [])[:8]:
                    add(ch, False, covered + len(rest_segs[0]))
            # 3) 末音节单字（整段可切时）
            if covered == len(pinyin):
                for ch in self.single.get(segs[-1], [])[:40]:
                    add(ch, True, len(pinyin))
        # 4) 按整个输入串的前缀找单字（处理不可完全切分的情况）
        if not result or result[0][2] < len(pinyin):
            for ch in self._prefix_chars(pinyin)[:30]:
                add(ch, False, len(pinyin))
        # 5) 原始字母兜底（英文直输）：仅当整串无法被拼音覆盖时才作为候选
        if not segs or (result and result[0][2] < len(pinyin)):
            add(pinyin, True, len(pinyin))

        # 排序：用户高频优先 > 完整匹配 > 覆盖拼音更长 > 生成顺序
        scored = []
        for idx, (w, full, cons) in enumerate(result):
            u = self.user_freq.get((pinyin, w), 0)
            scored.append((-u, 0 if full else 1, -cons, idx, w, full, cons))
        scored.sort()
        consumed_pinyin = pinyin[:scored[0][6]] if scored else ""
        out = [(item[4], item[5]) for item in scored[:max_n]]
        return out, consumed_pinyin

    def _prefix_chars(self, pinyin):
        """返回所有音节以 pinyin 为前缀的单字，音节更长的排前面。"""
        hits = [py for py in self.single if py.startswith(pinyin)]
        hits.sort(key=len, reverse=True)
        chars = []
        for py in hits:
            chars.extend(self.single[py][:3])
        return chars

    # ---------- 上屏学习 ----------
    def learn(self, pinyin, word):
        self.user_freq[(pinyin, word)] = self.user_freq.get((pinyin, word), 0) + 1
