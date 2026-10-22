"""端到端 —— build → match → pick → add → verify 全链路，以及可观测的失败模式。"""

import tempfile
import unittest
from pathlib import Path

import helpers
from seedbrain import DuplicateError, InvalidInputError


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.brain = helpers.make_brain(self.out)

    def tearDown(self):
        self._tmp.cleanup()


class BuildTest(_Base):
    def test_build_counts(self):
        r = self.brain.build()
        self.assertEqual(r.total, 22)
        self.assertEqual(r.layers, {"tool": 16, "card": 6})
        self.assertEqual(r.added, 0)

    def test_build_is_idempotent(self):
        """同一输入必得同一字节 —— CI 用 git diff 拦索引漂移的前提。"""
        self.brain.build()
        p1 = self.brain.profile.resolve_output(self.brain.profile.paths.index_jsonl)
        first = p1.read_bytes()
        self.brain.build()
        self.assertEqual(p1.read_bytes(), first)

    def test_index_md_written(self):
        self.brain.build()
        md = self.brain.profile.resolve_output(self.brain.profile.paths.index_md)
        text = md.read_text(encoding="utf-8")
        self.assertIn("等距平铺", text)
        self.assertIn("tl-矩阵分解", text)

    def test_fresh_snapshot_after_build(self):
        self.brain.build()
        self.assertEqual(len(self.brain.seeds), 22)


class MatchTest(_Base):
    def setUp(self):
        super().setUp()
        self.brain.build()

    def test_returns_relevant(self):
        matches = self.brain.match("非平稳信号的时频分析", k=3)
        self.assertTrue(matches)
        names = " ".join(m.seed.name + m.seed.one_liner for m in matches)
        self.assertTrue("时频" in names or "短时" in names)

    def test_debug_triple(self):
        matches, quotas, n_hit = self.brain.match("采样", k=5, debug=True)
        self.assertIsInstance(quotas, dict)
        self.assertGreaterEqual(n_hit, len(matches))

    def test_zero_hit(self):
        self.assertEqual(self.brain.match("qqqzzz", k=5), [])


class PickTest(_Base):
    def setUp(self):
        super().setUp()
        self.brain.build()

    def test_pick_updates_state(self):
        sid = self.brain.match("矩阵分解", k=1)[0].seed.id
        rec = self.brain.pick(sid, score=5, note="一次过")
        self.assertEqual(rec["count"], 1)
        self.assertEqual(rec["scores"], [5])

    def test_pick_twice_increments(self):
        sid = self.brain.seeds[0].id
        self.brain.pick(sid)
        rec = self.brain.pick(sid)
        self.assertEqual(rec["count"], 2)

    def test_pick_unknown_raises(self):
        with self.assertRaises(InvalidInputError):
            self.brain.pick("不存在-id")

    def test_picked_seed_sinks(self):
        """同一任务连问两次，第二次应换一个（状态记忆生效）。"""
        first = self.brain.match("信号", k=1)[0].seed.id
        self.brain.pick(first)
        self.brain.build()  # 重建索引（不会清状态）
        second = self.brain.match("信号", k=3)
        self.assertGreater(len(second), 1)


class AddTest(_Base):
    def setUp(self):
        super().setUp()
        self.brain.build()

    def test_add_then_visible(self):
        seed = self.brain.add(
            name="小波包分解", layer="tool",
            signals=["小波", "分解", "非平稳"],
            one_liner="多分辨率细分",
            ref=f"{helpers.FIXTURE_REL}/tools.md",
        )
        self.assertTrue(seed.id.startswith("tl-"))
        result = self.brain.build()
        self.assertEqual(result.added, 1)
        self.assertIn(seed.id, {s.id for s in self.brain.seeds})
        # 立即可召回
        hits = [m.seed.id for m in self.brain.match("小波 非平稳", k=5)]
        self.assertIn(seed.id, hits)

    def test_add_rejects_missing_ref(self):
        with self.assertRaises(InvalidInputError):
            self.brain.add(name="瞎猜路径", layer="tool", ref="references/nope.md")

    def test_add_rejects_unknown_layer(self):
        with self.assertRaises(InvalidInputError):
            self.brain.add(name="X", layer="bogus")

    def test_add_rejects_duplicate(self):
        with self.assertRaises(DuplicateError):
            self.brain.add(
                name="低秩近似专题", layer="card",
                signals=["低秩", "压缩", "奇异值"],
                one_liner="需要在保留主要结构的前提下压缩矩阵规模",
                ref=f"{helpers.FIXTURE_REL}/cards/low-rank.md",
            )

    def test_add_dry_run_does_not_write(self):
        before = self.brain.profile.resolve_output(self.brain.profile.paths.additions)
        existed = before.exists()
        self.brain.add(name="只看看", layer="tool", dry_run=True,
                       ref=f"{helpers.FIXTURE_REL}/tools.md")
        self.assertEqual(before.exists(), existed)

    def test_force_bypasses_duplicate(self):
        seed = self.brain.add(
            name="低秩近似专题", layer="card", force=True,
            signals=["低秩"], ref=f"{helpers.FIXTURE_REL}/cards/low-rank.md",
        )
        self.assertTrue(seed.id is not None)


class VerifyTest(_Base):
    def setUp(self):
        super().setUp()
        self.brain.build()

    def test_verify_all_green(self):
        report = self.brain.verify()
        failed = [(c.id, c.metric) for c in report.checks if not c.ok]
        self.assertEqual(report.failed, 0, f"失败项：{failed}")
        self.assertGreaterEqual(len(report.checks), 20)

    def test_verify_can_fail(self):
        """断言必须能失败 —— 否则测试是装饰品。

        故意把 legacy_shelf 写成不存在的 id，T1d 必须报错。
        """
        broken = helpers.make_brain_with(
            self.brain, verify={"probes": self.brain.profile.verify.probes,
                                "legacy_shelf": ["tl-根本没有这个"]}
        )
        report = broken.verify(groups=("core",))
        self.assertGreater(report.failed, 0)

    def test_stats_shape(self):
        st = self.brain.stats()
        self.assertEqual(st.total, 22)
        self.assertEqual(st.used, 0)
        self.assertEqual(st.coverage, 0.0)
        self.assertTrue(st.blind_groups)


class CliSmokeTest(unittest.TestCase):
    """CLI 只做冒烟：能解析参数、退出码正确。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.profile = helpers.make_brain(self.out).profile.src_path

    def tearDown(self):
        self._tmp.cleanup()

    def test_build_and_verify_exit_codes(self):
        from seedbrain.cli import main

        self.assertEqual(main(["build", "--profile", str(self.profile), "--quiet"]), 0)
        self.assertEqual(main(["verify", "--profile", str(self.profile)]), 0)

    def test_bad_profile_returns_2(self):
        from seedbrain.cli import main

        self.assertEqual(main(["build", "--profile", "不存在.json"]), 2)

    def test_match_json(self):
        from seedbrain.cli import main

        main(["build", "--profile", str(self.profile), "--quiet"])
        self.assertEqual(main(["match", "矩阵", "--profile", str(self.profile),
                               "--json", "--k", "2"]), 0)


if __name__ == "__main__":
    unittest.main()
