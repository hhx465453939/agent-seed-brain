"""评分与配额 —— 「无偏」的实现位置，必须逐条可证。"""

import time
import unittest
from pathlib import Path

import helpers
from seedbrain.score import build_idf, novelty, quotas_for, rank


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = __import__("tempfile").TemporaryDirectory()
        self.brain = helpers.make_brain(Path(self._tmp.name))
        self.brain.build()
        self.prof = self.brain.profile

    def tearDown(self):
        self._tmp.cleanup()


class NoveltyTest(_Base):
    def test_never_used_is_one(self):
        self.assertEqual(novelty(None, self.prof), 1.0)

    def test_just_used_is_suppressed(self):
        v = novelty({"count": 1, "last_ts": time.time()}, self.prof)
        self.assertLess(v, 0.5)
        self.assertGreaterEqual(v, 0.15)  # 下限作用在最终值上：复现永远可能

    def test_long_ago_recovers(self):
        """60 天后应明显回升 —— 用相对比较，不用绝对值。

        绝对值上限被次数惩罚压到 ``1/(1+0.5·ln2) ≈ 0.742``，永远到不了 0.8；
        真正要验的是「久未用 > 刚用过」这个方向。
        """
        fresh = novelty({"count": 1, "last_ts": time.time()}, self.prof)
        old = novelty({"count": 1, "last_ts": time.time() - 60 * 86400}, self.prof)
        self.assertGreater(old, fresh * 3)

    def test_count_penalty(self):
        now = time.time() - 30 * 86400
        once = novelty({"count": 1, "last_ts": now}, self.prof)
        many = novelty({"count": 10, "last_ts": now}, self.prof)
        self.assertLess(many, once)

    def test_floor_protects_reproducibility(self):
        """刚用完 10 次也要能再被选中（用户可能就想复现上次）。"""
        v = novelty({"count": 10, "last_ts": time.time()}, self.prof)
        self.assertGreaterEqual(v, 0.15 * 0.4)


class QuotaTest(_Base):
    def test_sum_never_exceeds_k(self):
        for k in (3, 5, 8, 20):
            q = quotas_for(self.prof, k)
            self.assertLessEqual(sum(q.values()), k, f"k={k}")

    def test_every_layer_gets_at_least_one(self):
        q = quotas_for(self.prof, 4)
        self.assertTrue(all(v >= 1 for v in q.values()))

    def test_proportional_to_quota(self):
        q = quotas_for(self.prof, 10)
        self.assertGreater(q["tool"], q["card"])  # tool 配额 0.6 > card 0.4


class RankTest(_Base):
    def test_relevant_first(self):
        matches = self.brain.match("降维压缩，矩阵分解", k=3)
        self.assertTrue(matches)
        self.assertIn("矩阵", matches[0].seed.name + matches[0].seed.one_liner)

    def test_hits_exposed(self):
        m = self.brain.match("矩阵分解", k=1)[0]
        self.assertTrue(m.hits)
        self.assertIsInstance(m.hits[0], tuple)
        self.assertEqual(len(m.hits[0]), 2)

    def test_deterministic(self):
        a = [m.seed.id for m in self.brain.match("信号频率", k=5)]
        b = [m.seed.id for m in self.brain.match("信号频率", k=5)]
        self.assertEqual(a, b)

    def test_no_hit_returns_empty(self):
        self.assertEqual(self.brain.match("zzzqqqxxx", k=5), [])

    def test_k_respected(self):
        matches = self.brain.match("信号", k=3)
        self.assertLessEqual(len(matches), 3)

    def test_use_idf_toggle_changes_scores(self):
        """关掉 IDF 后权重变成均匀，得分应不同（证明 IDF 真的参与计算）。"""
        seeds = self.brain.seeds
        idf = build_idf(seeds)
        on, _, _ = rank(self.prof, seeds, "采样率重建", 3, idf=idf, use_idf=True)
        off, _, _ = rank(self.prof, seeds, "采样率重建", 3, idf=idf, use_idf=False)
        self.assertNotEqual([round(m.total, 6) for m in on],
                            [round(m.total, 6) for m in off])


class IdfBuildTest(_Base):
    def test_idf_covers_all_grams(self):
        from seedbrain.tokenize import grams_cached
        idf = build_idf(self.brain.seeds)
        for s in self.brain.seeds:
            for g in grams_cached(s.text):
                self.assertIn(g, idf)


if __name__ == "__main__":
    unittest.main()
