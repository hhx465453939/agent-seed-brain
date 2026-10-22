"""验证套件 —— 把「无偏」变成可证伪的断言。

设计原则（源自上游 38 项断言的血泪）：

* **断言必须能失败**。曾经有一条「旧货架样本有效性」检查，因为引用了三个不存在的 id，
  导致下游的「去中心化」断言恒真（永远 PASS）。测试自己也要被测。
* **不写影子实现**。所有断言调用真实 API（``rank`` / ``merge_seeds`` / ``find_duplicate``），
  不复制算法。曾经在测试里重算了一遍配额公式，结果与实现不一致，报出假失败。
* **确定性**。切分用 ``hashlib.md5``，绝不用内置 ``hash()``（它带随机种子）。

三组断言：

| 组 | 何时跑 | 内容 |
|---|---|---|
| ``schema`` | 永远 | profile 自身合法性 |
| ``core`` | 永远 | 可达性 / 集中度 / IDF / 轮转 / 均衡 / 鲁棒 / 确定性 / 去中心化 / 增量 |
| ``content`` | profile 声明了 ``verify.content`` 时 | 目录计数 / 字段齐全 / 文档声明 |
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import Counter
from collections.abc import Sequence

from .additions import find_duplicate, merge_seeds
from .index import build as build_index
from .models import Check, Seed, VerifyReport
from .profile import Profile
from .score import build_idf, rank
from .tokenize import grams, grams_cached

#: 默认门槛。profile 的 ``verify.thresholds`` 可覆盖任意一项。
DEFAULT_THRESHOLDS: dict[str, float] = {
    "recall_name": 0.98,
    "recall_feature": 0.60,
    "gini_max": 0.80,
    "idf_top1_gain": 0.15,
    "layer_dominance_max": 0.70,
    "rotation_min": 4.0,
    "decenter_min": 0.50,
    "rotation_rounds": 6.0,
}


def md5_half(sid: str) -> int:
    """确定性分半。不要用内置 ``hash()``：Python 的 str hash 带随机种子。"""
    return int(hashlib.md5(sid.encode("utf-8")).hexdigest()[:8], 16) % 2


def gini(values: Sequence[float]) -> float:
    v = sorted(x for x in values if x >= 0)
    n = len(v)
    total = sum(v)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * total) - (n + 1) / n


class CheckSuite:
    """一个 profile 上的全套断言。"""

    def __init__(self, prof: Profile, seeds: list[Seed] | None = None, state: dict | None = None):
        self.prof = prof
        self.seeds: list[Seed] = seeds if seeds is not None else build_index(prof)[0]
        self.state = state or {"picks": {}}
        self.idf = build_idf(self.seeds)
        t = dict(DEFAULT_THRESHOLDS)
        t.update(prof.verify.thresholds or {})
        self.th = t
        self._feature_probe_cache: dict[str, str] = {}

    # ── 入口 ──────────────────────────────────────────────────────────

    def run(self, groups: Sequence[str] = ("schema", "core", "content")) -> VerifyReport:
        r = VerifyReport()
        if "schema" in groups:
            self.check_schema(r)
        if "core" in groups:
            self.check_integrity(r)
            self.check_recall(r)
            self.check_concentration(r)
            self.check_idf(r)
            self.check_rotation(r)
            self.check_balance(r)
            self.check_robustness(r)
            self.check_determinism(r)
            self.check_decentralized(r)
            self.check_incremental_equiv(r)
            self.check_incremental_unbiased(r)
            self.check_id_stability(r)
            self.check_dup_detection(r)
        if "content" in groups and self.prof.verify.content:
            self.check_content(r)
        return r

    # ── 基础工具 ──────────────────────────────────────────────────────

    def _add(self, r: VerifyReport, cid: str, name: str, metric: str, target: str, ok: bool) -> bool:
        return r.add(Check(id=cid, name=name, metric=metric, target=target, ok=bool(ok)))

    def _rank_ids(self, task: str, k: int = 8, *, seeds: list[Seed] | None = None,
                  idf: dict[str, float] | None = None, state: dict | None = None,
                  use_idf: bool = True) -> list[str]:
        matches, _, _ = rank(
            self.prof,
            seeds if seeds is not None else self.seeds,
            task,
            k,
            idf=self.idf if idf is None else idf,
            state=self.state if state is None else state,
            use_idf=use_idf,
        )
        return [m.seed.id for m in matches]

    def _feature_probe(self, seed: Seed) -> str:
        """用该种子自己的高 idf 特征词构造任务（排除名字，避免平凡命中）。"""
        cached = self._feature_probe_cache.get(seed.id)
        if cached is not None:
            return cached
        name_grams = set(grams(seed.name))
        cand = [(g, w) for g, w in grams_cached(seed.text).items() if g not in name_grams]
        top = sorted(cand, key=lambda x: -self.idf.get(x[0], 0.0))[:3]
        probe = " ".join(g for g, _ in top)
        self._feature_probe_cache[seed.id] = probe
        return probe

    def _split(self) -> tuple[list[Seed], list[Seed]]:
        return (
            [s for s in self.seeds if md5_half(s.id) == 0],
            [s for s in self.seeds if md5_half(s.id) == 1],
        )

    # ── schema ────────────────────────────────────────────────────────

    def check_schema(self, r: VerifyReport) -> None:
        try:
            self.prof.validate()
            self._add(r, "S1", "profile 合法", "validate() 通过", "无异常", True)
        except Exception as exc:  # noqa: BLE001
            self._add(r, "S1", "profile 合法", f"{type(exc).__name__}: {exc}", "无异常", False)
        self._add(r, "S2", "layer 前缀齐备",
                  f"{len(self.prof.layers)} 层",
                  "每层有 prefix",
                  all(spec.prefix for spec in self.prof.layers.values()))

    # ── T1 完整性 ─────────────────────────────────────────────────────

    def check_integrity(self, r: VerifyReport) -> None:
        ids = [s.id for s in self.seeds]
        dup = [k for k, v in Counter(ids).items() if v > 1]
        self._add(r, "T1a", "ID 唯一", f"重复 {len(dup)} 个", "0", not dup)

        hollow = [s.id for s in self.seeds if not s.name or not s.text or s.grams < 3]
        self._add(r, "T1b", "字段非空壳", f"缺字段/gram<3：{len(hollow)} 条", "0", not hollow)

        broken = []
        for s in self.seeds:
            if s.origin != "source":
                continue
            if not self.prof.resolve(s.ref).exists():
                broken.append(s.id)
        self._add(r, "T1c", "ref 可解析", f"断引用 {len(broken)} 条", "0", not broken)

        # 旧货架样本有效性：防止下游「去中心化」断言恒真
        shelf = set(self.prof.verify.legacy_shelf or [])
        known = {i.lower() for i in ids}
        ghost = sorted(i for i in shelf if i.lower() not in known)
        self._add(r, "T1d", "旧货架样本有效",
                  f"无效 id {len(ghost)} 个" + (f"（{ghost[:2]}）" if ghost else ""),
                  "0", not ghost)

    # ── T2 可达性 ─────────────────────────────────────────────────────

    def check_recall(self, r: VerifyReport) -> None:
        k = 8
        miss_name = [s.id for s in self.seeds if s.id not in self._rank_ids(s.name, k)]
        acc_n = 1 - len(miss_name) / max(1, len(self.seeds))
        self._add(r, "T2a", f"名字自召回@{k}", f"{acc_n:.1%}（漏 {len(miss_name)}）",
                  f">= {self.th['recall_name']:.0%}", acc_n >= self.th["recall_name"])

        miss_feat = []
        for s in self.seeds:
            probe = self._feature_probe(s)
            if probe and s.id not in self._rank_ids(probe, k):
                miss_feat.append(s.id)
        acc_f = 1 - len(miss_feat) / max(1, len(self.seeds))
        self._add(r, "T2b", f"特征词召回@{k}", f"{acc_f:.1%}（漏 {len(miss_feat)}）",
                  f">= {self.th['recall_feature']:.0%}", acc_f >= self.th["recall_feature"])

    # ── T3 集中度 ─────────────────────────────────────────────────────

    def check_concentration(self, r: VerifyReport) -> None:
        probes = self.prof.verify.probes or []
        if not probes:
            self._add(r, "T3a", "集中度", "未配置 verify.probes", "跳过", True)
            return
        hits: Counter = Counter()
        for p in probes:
            for sid in self._rank_ids(p, 10):
                hits[sid] += 1
        g = gini(list(hits.values()))
        self._add(r, "T3a", "命中基尼系数", f"{g:.3f}", f"< {self.th['gini_max']}", g < self.th["gini_max"])
        cover = len(hits) / max(1, len(self.seeds))
        self._add(r, "T3b", "触达种子占比", f"{cover:.1%}（{len(hits)}/{len(self.seeds)}）",
                  "> 0", cover > 0)

    # ── T4 IDF 有效性（对照实验）────────────────────────────────────────

    def check_idf(self, r: VerifyReport) -> None:
        """IDF 有效性 —— 拆成「性质断言」与「端到端对照」。

        为什么要拆：早期版本只看端到端 top1 对照（开 IDF vs 关 IDF），
        在小语料上两者都是 72.7%。根因不是算法坏了，而是 —— 探针里的稀有词
        只属于目标种子，关掉 IDF 时目标仍然独享那 1 分，永远领先。
        端到端对照依赖「库里存在大量短文本 + 通用词」这一条件，小 fixture 造不出来。

        所以：**核心性质用数学断言直接验**（确定、不依赖库规模、能真失败），
        端到端对照降为「不退化」检查（大库上仍能抓到明显倒退）。
        """
        # ── T4a：IDF 单调性（硬断言）──
        df: Counter = Counter()
        for s in self.seeds:
            df.update(grams_cached(s.text).keys())
        # 只看 2-gram 与英文词：3-gram 多为跨词碎片，不代表真实信号
        pool = [g for g in df if len(g) >= 2]
        if len(pool) < 2:
            self._add(r, "T4a", "IDF 单调性", "语料 gram 不足", "跳过", True)
            return
        lo = min(pool, key=lambda g: df[g])
        hi = max(pool, key=lambda g: df[g])
        idf_lo = self.idf.get(lo, 0.0)
        idf_hi = self.idf.get(hi, 0.0)
        self._add(
            r, "T4a", "IDF 单调性",
            f"df={df[lo]}「{lo}」{idf_lo:.2f} vs df={df[hi]}「{hi}」{idf_hi:.2f}",
            "稀有 > 常见", idf_lo > idf_hi,
        )

        # ── T4b：端到端对照（只要求不退化）──
        fill = self._auto_fill(4)
        if not fill:
            self._add(r, "T4b", "top1 对照", "无可用填充词", "跳过", True)
            return

        on: list[float] = []
        off: list[float] = []
        for s in self.seeds:
            name_grams = set(grams(s.name))
            cand = [(g, w) for g, w in grams_cached(s.text).items() if g not in name_grams]
            if not cand:
                continue
            rare = max(cand, key=lambda x: self.idf.get(x[0], 0.0))[0]
            probe = f"{rare} {fill}"
            for use, bucket in ((True, on), (False, off)):
                ids = self._rank_ids(probe, 8, use_idf=use)
                bucket.append(1.0 if ids and ids[0] == s.id else 0.0)
        if not on:
            self._add(r, "T4b", "top1 对照", "无可对照样本", "跳过", True)
            return
        a, b = statistics.fmean(on), statistics.fmean(off)
        floor = b * 0.90  # 允许噪声，但绝不允许明显倒退
        self._add(
            r, "T4b", "top1 对照（IDF vs 关）",
            f"{a:.1%} vs {b:.1%}",
            f">= {floor:.0%}（不退化）", a >= floor,
        )

    def _auto_fill(self, n: int = 4) -> str:
        """T4 的通用填充词：优先 profile 声明，但必须真的「通用」。

        实测：fixture profile 里写的是「方法/计算/结果/分析」，在库里 df = 0~2/22，
        根本起不到「稀释稀有词」的作用。所以这里加一道保底：
        profile 给的词只在 df ≥ max(2, N/10) 时采信，不足则自动从全库最高频 gram 补。
        """
        df: Counter = Counter()
        for s in self.seeds:
            df.update(grams_cached(s.text).keys())
        floor = max(2, int(len(self.seeds) * 0.1))

        picked: list[str] = []
        for w in (self.prof.verify.generic_fill or []):
            if df.get(w, 0) >= floor and w not in picked:
                picked.append(w)
        if len(picked) < n:
            for g, _c in df.most_common(300):
                if len(g) < 2 or g in picked:
                    continue
                picked.append(g)
                if len(picked) >= n:
                    break
        return " ".join(picked[:n])

    # ── T5 状态轮转 ───────────────────────────────────────────────────

    def check_rotation(self, r: VerifyReport) -> None:
        probes = self.prof.verify.probes or []
        if not probes:
            self._add(r, "T5", "状态轮转", "未配置 verify.probes", "跳过", True)
            return
        rounds = int(self.th.get("rotation_rounds", 6))
        state: dict = {"picks": {}}
        import time as _time
        tops: list[str] = []
        for _ in range(rounds):
            ids = self._rank_ids(probes[0], 5, state=state)
            if not ids:
                break
            tops.append(ids[0])
            rec = state["picks"].setdefault(ids[0], {"count": 0, "last_ts": 0, "scores": []})
            rec["count"] += 1
            rec["last_ts"] = _time.time()
        distinct = len(set(tops))
        self._add(r, "T5", f"{rounds} 次连选的 top1 多样性", f"{distinct} 个不同",
                  f">= {int(self.th['rotation_min'])}", distinct >= self.th["rotation_min"])

    # ── T6 跨层均衡 ───────────────────────────────────────────────────

    def check_balance(self, r: VerifyReport) -> None:
        probes = self.prof.verify.probes or []
        if not probes:
            self._add(r, "T6", "跨层均衡", "未配置 verify.probes", "跳过", True)
            return
        k = 8
        starved = dominant = multi = 0
        for p in probes:
            tg = grams(p)
            avail = Counter(s.layer for s in self.seeds
                            if _score_nonzero(self.prof, s, tg, self.idf))
            matches, quotas, _ = rank(self.prof, self.seeds, p, k, idf=self.idf, state={"picks": {}})
            counts = Counter(m.seed.layer for m in matches)
            assigned = sum(counts.values())
            for layer, q in quotas.items():
                if avail.get(layer, 0) >= q and counts.get(layer, 0) < q and assigned >= q:
                    starved += 1
            if sum(1 for n in avail.values() if n > 0) >= 2:
                multi += 1
                share = max(counts.values()) / (assigned or 1)
                top_layer = counts.most_common(1)[0][0] if counts else ""
                cap = max(self.th["layer_dominance_max"],
                          avail.get(top_layer, 0) / max(1, sum(avail.values())))
                if share > cap:
                    dominant += 1
        self._add(r, "T6a", "层饥饿（有货却没给位）", f"{starved} 次", "0", starved == 0)
        self._add(r, "T6b", "多候选层下单层垄断", f"{dominant}/{multi}",
                  f"0（上界 {self.th['layer_dominance_max']:.0%}）", dominant == 0)

    # ── T7 鲁棒性 ─────────────────────────────────────────────────────

    def check_robustness(self, r: VerifyReport) -> None:
        cases = ["", "a", "🎨🎨", "的的的", "一" * 2000,
                 "SELECT * FROM seeds", "<script>x</script>", "\n\t\r"]
        crashed = []
        for c in cases:
            try:
                self._rank_ids(c, 5)
            except Exception as exc:  # noqa: BLE001
                crashed.append(f"{type(exc).__name__}")
        self._add(r, "T7a", "边界输入不抛异常", f"崩 {len(crashed)}/{len(cases)}", "0", not crashed)

        try:
            from .score import novelty
            v = novelty({"count": 0, "last_ts": 0}, self.prof)
            ok = isinstance(v, float)
        except Exception:  # noqa: BLE001
            ok = False
        self._add(r, "T7b", "状态缺字段不崩", "仍返回 float", "True", ok)

    # ── T8 确定性 ─────────────────────────────────────────────────────

    def check_determinism(self, r: VerifyReport) -> None:
        probes = self.prof.verify.probes or [s.name for s in self.seeds[:3]]
        if not probes:
            self._add(r, "T8", "确定性", "无探针", "跳过", True)
            return
        a = self._rank_ids(probes[0], 10)
        b = self._rank_ids(probes[0], 10)
        self._add(r, "T8", "两次排序完全一致", "一致" if a == b else "不一致", "一致", a == b)

    # ── T9 去中心化 ───────────────────────────────────────────────────

    def check_decentralized(self, r: VerifyReport) -> None:
        probes = self.prof.verify.probes or []
        shelf = {i.lower() for i in (self.prof.verify.legacy_shelf or [])}
        if not probes or not shelf:
            self._add(r, "T9", "去中心化", "未配置 probes / legacy_shelf", "跳过", True)
            return
        tops, outside = [], []
        for p in probes:
            ids = self._rank_ids(p, 5)
            if not ids:
                continue
            tops.append(ids[0])
            if ids[0].lower() not in shelf:
                outside.append(ids[0])
        ratio = len(outside) / max(1, len(tops))
        self._add(r, "T9", "top1 落在旧货架之外", f"{ratio:.1%}（{len(outside)}/{len(tops)}）",
                  f">= {self.th['decenter_min']:.0%}", ratio >= self.th["decenter_min"])
        distinct = len(set(tops))
        self._add(r, "T9b", "top1 自身多样性", f"{distinct}/{len(tops)} 个不同",
                  "无单粒垄断", distinct >= 0.6 * max(1, len(tops)))

    # ── T10 增量等价 ──────────────────────────────────────────────────

    def check_incremental_equiv(self, r: VerifyReport) -> None:
        a, b = self._split()
        merged, collided = merge_seeds(a, b, self.prof)
        self._add(r, "T10a", "ID 集合等价", f"{len(merged)}/{len(self.seeds)}",
                  "完全一致", {s.id for s in merged} == {s.id for s in self.seeds})
        self._add(r, "T10b", "排序等价", "逐位对比",
                  "完全一致", [s.id for s in merged] == [s.id for s in self.seeds])
        self._add(r, "T10c", "无意外 ID 撞车", f"{collided} 次", "0", collided == 0)

    # ── T11 增量无偏 ──────────────────────────────────────────────────

    def check_incremental_unbiased(self, r: VerifyReport) -> None:
        a, b = self._split()
        if not b:
            self._add(r, "T11a", "增量无偏", "切分后无增量样本", "跳过", True)
            return
        batches = _chunks(b, 5)
        cur = list(a)
        recalls: list[float] = []
        ginis: list[float] = []
        probes = self.prof.verify.probes or []
        for batch in batches:
            cur, _ = merge_seeds(cur, batch, self.prof)
            cur_idf = build_idf(cur)
            hit = sum(1 for s in batch if s.id in self._rank_ids(s.name, 8, seeds=cur, idf=cur_idf))
            recalls.append(hit / max(1, len(batch)))
            if probes:
                counts: Counter = Counter()
                for p in probes[:12]:
                    for sid in self._rank_ids(p, 8, seeds=cur, idf=cur_idf):
                        counts[sid] += 1
                ginis.append(gini(list(counts.values())))
        self._add(r, "T11a", "增量中新增种子召回", f"最低 {min(recalls):.1%}", ">= 90%",
                  min(recalls) >= 0.90)
        if len(ginis) >= 2:
            drift = ginis[-1] / max(1e-9, ginis[0])
            self._add(r, "T11b", "基尼漂移（终/初）", f"{ginis[0]:.3f} → {ginis[-1]:.3f}（×{drift:.2f}）",
                      "< 1.2×", drift < 1.2)

    # ── T12 ID 稳定 ───────────────────────────────────────────────────

    def check_id_stability(self, r: VerifyReport) -> None:
        a, b = self._split()
        merged, _ = merge_seeds(a, b, self.prof)
        before = {s.id for s in a}
        after = {s.id for s in merged}
        renamed = sorted(i for i in before if i not in after)
        self._add(r, "T12", "已有 ID 零改写",
                  f"丢失/改名 {len(renamed)} 个" + (f"（{renamed[:2]}）" if renamed else ""),
                  "0", not renamed)

    # ── T13 重复检测 ──────────────────────────────────────────────────

    def check_dup_detection(self, r: VerifyReport) -> None:
        if not self.seeds:
            return
        src = max(self.seeds, key=lambda s: len(s.text))
        alias = Seed(id="probe-alias", name=src.name, layer=src.layer, group=src.group,
                     one_liner=src.one_liner, text=src.text, grams=src.grams, ref=src.ref)
        dup, sim = find_duplicate(self.seeds, alias, self.prof.norms.dup_threshold)
        self._add(r, "T13a", "同义别名被识别",
                  f"命中 {dup.id if dup else 'None'}（{sim:.2f}）",
                  f">= {self.prof.norms.dup_threshold}", dup is not None)

        novel = Seed(id="probe-novel", name="qzjvxk", layer=src.layer, group=src.group,
                     one_liner="", text="qzjvxk wpfmrt 完全无关的新概念", grams=12, ref="")
        dup2, sim2 = find_duplicate(self.seeds, novel, self.prof.norms.dup_threshold)
        self._add(r, "T13b", "真新种子不误报", f"{sim2:.2f}",
                  f"< {self.prof.norms.dup_threshold}", dup2 is None)

    # ── content（可选，profile 驱动）────────────────────────────────────

    def check_content(self, r: VerifyReport) -> None:
        cfg = self.prof.verify.content or {}

        dirs = cfg.get("dirs") or {}
        bad_dir = []
        for rel, expect in dirs.items():
            p = self.prof.resolve(rel)
            n = len(list(p.rglob("*.md"))) if p.is_dir() else -1
            if n != int(expect):
                bad_dir.append(f"{rel}={n}/{expect}")
        if dirs:
            self._add(r, "C1", "目录文件数", "全部吻合" if not bad_dir else "；".join(bad_dir[:2]),
                      "== 期望", not bad_dir)

        expect_total = cfg.get("expected_entries")
        if expect_total:
            self._add(r, "C2", "条目总数", f"{len(self.seeds)}", f"== {expect_total}",
                      len(self.seeds) == int(expect_total))

        fields = cfg.get("fields") or []
        if fields:
            bad = []
            for s in self.seeds:
                ref = self.prof.resolve(s.ref) if s.ref else None
                if ref is None or not ref.is_file():
                    continue
                text = ref.read_text(encoding="utf-8")
                lack = [f for f in fields if f"**{f}**：" not in text]
                if lack and s.origin == "source":
                    bad.append(f"{s.id}（缺 {'/'.join(lack)}）")
            self._add(r, "C3", "字段齐全",
                      f"{len(self.seeds) - len(bad)}/{len(self.seeds)}" + (f"；{bad[0]}" if bad else ""),
                      "全部齐全", not bad)

        docs = cfg.get("docs") or []
        if docs:
            stale = [d for d in docs
                     if not self.prof.resolve(d).is_file()
                     or str(len(self.seeds)) not in self.prof.resolve(d).read_text(encoding="utf-8")]
            self._add(r, "C4", "文档声明总数", "全部声明" if not stale else "；".join(stale[:2]),
                      "含真实总数", not stale)


# ── 模块级工具 ────────────────────────────────────────────────────────────


def _score_nonzero(prof: Profile, seed: Seed, task_grams: dict[str, float],
                   idf: dict[str, float]) -> bool:
    from .score import score_seed
    return score_seed(seed, task_grams, idf, prof)[0] > 0


def _chunks(items: list[Seed], n: int) -> list[list[Seed]]:
    size = max(1, math.ceil(len(items) / n))
    return [items[i:i + size] for i in range(0, len(items), size)]


def run(prof: Profile, seeds: list[Seed] | None = None,
        state: dict | None = None,
        groups: Sequence[str] = ("schema", "core", "content")) -> VerifyReport:
    """便捷入口：``run(prof)`` 一套跑完。"""
    return CheckSuite(prof, seeds, state).run(groups)
