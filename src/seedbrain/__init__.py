"""seedbrain —— 把任意领域的知识编译成可无偏检索、可增量演进的种子库。

用法（3 行）::

    from seedbrain import SeedBrain
    brain = SeedBrain.load("profiles/example.json")
    for m in brain.match("降维压缩，矩阵分解选型", k=5):
        print(m.total, m.seed.id, m.hits[:2])

设计边界见 ``docs/en/methodology.md`` 与 ``tasks/CHG-20261022-seed-brain-sdk/``。
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .models import BuildResult, Check, Match, Seed, Stats, VerifyReport
from .profile import Profile, ProfileError

__version__ = "0.3.0"
__all__ = [
    "SeedBrain",
    "Seed",
    "Match",
    "BuildResult",
    "VerifyReport",
    "Check",
    "Stats",
    "Profile",
    "ProfileError",
    "SeedBrainError",
    "InvalidInputError",
    "DuplicateError",
    "__version__",
]


# ── 异常 ──────────────────────────────────────────────────────────────────


class SeedBrainError(RuntimeError):
    """本库所有可预期错误的基类。"""


class InvalidInputError(SeedBrainError):
    """输入非法：未知层、ref 不存在、ID 冲突等。"""


class DuplicateError(SeedBrainError):
    """疑似重复（包含度 ≥ 阈值）。"""


# ── 门面 ──────────────────────────────────────────────────────────────────


class SeedBrain:
    """一个 profile 上的全部能力。

    不可变约定：``build()`` 之后 :attr:`seeds` 是只读快照；``add()`` 会自动重建。
    """

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self._seeds: list[Seed] | None = None
        self._state: dict | None = None

    @classmethod
    def load(cls, profile: str | Path, root: str | Path | None = None) -> SeedBrain:
        return cls(Profile.load(profile, root))

    # ── 读 ────────────────────────────────────────────────────────────

    @property
    def seeds(self) -> list[Seed]:
        """当前种子快照（懒加载：未 build 过则从索引读）。"""
        if self._seeds is None:
            from .index import load
            self._seeds = load(self.profile)
        return self._seeds

    @property
    def state(self) -> dict:
        if self._state is None:
            from .state import load
            self._state = load(self.profile)
        return self._state

    # ── 写 ────────────────────────────────────────────────────────────

    def build(self) -> BuildResult:
        from .index import build, write

        seeds, result = build(self.profile)
        write(self.profile, seeds, result)
        self._seeds = seeds
        return result

    def match(self, task: str, k: int = 8, *, debug: bool = False):
        """任务描述 → top-K。

        ``debug=True`` 时返回 ``(matches, quotas, 命中数)``，否则只返回 matches。
        """
        from .score import rank

        matches, quotas, n_hit = rank(self.profile, self.seeds, task, k, state=self.state)
        return (matches, quotas, n_hit) if debug else matches

    def pick(self, seed_id: str, score: int = 0, note: str = "") -> dict:
        from .state import record, save

        by_id = {s.id: s for s in self.seeds}
        if seed_id not in by_id:
            near = [k for k in by_id if seed_id in k][:5]
            raise InvalidInputError(
                f"未知 id：{seed_id}" + (f"（相近：{', '.join(near)}）" if near else "（先跑 match 拿 id）")
            )
        rec = record(self.state, by_id[seed_id], score=score, note=note)
        save(self.profile, self.state)
        return rec

    def add(
        self,
        *,
        name: str,
        layer: str,
        signals: Sequence[str] = (),
        one_liner: str = "",
        ref: str = "",
        seed_id: str = "",
        force: bool = False,
        dry_run: bool = False,
    ) -> Seed:
        """新增一粒种子到增量池（不修改源文件）。

        三道护栏（源自上游实测事故）：

        1. ``layer`` 必须已在 profile 声明；
        2. ``ref`` 必须存在且不越界 —— 猜错的路径会变成静默断链；
        3. 同层查重（包含度 ≥ 阈值）—— Jaccard 会被并集分母稀释到永不告警。
        """
        import time

        from .additions import append_addition, find_duplicate, seed_from_addition

        name = (name or "").strip()
        if not name:
            raise InvalidInputError("--name 不能为空")
        if layer not in self.profile.layers:
            raise InvalidInputError(
                f"未知层：{layer}；本 profile 可选 {sorted(self.profile.layers)}"
            )

        ref = (ref or "").strip() or self.profile.paths.additions
        if not self.profile.resolve(ref).exists() and not force:
            raise InvalidInputError(
                f"--ref 指向的文件不存在：{ref}\n"
                f"  深挖路径必须是 root 内已存在的文件（不要写猜测路径）。确实要留空请加 --force。"
            )

        rec = {
            "name": name,
            "layer": layer,
            "signals": list(signals),
            "one_liner": one_liner.strip(),
            "ref": ref,
            "added_at": time.strftime("%Y-%m-%d"),
            "origin": "addition",
        }
        if seed_id:
            rec["id"] = seed_id

        cand = seed_from_addition(self.profile, rec)

        existing = {s.id: s for s in self.seeds}
        if cand.id in existing and not force:
            raise InvalidInputError(
                f"ID 已存在：{cand.id}（确认新增请加 --force，会自动加后缀）"
            )

        if not force and existing:
            dup, sim = find_duplicate(
                list(existing.values()), cand, self.profile.norms.dup_threshold
            )
            if dup is not None:
                raise DuplicateError(
                    f"疑似重复：{dup.id}（{dup.name}）包含度={sim:.2f} ≥ {self.profile.norms.dup_threshold}"
                )

        if dry_run:
            return cand

        append_addition(self.profile, rec)
        return cand

    # ── 验 ────────────────────────────────────────────────────────────

    def verify(self, groups: Sequence[str] = ("schema", "core", "content")) -> VerifyReport:
        from .verify import run

        return run(self.profile, self.seeds, self.state, groups)

    def stats(self) -> Stats:
        from .state import summarize

        return summarize(self.profile, self.seeds, self.state)
