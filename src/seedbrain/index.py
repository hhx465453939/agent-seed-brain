"""索引构建 —— 把 profile 声明的所有源编译成「等距平铺」的种子库。

三条不变量（由 verify 组守住）：

1. **不丢种子**：每种源至少解析出 1 粒，重名合并但绝不静默丢弃；
2. **ID 稳定**：已有 ID 一旦生成，增量撞车只加后缀，绝不改写（否则风味日志、
   状态记忆、外部引用全部断链）；
3. **幂等**：同一输入必得同一字节输出，CI 才能用 ``git diff --exit-code`` 拦漂移。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .additions import load_additions, merge_seeds, seed_from_addition
from .models import BuildResult, Seed
from .parse import parse_source
from .profile import Profile
from .tokenize import grams_cached

FLAT_HEADER = """# 🗂️ 种子全景索引（等距平铺 · 全员同等可见）· {label}

> **这是什么**：全库种子的**等距平铺目录**——每粒一行、同等曝光、没有「首选 / 备选」的层级差。
> **为什么要它**：人工写的「快速索引表」通常只有十几行，结构性地让绝大多数种子永远没有入口。
> **怎么用**：机器选 → `seedbrain match "<任务描述>"`（IDF 加权 top-K）；
> 人/LLM 通读 → 本文件全文，按信号词自行判断归属。
> **排序**：按层、层内按 ID 字典序——**刻意不按重要性**，杜绝任何隐含优先级。
> **规模**：{total} 粒 ｜ {by_layer}{added_note}
{incremental_hint}---
"""

INCREMENTAL_HINT = (
    "> **🌱 增量区**：带 🌱 的条目来自增量池（`seedbrain add` 写入）。\n"
    "> 它们与源库种子**同权参与匹配**，不因「新」而优先，也不因「未回填源文件」而低一等。\n\n"
)


def build(prof: Profile) -> tuple[list[Seed], BuildResult]:
    """解析全部源 + 合并增量池 → (种子列表, 构建统计)。不写文件。"""
    raw: list[Seed] = []
    for src in prof.sources:
        raw.extend(parse_source(prof, src))

    # 加层前缀（消跨层 ID 冲突）+ 层内重名加序号（绝不因重名丢种子）
    prefixed: list[Seed] = []
    for s in raw:
        prefixed.append(_with_id(s, f"{prof.prefix_of(s.layer)}-{s.id}"))
    prefixed = _disambiguate(prefixed)

    # 源库内部去重（同 ID 保留 text 更长的那条）
    deduped: dict[str, Seed] = {}
    for s in prefixed:
        cur = deduped.get(s.id)
        if cur is None or len(s.text) > len(cur.text):
            deduped[s.id] = s
    merged_dropped = len(prefixed) - len(deduped)

    base = sorted(deduped.values(), key=_sort_key(prof))

    # 合并增量池
    additions = [seed_from_addition(prof, rec) for rec in load_additions(prof)]
    seeds, collided = merge_seeds(base, additions, prof)

    # 补齐 grams 计数（增量条目已算，源条目在 parse 时已算；这里兜底）
    seeds = [_with_grams(s) for s in seeds]

    layers = Counter(s.layer for s in seeds)
    result = BuildResult(
        total=len(seeds),
        added=sum(1 for s in seeds if s.origin == "addition"),
        collided=collided,
        layers=dict(layers),
        groups=len({s.group for s in seeds}),
        dropped=merged_dropped,
    )
    return seeds, result


def write(prof: Profile, seeds: list[Seed], result: BuildResult) -> tuple[Path, Path]:
    """落盘：机器可读的 ``.jsonl`` + 人可读的 ``.md``。"""
    jsonl = prof.resolve_output(prof.paths.index_jsonl)
    md = prof.resolve_output(prof.paths.index_md)
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    md.parent.mkdir(parents=True, exist_ok=True)

    with jsonl.open("w", encoding="utf-8", newline="\n") as f:
        for s in seeds:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")

    md.write_text(_render_flat(prof, seeds, result), encoding="utf-8", newline="\n")
    return jsonl, md


def load(prof: Profile) -> list[Seed]:
    """读回索引；不存在时抛 :class:`FileNotFoundError`。"""
    path = prof.resolve_output(prof.paths.index_jsonl)
    if not path.is_file():
        raise FileNotFoundError(f"索引不存在：{path}（先跑 build）")
    seeds: list[Seed] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            seeds.append(Seed.from_dict(json.loads(line)))
    return seeds


# ── 内部 ──────────────────────────────────────────────────────────────────


def _with_id(seed: Seed, new_id: str) -> Seed:
    d = seed.to_dict()
    d["id"] = new_id
    return Seed.from_dict(d)


def _with_grams(seed: Seed) -> Seed:
    g = len(grams_cached(seed.text))
    if g == seed.grams:
        return seed
    d = seed.to_dict()
    d["grams"] = g
    return Seed.from_dict(d)


def _disambiguate(seeds: list[Seed]) -> list[Seed]:
    """层内重名加 ``-2`` ``-3``…：重名不等于丢弃。"""
    seen: Counter = Counter()
    out: list[Seed] = []
    for s in seeds:
        seen[s.id] += 1
        out.append(s if seen[s.id] == 1 else _with_id(s, f"{s.id}-{seen[s.id]}"))
    return out


def _sort_key(prof: Profile):
    """稳定排序：先按层（profile 声明的顺序），再按 ID 字典序。"""
    order = {layer: i for i, layer in enumerate(prof.layer_order)}
    return lambda s: (order.get(s.layer, len(order)), s.id)


def _render_flat(prof: Profile, seeds: list[Seed], result: BuildResult) -> str:
    by_layer: dict[str, list[Seed]] = {}
    for s in seeds:
        by_layer.setdefault(s.layer, []).append(s)

    by_layer_text = " ｜ ".join(
        f"{prof.layers[layer].label or layer} {len(by_layer[layer])}"
        for layer in prof.layer_order
        if layer in by_layer
    )
    added_note = f" ｜ 🌱 增量 {result.added} 粒" if result.added else ""

    parts = [FLAT_HEADER.format(
        label=prof.label or prof.name,
        total=result.total,
        by_layer=by_layer_text,
        added_note=added_note,
        incremental_hint=INCREMENTAL_HINT if result.added else "",
    )]

    for layer in prof.layer_order:
        items = by_layer.get(layer)
        if not items:
            continue
        spec = prof.layers[layer]
        ref = _layer_ref(prof, layer)
        parts.append(f"## {spec.label or layer}（{len(items)} 粒）\n")
        parts.append(f"目录：`{ref}`\n")
        parts.append("| id | 名称 | 一句话 |")
        parts.append("|---|---|---|")
        for s in items:
            mark = "🌱 " if s.origin == "addition" else ""
            one = s.one_liner.replace("|", "／")
            parts.append(f"| `{s.id}` | {mark}{s.name} | {one} |")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _layer_ref(prof: Profile, layer: str) -> str:
    for src in prof.sources:
        if src.layer == layer:
            return src.path or (src.dir.rstrip("/") + "/")
    return layer
