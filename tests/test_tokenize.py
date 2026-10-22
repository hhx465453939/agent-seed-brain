"""tokenize 的单元测试 —— 分词是匹配的底座，错了上层全错。"""

import unittest

import helpers  # noqa: F401  （设置 sys.path）
from seedbrain import tokenize as tk


class GramsTest(unittest.TestCase):
    def setUp(self):
        tk.clear_cache()

    def test_cjk_bigram_and_trigram(self):
        g = tk.grams("降维压缩")
        self.assertIn("降维", g)
        self.assertIn("压缩", g)
        # 3-gram 存在但权重更低
        self.assertIn("降维压", g)
        self.assertGreater(g["降维"], g["降维压"])

    def test_ascii_lowercased(self):
        g = tk.grams("SVD decomposition")
        self.assertIn("svd", g)
        self.assertIn("decomposition", g)
        self.assertNotIn("SVD", g)

    def test_stopwords_excluded(self):
        g = tk.grams("the style of art")
        for w in ("the", "style", "of", "art"):
            self.assertNotIn(w, g)

    def test_cache_returns_same_object(self):
        a = tk.grams_cached("采样定理")
        b = tk.grams_cached("采样定理")
        self.assertIs(a, b)

    def test_cache_can_be_cleared(self):
        a = tk.grams_cached("采样定理")
        tk.clear_cache()
        b = tk.grams_cached("采样定理")
        self.assertIsNot(a, b)
        self.assertEqual(a, b)


class IdfTest(unittest.TestCase):
    def setUp(self):
        tk.clear_cache()

    def test_idf_monotonic_in_df(self):
        """df 越小 → idf 越大。这是 T4a 断言的算法依据。"""
        texts = ["甲乙", "甲乙", "甲乙", "丙丁"]
        idf = tk.build_idf(texts)
        self.assertGreater(idf["丙丁"], idf["甲乙"])

    def test_idf_always_positive(self):
        idf = tk.build_idf(["只有一个"])
        self.assertTrue(all(v > 0 for v in idf.values()))

    def test_empty_corpus(self):
        self.assertEqual(tk.build_idf([]), {})


class IntersectTest(unittest.TestCase):
    def test_returns_weights_desc(self):
        left = {"a": 1.0, "b": 1.0}
        right = {"a": 1.0, "b": 1.0}
        idf = {"a": 1.0, "b": 3.0}
        hits = tk.intersect_weights(left, right, idf, limit=5)
        self.assertEqual(hits[0][0], "b")
        self.assertGreater(hits[0][1], hits[1][1])

    def test_no_idf_means_uniform(self):
        hits = tk.intersect_weights({"a": 1.0}, {"a": 1.0}, None)
        self.assertEqual(hits, [("a", 1.0)])

    def test_limit_respected(self):
        left = {c: 1.0 for c in "abcdef"}
        hits = tk.intersect_weights(left, left, None, limit=3)
        self.assertEqual(len(hits), 3)

    def test_empty_on_disjoint(self):
        self.assertEqual(tk.intersect_weights({"a": 1.0}, {"b": 1.0}, None), [])


class DedupeTest(unittest.TestCase):
    def test_shorter_substring_hidden(self):
        hits = [("条件数", 5.0), ("条件", 2.0), ("件数", 1.0)]
        out = [g for g, _ in tk.dedupe_hits(hits)]
        self.assertIn("条件数", out)
        self.assertNotIn("条件", out)
        self.assertNotIn("件数", out)

    def test_unrelated_kept(self):
        hits = [("降维", 2.0), ("压缩", 1.5)]
        self.assertEqual(len(tk.dedupe_hits(hits)), 2)


if __name__ == "__main__":
    unittest.main()
