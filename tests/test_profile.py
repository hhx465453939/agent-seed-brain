"""profile 校验 —— 五条规则必须各有失败用例（否则「校验」是摆设）。"""

import json
import tempfile
import unittest
from pathlib import Path

import helpers
from seedbrain.profile import (
    Profile,
    ProfileError,
    _apply_probes_ref,
    _deep_merge,
    _load_merged,
)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # 用 example profile 原始 dict：sources 相对于仓库根，paths 不参与校验
        self.data = helpers.read_example_profile()

    def tearDown(self):
        self._tmp.cleanup()

    def _load(self, data=None):
        p = self.tmp / "seedbrain.json"
        p.write_text(json.dumps(data or self.data, ensure_ascii=False), encoding="utf-8")
        return Profile.load(p, root=helpers.ROOT)

    def _expect_error(self, mutate, needle=""):
        data = json.loads(json.dumps(self.data))
        mutate(data)
        with self.assertRaises(ProfileError) as ctx:
            self._load(data)
        if needle:
            self.assertIn(needle, str(ctx.exception))


class ValidProfileTest(_Base):
    def test_loads_example(self):
        prof = self._load()
        self.assertEqual(prof.name, "example")
        self.assertEqual(len(prof.sources), 2)
        self.assertEqual(set(prof.layers), {"tool", "card"})

    def test_layer_order_by_quota(self):
        prof = self._load()
        self.assertEqual(prof.layer_order, ["tool", "card"])

    def test_prefix_lookup(self):
        prof = self._load()
        self.assertEqual(prof.prefix_of("tool"), "tl")
        self.assertEqual(prof.prefix_of("unknown"), "unknown")


class SchemaRuleTest(_Base):
    def test_wrong_schema_version(self):
        self._expect_error(lambda d: d.update(schema_version=99), "schema_version")

    def test_no_sources(self):
        self._expect_error(lambda d: d.update(sources=[]), "sources")

    def test_unknown_layer(self):
        self._expect_error(lambda d: d["sources"][0].update(layer="nope"), "未在 layers 中声明")

    def test_missing_prefix(self):
        def mutate(d):
            d["layers"]["tool"]["prefix"] = ""
        self._expect_error(mutate, "prefix")

    def test_quota_sum_over_one(self):
        def mutate(d):
            d["layers"]["tool"]["quota"] = 0.9
            d["layers"]["card"]["quota"] = 0.9
        self._expect_error(mutate, "quota")

    def test_source_path_missing(self):
        self._expect_error(lambda d: d["sources"][0].update(path="nope/none.md"), "不存在")

    def test_bad_regex(self):
        self._expect_error(lambda d: d["sources"][0].update(entry_re="(unclosed"), "正则")

    def test_entry_re_requires_name_group(self):
        self._expect_error(
            lambda d: d["sources"][0].update(entry_re=r"^(?P<x>.+)$"), "name"
        )

    def test_card_requires_title_group(self):
        self._expect_error(
            lambda d: d["sources"][1].update(title_re=r"^(?P<x>.+)$"), "title"
        )


class PathSafetyTest(_Base):
    def test_resolve_rejects_escape(self):
        prof = self._load()
        with self.assertRaises(ProfileError):
            prof.resolve("../../../etc/passwd")

    def test_resolve_output_allows_outside(self):
        """输出位置必须能写到仓库外 —— 否则测试与 CI 无法隔离。"""
        prof = self._load()
        outside = self.tmp / "out.json"
        self.assertEqual(prof.resolve_output(str(outside)), outside.resolve())

    def test_resolve_allows_inside(self):
        prof = self._load()
        self.assertTrue(str(prof.resolve("tests/fixtures/mini-domain/tools.md")).endswith("tools.md"))


class InheritanceTest(unittest.TestCase):
    """`extends` 的语义必须有测试兜住 —— 合并规则写错会静默影响所有领域。

    两组：纯函数（_deep_merge / _load_merged，精确）与端到端（Profile.load，真实）。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, data):
        p = self.tmp / name
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    # ── 纯函数 ──────────────────────────────────────────────────

    def test_deep_merge_recurses_dicts(self):
        base = {"norms": {"decay_tau_days": 14.0, "max_hits": 5}, "name": "b"}
        over = {"norms": {"decay_tau_days": 7.0}}
        merged = _deep_merge(base, over)
        self.assertEqual(merged["norms"]["decay_tau_days"], 7.0)   # 子覆盖
        self.assertEqual(merged["norms"]["max_hits"], 5)          # 父保留
        self.assertEqual(merged["name"], "b")

    def test_deep_merge_replaces_lists(self):
        """list 整体替换 —— 否则「清空继承来的 probes」无法表达。"""
        merged = _deep_merge({"probes": ["a", "b", "c"]}, {"probes": ["z"]})
        self.assertEqual(merged["probes"], ["z"])

    def test_deep_merge_does_not_mutate_base(self):
        base = {"norms": {"max_hits": 5}}
        _deep_merge(base, {"norms": {"max_hits": 9}})
        self.assertEqual(base["norms"]["max_hits"], 5)

    def test_load_merged_chain(self):
        self._write("base.json", {"schema_version": 1, "name": "base"})
        child = self._write("child.json", {"extends": "base.json", "name": "child"})
        data, chain = _load_merged(child)
        self.assertEqual(chain, ["base.json"])
        self.assertEqual(data["name"], "child")
        self.assertNotIn("extends", data)

    def test_load_merged_cycle_detected(self):
        self._write("a.json", {"extends": "b.json", "name": "a"})
        self._write("b.json", {"extends": "a.json", "name": "b"})
        with self.assertRaises(ProfileError) as ctx:
            _load_merged(self.tmp / "a.json")
        self.assertIn("循环", str(ctx.exception))

    def test_load_merged_missing_base(self):
        child = self._write("child.json", {"extends": "nope.json", "name": "c"})
        with self.assertRaises(ProfileError) as ctx:
            _load_merged(child)
        self.assertIn("不存在", str(ctx.exception))

    def test_load_merged_bad_regex_in_base(self):
        """base 里的正则写错时，报错必须指向具体字段。"""
        self._write("base.json", {
            "schema_version": 1, "name": "base",
            "sources": [{"kind": "table", "path": "x.md", "layer": "t",
                         "entry_re": "(unclosed"}],
            "layers": {"t": {"prefix": "t", "quota": 1.0}},
        })
        child = self._write("child.json", {"extends": "base.json", "name": "c"})
        with self.assertRaises(ProfileError) as ctx:
            Profile.load(child, root=self.tmp)
        self.assertIn("正则", str(ctx.exception))

    # ── 端到端 ──────────────────────────────────────────────────

    def _valid_min_profile(self, name, extra=None):
        """构造最小合法 profile（对 fixture 源的引用改成临时目录里的文件）。"""
        (self.tmp / "src.md").write_text(
            "## g\n\n- **甲** · 类 —— 描述甲 ｜ 信号：甲\n", encoding="utf-8")
        data = {
            "schema_version": 1, "name": name,
            "sources": [{"kind": "table", "path": "src.md", "layer": "t",
                         "group_re": r"^##\s+(?P<group>.+)$",
                         "entry_re": r"^-\s*\*\*(?P<name>[^*]+?)\*\*\s*·\s*(?P<tag>[^—]+?)\s*——\s*(?P<desc>.+)$"}],
            "layers": {"t": {"prefix": "t", "quota": 1.0}},
        }
        if extra:
            data.update(extra)
        return data

    def test_profile_extends_end_to_end(self):
        self._write("base.json", {
            "schema_version": 1, "norms": {"decay_tau_days": 14.0, "max_hits": 5},
            "verify": {"thresholds": {"recall_name": 0.98, "gini_max": 0.8}},
        })
        child = self._write("child.json", self._valid_min_profile("child", {
            "extends": "base.json",
            "norms": {"decay_tau_days": 7.0},
            "verify": {"probes": ["甲"], "thresholds": {"recall_name": 0.9}},
        }))
        p = Profile.load(child, root=self.tmp)
        self.assertEqual(p.extends_chain, ["base.json"])
        self.assertEqual(p.norms.decay_tau_days, 7.0)   # 覆盖
        self.assertEqual(p.norms.max_hits, 5)           # 继承
        self.assertEqual(p.verify.thresholds["recall_name"], 0.9)   # 覆盖
        self.assertEqual(p.verify.thresholds["gini_max"], 0.8)      # 继承
        self.assertEqual(p.verify.probes, ["甲"])                   # 替换


class ProbesRefTest(unittest.TestCase):
    """v0.3：probes_ref / builtin: 引用 —— 每个新行为都要有能失败的断言。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _pool(self, name, data):
        p = self.tmp / name
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def test_probes_ref_appends(self):
        """池在前 + 本域在后（不是替换，也不是本域在前）。"""
        self._pool("pool.json", ["a", "b", "c"])
        out = _apply_probes_ref(
            {"verify": {"probes_ref": "pool.json", "probes": ["x", "y"]}}, self.tmp)
        self.assertEqual(out["verify"]["probes"], ["a", "b", "c", "x", "y"])
        self.assertNotIn("probes_ref", out["verify"])
        self.assertEqual(out["verify"]["_source"], {"ref": "pool.json", "pool": 3, "local": 2})

    def test_probes_ref_missing_file(self):
        with self.assertRaises(ProfileError) as ctx:
            _apply_probes_ref({"verify": {"probes_ref": "nope.json"}}, self.tmp)
        self.assertIn("不存在", str(ctx.exception))

    def test_probes_ref_empty_pool(self):
        """空池必须报错——不能静默跑出零探针的 verify。"""
        self._pool("empty.json", [])
        with self.assertRaises(ProfileError) as ctx:
            _apply_probes_ref({"verify": {"probes_ref": "empty.json"}}, self.tmp)
        self.assertIn("非空数组", str(ctx.exception))

    def test_probes_ref_bad_json(self):
        (self.tmp / "bad.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(ProfileError) as ctx:
            _apply_probes_ref({"verify": {"probes_ref": "bad.json"}}, self.tmp)
        self.assertIn("不是合法 JSON", str(ctx.exception))

    def test_probes_ref_absent_keeps_behaviour(self):
        """回归：不用 probes_ref 时行为与 v0.2 完全一致。"""
        out = _apply_probes_ref({"verify": {"probes": ["a"]}}, self.tmp)
        self.assertEqual(out["verify"]["probes"], ["a"])
        self.assertNotIn("_source", out["verify"])

    def test_builtin_probes_ref_resolves(self):
        """builtin: 必须能在包内找到（发布后 wheel 里也要有，见 package-data）。"""
        out = _apply_probes_ref(
            {"verify": {"probes_ref": "builtin:probes/core"}}, self.tmp)
        self.assertGreaterEqual(len(out["verify"]["probes"]), 5)

    def test_builtin_missing_raises(self):
        with self.assertRaises(ProfileError) as ctx:
            _apply_probes_ref({"verify": {"probes_ref": "builtin:probes/nope"}}, self.tmp)
        self.assertIn("内置配置不存在", str(ctx.exception))

    def test_profile_records_probe_source(self):
        """`config --show` 靠 Profile.probes_source 报来源。"""
        prof = Profile.load(helpers.EXAMPLE_PROFILE, root=helpers.ROOT)
        self.assertEqual(prof.probes_source.get("pool"), 8)
        self.assertEqual(prof.probes_source.get("local"), 4)
        self.assertEqual(len(prof.verify.probes), 12)


if __name__ == "__main__":
    unittest.main()
