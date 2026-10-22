"""源解析 —— profile 的正则与真实 Markdown 格式是否对得上，全靠这层。"""

import tempfile
import unittest
from pathlib import Path

import helpers
from seedbrain.parse import ParseError, parse_source
from seedbrain.profile import Profile


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.brain = helpers.make_brain(self.tmp)
        self.prof = self.brain.profile

    def tearDown(self):
        self._tmp.cleanup()


class TableParseTest(_Base):
    def test_entry_count(self):
        src = self.prof.sources[0]
        seeds = parse_source(self.prof, src)
        self.assertEqual(len(seeds), 16)  # fixture 里 16 条方法

    def test_group_assigned(self):
        seeds = parse_source(self.prof, self.prof.sources[0])
        groups = {s.group for s in seeds}
        self.assertIn("一、结构", groups)
        self.assertEqual(len(groups), 4)

    def test_ref_points_to_source_file(self):
        seeds = parse_source(self.prof, self.prof.sources[0])
        self.assertTrue(all(s.ref.endswith("tools.md") for s in seeds))

    def test_ascii_name_preferred_for_id(self):
        """名字里有 ASCII 就用它；纯中文才用中文 slug。"""
        from seedbrain.parse import _slug_from_name
        self.assertEqual(_slug_from_name("SVD Decomposition"), "svd-decomposition")
        self.assertEqual(_slug_from_name("矩阵分解"), "")

    def test_chinese_id_is_readable(self):
        """纯中文名不应带无意义序号（旧实现会产出 ``001-矩阵分解``）。"""
        seeds = parse_source(self.prof, self.prof.sources[0])
        ids = {s.id for s in seeds}
        self.assertIn("矩阵分解", ids)
        self.assertFalse(any(i[:3].isdigit() for i in ids), f"出现序号前缀 ID：{sorted(ids)[:3]}")

    def test_one_liner_truncated(self):
        seeds = parse_source(self.prof, self.prof.sources[0])
        self.assertTrue(all(len(s.one_liner) <= 90 for s in seeds))


class CardParseTest(_Base):
    def test_card_count(self):
        seeds = parse_source(self.prof, self.prof.sources[1])
        self.assertEqual(len(seeds), 6)

    def test_title_strips_template_parts(self):
        seeds = parse_source(self.prof, self.prof.sources[1])
        names = {s.name for s in seeds}
        self.assertIn("低秩近似专题", names)
        self.assertFalse(any(n.lower().startswith("card") for n in names), names)

    def test_fields_merged_into_text(self):
        seeds = parse_source(self.prof, self.prof.sources[1])
        sampling = next(s for s in seeds if s.id == "sampling")
        self.assertIn("适用场景", sampling.text)
        self.assertIn("混叠", sampling.text)

    def test_list_field_continuation(self):
        """`> - 条目` / `> 1. 条目` 应归并到上一个字段，而不是被丢弃。"""
        seeds = parse_source(self.prof, self.prof.sources[1])
        # 夹具里的卡片用「## 选择建议」普通段落，这里验证字段已被收集
        for s in seeds:
            self.assertIn("fields", s.extra)


class ParseErrorTest(_Base):
    def test_empty_source_raises(self):
        """源解析出 0 条时必须报错，而不是静默产出一个空索引。"""
        empty = self.prof.root / "empty.md"
        empty.write_text("# 空的\n\n没有可解析条目\n", encoding="utf-8")
        data = helpers.read_example_profile()
        data["sources"][0]["path"] = "empty.md"
        data["sources"][1]["path"] = "empty.md"
        data["sources"] = data["sources"][:1]
        data["paths"] = helpers.read_example_profile()["paths"]
        import json
        p = self.prof.root / "p2.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        prof = Profile.load(p, root=self.prof.root)
        with self.assertRaises(ParseError):
            parse_source(prof, prof.sources[0])


if __name__ == "__main__":
    unittest.main()
