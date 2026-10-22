"""增量池 —— 智能体在会话中新增种子时的唯一写入路径。

为什么不直接改源文件：

* 源库是**人工策展产物**（有分层、格式、字段完整性约束），脚本盲插会破坏它；
* 增量池可审计、可回滚、可批量审阅后再回填；
* 回填后从增量池删除那一行，``build`` 结果不变（幂等）。

三条硬约束（由 verify 的 T10/T12 守住）：

1. **已有 ID 绝不改写** —— 只加后缀，不覆盖；
2. **增量结果 ≡ 全量重建** —— split-half 拆库验证；
3. **``ref`` 必须存在且不越界** —— 防静默断链与路径穿越。
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Seed
from .profile import Profile
from .tokenize import grams


def additions_path(prof: Profile) -> Path:
    return prof.resolve_output(prof.paths.additions)


def load_additions(prof: Profile) -> list[dict]:
    """读增量池。文件缺失 / 单行损坏都不阻塞主流程——写入路径不能成为单点故障。"""
    path = additions_path(prof)
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("name"):
            out.append(rec)
    return out


def append_addition(prof: Profile, rec: dict) -> Path:
    path = additions_path(prof)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def seed_from_addition(prof: Profile, rec: dict) -> Seed:
    """把一条增量记录补全成与源库同构的 Seed。"""
    layer = str(rec.get("layer") or "")
    prefix = prof.prefix_of(layer)
    raw_id = str(rec.get("id") or _slug(rec["name"]))
    sid = raw_id if raw_id.startswith(f"{prefix}-") else f"{prefix}-{_slug(raw_id)}"

    signals = [str(x) for x in (rec.get("signals") or [])]
    one = str(rec.get("one_liner") or "")
    text = " ".join([str(rec["name"])] + signals + ([one] if one else []))
    return Seed(
        id=sid,
        name=str(rec["name"]),
        layer=layer,
        group=str(rec.get("group") or "增量区"),
        one_liner=one[:90],
        text=text,
        grams=len(grams(text)),
        ref=str(rec.get("ref") or prof.paths.additions),
        origin="addition",
        extra={"added_at": str(rec.get("added_at") or "")},
    )


def merge_seeds(base: list[Seed], additions: list[Seed], prof: Profile | None = None) -> tuple[list[Seed], int]:
    """把增量并进基础库。

    返回 ``(合并后列表, 撞车次数)``。撞车的条目**保留**，只是 ID 加后缀。
    """
    merged: dict[str, Seed] = {s.id: s for s in base}
    used = set(merged)
    collided = 0

    for a in additions:
        sid = a.id
        if sid in used:
            n = 2
            while f"{sid}-{n}" in used:
                n += 1
            d = a.to_dict()
            d["id"] = f"{sid}-{n}"
            a = Seed.from_dict(d)
            sid = a.id
            collided += 1
        merged[sid] = a
        used.add(sid)

    order = {layer: i for i, layer in enumerate(prof.layer_order)} if prof else {}
    out = sorted(merged.values(), key=lambda s: (order.get(s.layer, len(order)), s.id))
    return out, collided


def find_duplicate(seeds: list[Seed], cand: Seed, threshold: float = 0.75) -> tuple[Seed | None, float]:
    """同层内按**包含度**找最相似的已有种子。

    为什么不用 Jaccard：新种子通常只有名字 + 几个信号（短），已有卡片文本很长，
    Jaccard 的并集分母会把相似度稀释到 0.05，于是查重永远不告警。
    包含度 ``|A∩B| / min(|A|,|B|)`` 才回答得了「这粒是不是已有那粒的别名」。
    """
    from .tokenize import grams_cached

    cg = set(grams_cached(cand.text))
    if not cg:
        return None, 0.0

    best: Seed | None = None
    best_score = 0.0
    for s in seeds:
        if s.layer != cand.layer or s.id == cand.id:
            continue
        sg = set(grams_cached(s.text))
        if not sg:
            continue
        score = len(cg & sg) / (min(len(cg), len(sg)) or 1)
        if score > best_score:
            best, best_score = s, score
    return (best if best_score >= threshold else None), best_score


def _slug(text: str) -> str:
    import re
    text = re.sub(r"[（）()《》「」【】\[\]：:；;，,。.、/\\|\"'’]", " ", str(text))
    text = re.sub(r"\s+", "-", text.strip())
    return re.sub(r"-{2,}", "-", text).strip("-").lower()
