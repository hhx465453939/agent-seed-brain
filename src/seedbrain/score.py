"""评分与排序 —— 「无偏」的实现位置。

四个机制叠加，各自解决一个问题：

| 机制 | 解决的问题 | 数学形式 |
|---|---|---|
| IDF 加权 | 低频但精确的信号被高频通用词淹没 | ``log(1 + N/(1+df))`` |
| 长度归一 | 文本长的种子靠「命中的 gram 多」占便宜 | ``raw / (1 + log1p(grams)/10)`` |
| 跨层配额 | 强层（条目多）把弱层挤成药渣 | 两阶段：先按层保底，再全局补满 |
| 时间衰减 | 同一任务反复命中同一条 | ``recovery × 次数惩罚`` |

**刻意不用随机数**：合适性由 IDF 决定（确定、可解释、可复现）；
多样性由状态记忆 + 时间衰减产生（同一任务隔几天再跑，会拿到不同的**同等合适**候选）。
"""

from __future__ import annotations

import math
import time

from .models import Match, Seed
from .profile import Profile
from .tokenize import grams, grams_cached, intersect_weights

# ── 时间衰减 ──────────────────────────────────────────────────────────────


def novelty(rec: dict | None, prof: Profile, now: float | None = None) -> float:
    """刚用过 → 下沉；久未用 → 回升；从未用 → 1.0。

    ``recovery = 1 - exp(-Δt/τ)``：τ=14 天时，0 天→0，14 天→0.63，30 天→0.88。
    下限 0.15 保证「用户就想复现上次结果」时仍能被选中（可复现性优先于去重）。
    """
    if not rec:
        return 1.0
    now = time.time() if now is None else now
    days = max(0.0, (now - float(rec.get("last_ts", 0))) / 86400.0)
    recovery = 1.0 - math.exp(-days / max(1e-9, prof.norms.decay_tau_days))
    count_pen = 1.0 / (1.0 + prof.norms.count_penalty * math.log1p(int(rec.get("count", 0))))
    # 下限作用在**最终值**上，而不是只作用在 recovery 上。
    # 早期版本写成 max(0.15, recovery) * count_pen，刚用过 1 次的种子会掉到 0.11
    # —— 用户想复现上次结果时它可能连 top-K 都进不去，与「可复现性优先」的设计相违。
    return max(0.15, recovery * count_pen)


# ── 单粒打分 ──────────────────────────────────────────────────────────────


def score_seed(
    seed: Seed,
    task_grams: dict[str, float],
    idf: dict[str, float] | None,
    prof: Profile,
) -> tuple[float, list[tuple[str, float]]]:
    """返回 ``(归一化得分, [(gram, 权重)…])``。

    ``idf=None`` 时退化为均匀权重 —— 这是验证套件「关掉 IDF」对照实验的入口。
    """
    sg = grams_cached(seed.text)
    hits = intersect_weights(sg, task_grams, idf, limit=prof.norms.max_hits)
    if not hits:
        return 0.0, []
    raw = sum(w for _, w in hits)
    # 温和归一：只压一点点长文本优势。用 sqrt 会把条目多的层整体压死，
    # 反而摧毁「平等摊开」——长文本信息量大，理应更容易相关。
    norm = raw / (1.0 + math.log1p(max(1, seed.grams)) / 10.0)
    return norm, hits


def build_idf(seeds: list[Seed]) -> dict[str, float]:
    from .tokenize import build_idf as _build
    return _build(s.text for s in seeds)


# ── 排序 + 跨层配额 ───────────────────────────────────────────────────────


def quotas_for(prof: Profile, k: int) -> dict[str, int]:
    """把 top-K 按 quota 分给各层；总和不超过 K（floor + 削峰）。"""
    q = {layer: max(1, math.floor(k * spec.quota)) for layer, spec in prof.layers.items()}
    while sum(q.values()) > k:
        biggest = max(q, key=lambda x: q[x])
        if q[biggest] <= 1:
            break
        q[biggest] -= 1
    return q


def rank(
    prof: Profile,
    seeds: list[Seed],
    task: str,
    k: int = 8,
    *,
    idf: dict[str, float] | None = None,
    state: dict | None = None,
    use_idf: bool = True,
) -> tuple[list[Match], dict[str, int], int]:
    """全库扫描 → 打分 → 跨层配额 → top-K。

    返回 ``(matches, quotas, 命中数)``。
    """
    idf = idf if idf is not None else build_idf(seeds)
    picks = (state or {}).get("picks", {})
    task_grams = grams(task)

    scored: list[tuple[float, Seed, list, float, float]] = []
    for s in seeds:
        base, hits = score_seed(s, task_grams, idf if use_idf else None, prof)
        if base <= 0:
            continue
        nv = novelty(picks.get(s.id), prof)
        scored.append((base * nv, s, hits, nv, base))
    scored.sort(key=lambda x: -x[0])

    quotas = quotas_for(prof, k)

    # 阶段 1：按层保底（层内最优）—— 配额是「下限」，不只是「上限」。
    # 旧实现只防「某层超配额」，却不保「某层有货却拿不到位」：按分数单次扫到底，
    # 弱层候选常排在 K 之外，等于配了白配。
    taken: list[tuple] = []
    idx_taken: set = set()
    for layer, q in quotas.items():
        picked = 0
        for i, row in enumerate(scored):
            if i in idx_taken or row[1].layer != layer:
                continue
            taken.append(row)
            idx_taken.add(i)
            picked += 1
            if picked >= q:
                break

    # 阶段 2：按全局分数补满 K（某层无候选时，配额让给有货的层）
    for i, row in enumerate(scored):
        if len(taken) >= k:
            break
        if i not in idx_taken:
            taken.append(row)
            idx_taken.add(i)

    taken.sort(key=lambda x: -x[0])
    matches = [
        Match(seed=s, total=t, base=b, novelty=nv, hits=tuple(hits))
        for t, s, hits, nv, b in taken[:k]
    ]
    return matches, quotas, len(scored)
