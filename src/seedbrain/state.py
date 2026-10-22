"""使用状态 —— 「记忆快照」的落地位置。

存什么：``{seed_id: {count, last_ts, scores[], name, layer, note}}``。
为什么不全量入库：使用历史因人而异，提交会让每次 ``pick`` 产生噪声 diff。
损坏时优雅退化（返回空状态），绝不阻塞主流程。
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from .models import Seed, Stats
from .profile import Profile


def state_path(prof: Profile) -> Path:
    return prof.resolve_output(prof.paths.state)


def load(prof: Profile) -> dict:
    path = state_path(prof)
    if not path.is_file():
        return {"picks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"picks": {}}
    if not isinstance(data, dict):
        return {"picks": {}}
    data.setdefault("picks", {})
    return data


def save(prof: Profile, state: dict) -> Path:
    path = state_path(prof)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def record(
    state: dict,
    seed: Seed,
    score: int = 0,
    note: str = "",
    now: float | None = None,
) -> dict:
    """记录一次使用，返回该种子的记录（原地修改 state）。"""
    now = time.time() if now is None else now
    picks = state.setdefault("picks", {})
    rec = picks.setdefault(seed.id, {"count": 0, "last_ts": 0, "scores": []})
    rec["count"] = int(rec.get("count", 0)) + 1
    rec["last_ts"] = now
    if score:
        rec["scores"] = (list(rec.get("scores") or []) + [int(score)])[-20:]
    if note:
        rec["note"] = note[:200]
    rec["name"] = seed.name
    rec["layer"] = seed.layer
    return rec


def summarize(prof: Profile, seeds: list[Seed], state: dict) -> Stats:
    """覆盖率审计：哪些层/分组从未被选中，哪些被复用最多。"""
    picks = state.get("picks", {})

    by_layer: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_group: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for s in seeds:
        by_layer[s.layer][0] += 1
        by_group[s.group][0] += 1
        if s.id in picks:
            by_layer[s.layer][1] += 1
            by_group[s.group][1] += 1

    blind = tuple(g for g, (total, used) in sorted(by_group.items()) if used == 0)
    top = tuple(sorted(((sid, int(r.get("count", 0))) for sid, r in picks.items()),
                       key=lambda kv: -kv[1])[:8])

    return Stats(
        total=len(seeds),
        used=sum(1 for s in seeds if s.id in picks),
        by_layer={k: (v[0], v[1]) for k, v in sorted(by_layer.items())},
        blind_groups=blind,
        top_reused=top,
    )


def usage_counts(state: dict) -> Counter:
    """每粒种子被用了几次（供统计与调试）。"""
    return Counter({sid: int(r.get("count", 0)) for sid, r in state.get("picks", {}).items()})
