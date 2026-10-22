"""增量池 —— 三条硬约束（不改写老 ID / 不丢数据 / 可审计）的验证。"""

import json
import tempfile
import unittest
from pathlib import Path

import helpers
from seedbrain.additions import (
    append_addition,
    find_duplicate,
    load_additions,
    merge_seeds,
    seed_from_addition,
)
from seedbrain.models import Seed


def _seed(sid, layer="tool", text="甲 乙 丙"):
    return Seed(id=sid, name=sid, layer=layer, group="g", one_liner="",
                text=text, grams=3, ref="")


class MergeTest(unittest.TestCase):
    def test_collision_keeps_both(self):
        base = [_seed("tl-a")]
        adds = [_seed("tl-a", text="不同的文本")]
        merged, collided = merge_seeds(base, adds)
        self.assertEqual(collided, 1)
        self.assertEqual(len(merged), 2)  # 绝不覆盖
        self.assertIn("tl-a-2", {s.id for s in merged})

    def test_no_collision_when_ids_differ(self):
        merged, collided = merge_seeds([_seed("tl-a")], [_seed("tl-b")])
        self.assertEqual(collided, 0)
        self.assertEqual(len(merged), 2)

    def test_sorted_stably(self):
        merged, _ = merge_seeds([_seed("tl-b"), _seed("tl-a")], [_seed("tl-c")])
        self.assertEqual([s.id for s in merged], ["tl-a", "tl-b", "tl-c"])

    def test_original_ids_never_rewritten(self):
        base = [_seed(f"tl-{i}") for i in range(5)]
        merged, collided = merge_seeds(base, [_seed(f"tl-{i}", text="x") for i in range(5)])
        self.assertEqual(collided, 5)
        original = {s.id for s in base}
        self.assertTrue(original.issubset({s.id for s in merged}))


class DuplicateTest(unittest.TestCase):
    def test_short_alias_detected(self):
        """短候选 vs 长已有：包含度必须能识别，Jaccard 会稀释到 0.05 而漏报。"""
        long_text = "矩阵分解 降维 压缩 低秩 去噪 分解 乘积"
        existing = [_seed("tl-矩阵分解", text=long_text)]
        cand = _seed("tl-新", text="矩阵分解 降维 压缩")
        dup, sim = find_duplicate(existing, cand, threshold=0.75)
        self.assertIsNotNone(dup)
        self.assertEqual(dup.id, "tl-矩阵分解")
        self.assertGreaterEqual(sim, 0.75)

    def test_unrelated_not_flagged(self):
        existing = [_seed("tl-矩阵分解", text="矩阵分解 降维 压缩")]
        cand = _seed("tl-新", text="烘焙 面包 酵母")
        dup, _ = find_duplicate(existing, cand, threshold=0.75)
        self.assertIsNone(dup)

    def test_layer_isolation(self):
        """跨层同名不算重复：同一概念可以在不同层各有一粒。"""
        existing = [_seed("tl-x", layer="tool", text="甲 乙")]
        cand = _seed("cd-x", layer="card", text="甲 乙")
        dup, _ = find_duplicate(existing, cand, threshold=0.5)
        self.assertIsNone(dup)


class SeedFromAdditionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = helpers.make_brain(Path(self._tmp.name))
        self.prof = self.brain.profile

    def tearDown(self):
        self._tmp.cleanup()

    def test_prefix_added(self):
        rec = {"name": "新方法", "layer": "tool", "signals": ["甲"], "one_liner": ""}
        s = seed_from_addition(self.prof, rec)
        self.assertTrue(s.id.startswith("tl-"))
        self.assertEqual(s.origin, "addition")

    def test_explicit_id_kept(self):
        rec = {"name": "新方法", "layer": "tool", "id": "my-own-id", "signals": []}
        s = seed_from_addition(self.prof, rec)
        self.assertEqual(s.id, "tl-my-own-id")

    def test_text_includes_signals(self):
        rec = {"name": "新方法", "layer": "tool",
               "signals": ["降维", "压缩"], "one_liner": "一句话"}
        s = seed_from_addition(self.prof, rec)
        for token in ("新方法", "降维", "压缩", "一句话"):
            self.assertIn(token, s.text)


class LoadTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.brain = helpers.make_brain(self.dir)
        self.prof = self.brain.profile

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_additions(self.prof), [])

    def test_corrupt_line_skipped(self):
        path = self.prof.resolve_output(self.prof.paths.additions)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"name":"好行","layer":"tool"}\n'
            'not json at all\n'
            '{"no_name":true}\n',
            encoding="utf-8",
        )
        recs = load_additions(self.prof)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["name"], "好行")

    def test_append_is_newline_terminated(self):
        append_addition(self.prof, {"name": "甲", "layer": "tool"})
        append_addition(self.prof, {"name": "乙", "layer": "tool"})
        path = self.prof.resolve_output(self.prof.paths.additions)
        raw = path.read_text(encoding="utf-8")
        self.assertTrue(raw.endswith("\n"))
        self.assertEqual(len([ln for ln in raw.splitlines() if ln.strip()]), 2)
        self.assertEqual(json.loads(raw.splitlines()[0])["name"], "甲")


if __name__ == "__main__":
    unittest.main()
