"""profile 校验 —— 五条规则必须各有失败用例（否则「校验」是摆设）。"""

import json
import tempfile
import unittest
from pathlib import Path

import helpers
from seedbrain.profile import Profile, ProfileError


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


if __name__ == "__main__":
    unittest.main()
