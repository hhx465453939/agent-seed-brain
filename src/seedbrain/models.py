"""数据模型 —— 全部 dataclass，尽量不可变。

设计约束（见 SPEC §2）：
  * Python 3.9+：类型注解全部字符串化（``from __future__ import annotations``），
    运行时不做泛型求值，避免 3.9 不支持的新语法。
  * 不引入任何第三方库（含 pydantic / attrs）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── 种子 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Seed:
    """一粒种子。``text`` 是唯一的匹配输入，``grams`` 是长度缓存（用于归一化）。"""

    id: str
    name: str
    layer: str
    group: str
    one_liner: str
    text: str
    grams: int
    ref: str
    origin: str = "source"  # "source" | "addition"
    extra: dict[str, Any] = field(default_factory=dict)

    _KNOWN = (
        "id", "name", "layer", "group", "one_liner", "text", "grams", "ref", "origin",
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Seed:
        extra = {k: v for k, v in d.items() if k not in cls._KNOWN}
        return cls(
            id=str(d["id"]),
            name=str(d.get("name") or d["id"]),
            layer=str(d.get("layer", "")),
            group=str(d.get("group", "")),
            one_liner=str(d.get("one_liner", "")),
            text=str(d.get("text", "")),
            grams=int(d.get("grams") or 0),
            ref=str(d.get("ref", "")),
            origin=str(d.get("origin", "source")),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "layer": self.layer,
            "group": self.group,
            "one_liner": self.one_liner,
            "text": self.text,
            "grams": self.grams,
            "ref": self.ref,
            "origin": self.origin,
        }
        out.update(self.extra)
        return out


# ── 匹配结果 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Match:
    """一条候选。``hits`` 暴露 ``(信号, 权重)``，满足「可解释」要求（NFR-4）。"""

    seed: Seed
    total: float
    base: float
    novelty: float
    hits: tuple[tuple[str, float], ...] = ()

    def __str__(self) -> str:  # pragma: no cover - 仅调试用
        h = "  ".join(f"{g}·{w:.1f}" for g, w in self.hits[:5])
        return f"{self.total:7.1f} {self.seed.id:<28} {h}"


# ── 构建结果 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuildResult:
    total: int
    added: int          # 来自增量池的条数
    collided: int       # 增量 ID 与源库撞车、已加后缀的条数
    layers: dict[str, int] = field(default_factory=dict)
    groups: int = 0
    dropped: int = 0    # 源库内部重名合并掉的条数（不是增量撞车）

    def summary(self) -> str:
        parts = [f"{self.total} 粒种子"]
        if self.added:
            parts.append(f"其中增量 {self.added}")
        if self.collided:
            parts.append(f"{self.collided} 个增量 ID 撞车已加后缀")
        if self.dropped:
            parts.append(f"源库重名合并 {self.dropped} 条")
        return "，".join(parts)


# ── 验证 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Check:
    id: str
    name: str
    metric: str
    target: str
    ok: bool


@dataclass
class VerifyReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> bool:
        self.checks.append(check)
        return check.ok

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.ok)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "ok": self.ok,
            "checks": [
                {"id": c.id, "name": c.name, "metric": c.metric,
                 "target": c.target, "ok": c.ok}
                for c in self.checks
            ],
        }


# ── 覆盖率统计 ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Stats:
    total: int
    used: int
    by_layer: dict[str, tuple[int, int]]   # layer -> (总数, 用过数)
    blind_groups: tuple[str, ...]          # 从未被选中的分组
    top_reused: tuple[tuple[str, int], ...]

    @property
    def coverage(self) -> float:
        return self.used / self.total if self.total else 0.0
