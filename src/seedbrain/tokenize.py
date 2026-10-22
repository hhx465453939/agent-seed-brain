"""分词与 IDF —— 整个 SDK 的匹配底座。

为什么不分词：中文没有词边界，引入分词器就引入第三方依赖（违反 C2），
且分词结果随词典版本漂移（违反 NFR-3 可复现）。2~3 字 n-gram 是零依赖下
信噪比最好的折中：

  * 2-gram 全权重：``夜景`` 能命中「雨夜夜景」「城市夜景」
  * 3-gram 降权到 0.35：中文 3 字常跨词边界（「信息密度」→「息密」），
    只作为确认信号，不作为主证据

IDF 让稀有信号获得应有权重 —— 这是「无偏」的数学实现，不是随机。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'\-\+\.]{2,}")

#: 任何领域都没有区分度、或会制造假命中的词。
#: 注意 ``ai``：任务里的「AI」指人工智能，而源库里的 ``AI:`` 是提示词前缀。
STOP = frozenset({
    "the", "and", "with", "for", "style", "art", "of", "in", "to", "an", "as",
    "is", "by", "on", "from", "that", "this", "ai", "www", "http", "https",
    "使用", "以及", "一个", "可以", "需要", "任务", "问题", "方法", "工具",
    "风格", "艺术", "作品", "进行", "通过", "如果", "因为", "所以", "我们",
})

W2 = 1.0
W3 = 0.35

_CACHE: dict[str, dict[str, float]] = {}
_MAX_CACHE = 20000


def grams(text: str, w2: float = W2, w3: float = W3) -> dict[str, float]:
    """文本 → ``{gram: 权重}``。同一 gram 取最大权重（2-gram 优先于 3-gram）。"""
    out: dict[str, float] = {}
    for run in CJK_RUN.findall(text):
        n = len(run)
        for i in range(n - 1):
            g = run[i:i + 2]
            if g not in STOP and out.get(g, 0.0) < w2:
                out[g] = w2
        for i in range(n - 2):
            g = run[i:i + 3]
            if g not in STOP and out.get(g, 0.0) < w3:
                out[g] = w3
    for w in ASCII_WORD.findall(text):
        lw = w.lower()
        if lw not in STOP and out.get(lw, 0.0) < w2:
            out[lw] = w2
    return out


def grams_cached(text: str) -> dict[str, float]:
    """带缓存的 :func:`grams`。

    验证套件会对同一批种子反复扫描（对照实验要跑 2N 次），
    没有这层缓存，一次完整验证要 30 秒以上。
    """
    hit = _CACHE.get(text)
    if hit is None:
        if len(_CACHE) > _MAX_CACHE:
            _CACHE.clear()
        hit = _CACHE[text] = grams(text)
    return hit


def clear_cache() -> None:
    """清空缓存（测试用：避免跨用例污染）。"""
    _CACHE.clear()


def build_idf(texts: Iterable[str]) -> dict[str, float]:
    """按语料计算 IDF：``log(1 + N / (1 + df))``。

    +1 平滑保证即使某 gram 出现在全部文档里也有正权重；
    稀有 gram（df=1）约得 ``log(1+N)``，常见 gram 约得 1 量级，
    二者 3~5 倍差距正是「让低频但精确的信号浮上来」的原因。
    """
    df: Counter = Counter()
    n = 0
    for t in texts:
        n += 1
        df.update(grams_cached(t).keys())
    n = max(1, n)
    return {g: math.log(1 + n / (1 + c)) for g, c in df.items()}


def intersect_weights(
    left: dict[str, float],
    right: dict[str, float],
    idf: dict[str, float] | None = None,
    limit: int = 5,
) -> list[tuple[str, float]]:
    """两个 gram 字典的交集 → 按权重降序的 ``[(gram, 权重)]``。

    ``idf=None`` 时退化为均匀权重（供验证套件的「关掉 IDF」对照实验使用）。
    """
    common = set(left) & set(right)
    if not common:
        return []
    weighted = [
        (g, (idf.get(g, 1.0) if idf else 1.0) * min(left[g], right[g]))
        for g in common
    ]
    weighted.sort(key=lambda x: -x[1])
    return weighted[:limit]


def dedupe_hits(hits: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """展示层去冗余：短 gram 若被同批命中的长 gram 包含则隐去。

    「条件数」命中时会把「件数」隐去 —— 计分不变，只是人看起来更干净。
    """
    pool = {g for g, _ in hits}
    return [(g, w) for g, w in hits if not any(g != h and g in h for h in pool)]
