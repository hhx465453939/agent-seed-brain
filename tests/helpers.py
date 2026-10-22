"""测试基座 —— 在临时目录里造一个**完整自包含**的最小仓库。

为什么要这样（踩过的坑）：
``Profile.resolve()`` 对知识源强制 root 内（防路径穿越）。若把「源留在仓库、
输出写到 tmp」，root 概念会撕裂 —— 测试撞越界，CLI 还会把 root 推断成 tmp 的父级
而找不到源。所以测试要么完全在仓库内跑（污染工作区），要么造一个完整临时仓库。
选后者。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

EXAMPLE_PROFILE = ROOT / "profiles" / "example.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "mini-domain"

#: 临时仓库内 fixture 的相对位置（测试里写 ref 用这个前缀）
FIXTURE_REL = "mini"


def isolation_ok() -> bool:
    """CI 与本地都要求能写临时目录。"""
    try:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x"
            p.write_text("ok", encoding="utf-8")
            return p.read_text(encoding="utf-8") == "ok"
    except Exception:  # noqa: BLE001
        return False


def read_example_profile() -> dict[str, Any]:
    return json.loads(EXAMPLE_PROFILE.read_text(encoding="utf-8"))


def make_tmp_repo(out_dir: Path) -> Path:
    """在 ``out_dir/repo`` 造一个自包含仓库：fixture 源 + profile + out/ 输出位。

    返回仓库根。重复调用是幂等的（fixture 已存在则跳过复制）。
    """
    repo = out_dir / "repo"
    mini = repo / FIXTURE_REL
    if not (mini / "tools.md").is_file():
        mini.mkdir(parents=True, exist_ok=True)
        shutil.copytree(FIXTURE_DIR, mini, dirs_exist_ok=True)

    data = read_example_profile()
    # 源指向仓库内的 fixture 副本
    data["sources"][0]["path"] = f"{FIXTURE_REL}/tools.md"
    data["sources"][1]["dir"] = f"{FIXTURE_REL}/cards"
    # 输出也落在仓库内（相对 root，跨平台一致）
    data["paths"] = {
        "index_jsonl": "out/seed-index.jsonl",
        "index_md": "out/SEED-INDEX.md",
        "additions": "out/seed-additions.jsonl",
        "state": "out/.seed-usage.json",
    }
    (repo / "seedbrain.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return repo


def make_brain(out_dir: Path):
    """返回一个跑在临时仓库里的 SeedBrain。``root`` 就是那个临时仓库。"""
    from seedbrain import SeedBrain

    out_dir.mkdir(parents=True, exist_ok=True)
    repo = make_tmp_repo(out_dir)
    return SeedBrain.load(repo / "seedbrain.json", root=repo)


def make_brain_with(brain, **overrides):
    """在现有 brain 的 profile 上覆盖顶层字段，返回新 brain（root 不变）。"""
    from seedbrain import SeedBrain

    src = Path(str(brain.profile.src_path))
    data = json.loads(src.read_text(encoding="utf-8"))
    data.update(overrides)
    p = src.with_name("seedbrain-override.json")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return SeedBrain.load(p, root=brain.profile.root)
