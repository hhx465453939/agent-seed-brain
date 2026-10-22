#!/usr/bin/env python3
"""最小可用示例 —— 5 行拿到候选。

运行（在仓库根）::

    PYTHONPATH=src python examples/minimal.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from seedbrain import SeedBrain  # noqa: E402

brain = SeedBrain.load(ROOT / "profiles" / "example.json")
brain.build()

for m in brain.match("降维压缩，矩阵分解选型", k=5):
    hits = "  ".join(f"{g}·{w:.1f}" for g, w in m.hits[:3])
    print(f"{m.total:6.1f}  {m.seed.id:<24} {hits}")

# 想记录一次使用（让它在 14 天内自然下沉）：
# brain.pick("tl-矩阵分解", score=5, note="一次过")
