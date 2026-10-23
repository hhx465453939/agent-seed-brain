"""命令行入口 —— 让能力可脚本化（CI / shell / 任意 harness）。

退出码约定（SPEC §6）：

* ``0`` 成功
* ``1`` 校验失败（``verify`` 有 FAIL）
* ``2`` 输入非法（未知层、ref 不存在、疑似重复、ID 冲突）
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from . import __version__
from .profile import Profile, ProfileError


def _out(msg: str = "") -> None:
    print(msg)


# ── profile 发现 ──────────────────────────────────────────────────────────


def _load_profile(args: argparse.Namespace) -> Profile:
    """``--profile`` → ``./seedbrain.json`` → 报错。"""
    given = getattr(args, "profile", None)
    if given:
        return Profile.load(given, getattr(args, "root", None))
    local = Path("seedbrain.json")
    if local.is_file():
        return Profile.load(local, getattr(args, "root", None))
    raise ProfileError(
        "找不到 profile：请用 --profile 指定，或在当前目录放 seedbrain.json"
    )


# ── 子命令 ────────────────────────────────────────────────────────────────


def cmd_build(args: argparse.Namespace) -> int:
    from . import SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    result = brain.build()
    if not args.quiet:
        _out(f"✓ {result.summary()}")
        by_layer = " ｜ ".join(f"{k} {v}" for k, v in result.layers.items())
        _out(f"  分层：{by_layer}")
        _out(f"  → {brain.profile.paths.index_jsonl}")
        _out(f"  → {brain.profile.paths.index_md}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    from . import SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    matches, quotas, n_hit = brain.match(args.task, k=args.k, debug=True)
    if args.json:
        _out(json.dumps([{
            "id": m.seed.id,
            "name": m.seed.name,
            "layer": m.seed.layer,
            "score": round(m.total, 2),
            "base": round(m.base, 2),
            "novelty": round(m.novelty, 3),
            "hits": [[g, round(w, 2)] for g, w in m.hits],
            "ref": m.seed.ref,
        } for m in matches], ensure_ascii=False, indent=2))
        return 0

    _out(f"\n任务：{args.task}")
    _out(f"扫描 {len(brain.seeds)} 粒 ｜ 命中 {n_hit} ｜ 跨层配额 "
         + " ".join(f"{k}<={v}" for k, v in quotas.items()))
    if not matches:
        _out("  （零命中）换更具体的领域词，或直接通读全景索引。")
        return 0

    _out(f"\n{'#':>2}  {'层':<10}{'得分':>7} {'新颖':>5}  {'id':<26} 命中信号")
    _out("─" * 100)
    for i, m in enumerate(matches, 1):
        from .tokenize import dedupe_hits
        hits = "  ".join(f"{g}·{w:.1f}" for g, w in dedupe_hits(list(m.hits))[:5])
        _out(f"{i:>2}  {m.seed.layer:<10}{m.total:>7.1f} {m.novelty:>5.2f}  {m.seed.id[:25]:<26} {hits}")
        _out(f"    └ {m.seed.name} ｜ {m.seed.one_liner[:62]}")
        _out(f"      深挖 {m.seed.ref}")
    _out("\n下一步：挑定一个 → 读 ref 深挖 → 交付后 `seedbrain pick <id>`")
    return 0


def cmd_pick(args: argparse.Namespace) -> int:
    from . import InvalidInputError, SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    try:
        rec = brain.pick(args.id, score=args.score, note=args.note)
    except InvalidInputError as exc:
        _out(f"✗ {exc}")
        return 2
    _out(f"✓ 已记录 {args.id} 第 {rec['count']} 次")
    _out(f"  → {brain.profile.paths.state} ｜ {brain.profile.norms.decay_tau_days:.0f}d 内会自然下沉")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    from . import DuplicateError, InvalidInputError, SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    signals = [x.strip() for x in __import__("re").split(r"[,，、·/|]", args.signals or "") if x.strip()]
    try:
        seed = brain.add(
            name=args.name, layer=args.layer, signals=signals,
            one_liner=args.one_liner, ref=args.ref, seed_id=args.id,
            force=args.force, dry_run=args.dry_run,
        )
    except DuplicateError as exc:
        _out(f"⚠ {exc}")
        _out("  确认是新种子请加 --force；否则先复用已有那粒。")
        return 2
    except InvalidInputError as exc:
        _out(f"✗ {exc}")
        return 2

    if args.dry_run:
        _out(json.dumps(seed.to_dict(), ensure_ascii=False, indent=2))
        _out("\n(dry-run：未写入)")
        return 0
    result = brain.build()
    _out(f"✓ 已加入增量池：{seed.id} ｜ {seed.name}")
    _out(f"  {result.summary()}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from . import SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    groups = tuple(args.group) if args.group else ("schema", "core", "content")
    report = brain.verify(groups=groups)

    for c in report.checks:
        flag = "PASS" if c.ok else "FAIL"
        _out(f"  [{flag}] {c.id:<5} {c.name:<26} {c.metric:<44} 门槛 {c.target}")
    _out("─" * 100)
    _out(f"  结果：{report.passed}/{len(report.checks)} 通过"
         + ("" if report.ok else f" ｜ {report.failed} 项失败"))

    if args.evidence:
        path = Path(args.evidence)
        path.parent.mkdir(parents=True, exist_ok=True)
        # write_text(newline=) 是 Python 3.10+；用 Path.open 兼容 3.9。
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(_render_evidence(brain, report))
        _out(f"\n✓ evidence 已写入 {path}")

    if args.json:
        _out(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


def cmd_stats(args: argparse.Namespace) -> int:
    from . import SeedBrain

    brain = SeedBrain.load(args.profile, args.root)
    st = brain.stats()
    _out(f"\n{brain.profile.label} · 覆盖率审计")
    _out(f"全库 {st.total} 粒 ｜ 曾使用 {st.used} 粒 ｜ 覆盖率 {st.coverage:.1%}")
    for layer, (total, used) in st.by_layer.items():
        _out(f"  {layer:<12}{used:>4}/{total:<4} {100 * used / max(1, total):>5.1f}%")
    _out(f"\n零使用分组：{len(st.blind_groups)}")
    for g in st.blind_groups[:10]:
        _out(f"  · {g[:48]}")
    if st.top_reused:
        _out("\n复用最多（警惕正反馈收敛）：")
        for sid, n in st.top_reused:
            _out(f"  {n:>2}× {sid}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """打印合并后的最终配置 —— 继承的调试入口。

    没有它，出问题时只能靠猜「这个阈值到底来自 base 还是自己写的」。
    继承链只允许单层是有意的：链越长，「这值从哪来」越难回答。
    """
    from . import SeedBrain

    prof = SeedBrain.load(args.profile, args.root).profile
    if args.chain:
        _out(str(prof.src_path))
        for rel in prof.extends_chain:
            _out(f"  ← {rel}")
        if not prof.extends_chain:
            _out("  （无 extends）")
        return 0
    _out(json.dumps(prof.raw, ensure_ascii=False, indent=2))
    return 0


# ── evidence 渲染 ─────────────────────────────────────────────────────────


def _render_evidence(brain, report) -> str:
    import time

    lines = [
        f"# 🧪 {brain.profile.label} · 无偏分布验证 Evidence",
        "",
        f"> **生成**：{time.strftime('%Y-%m-%d %H:%M')} ｜ **套件** `seedbrain verify` ｜ "
        f"**版本** `v{__version__}`",
        f"> **被测**：`{brain.profile.paths.index_jsonl}`（{len(brain.seeds)} 粒）",
        f"> **复跑**：`seedbrain verify --profile {brain.profile.src_path} --evidence <path>`",
        "",
        f"## 结论：{report.passed}/{len(report.checks)} 项通过"
        + ("" if report.ok else f"，**{report.failed} 项失败**"),
        "",
        "| # | 检查项 | 实测 | 门槛 | 判定 |",
        "|---|---|---|---|---|",
    ]
    for c in report.checks:
        lines.append(f"| {c.id} | {c.name} | {c.metric} | {c.target} | {'✅' if c.ok else '❌'} |")
    lines.append("")
    return "\n".join(lines)


# ── 参数解析 ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="seedbrain",
        description="把任意领域的知识编译成可无偏检索、可增量演进的种子库。",
    )
    ap.add_argument("--version", action="version", version=f"seedbrain {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--profile", help="profile JSON 路径（默认 ./seedbrain.json）")
        p.add_argument("--root", help="知识库根目录（默认 profile 所在目录的父级）")

    p = sub.add_parser("build", help="解析全部源 → 等距平铺索引")
    common(p)
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("match", help="任务描述 → top-K 候选")
    common(p)
    p.add_argument("task")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_match)

    p = sub.add_parser("pick", help="记录一次使用")
    common(p)
    p.add_argument("id")
    p.add_argument("--score", type=int, default=0, choices=[0, 1, 2, 3, 4, 5])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_pick)

    p = sub.add_parser("add", help="新增一粒种子到增量池（不改源文件）")
    common(p)
    p.add_argument("--name", required=True)
    p.add_argument("--layer", required=True)
    p.add_argument("--signals", default="")
    p.add_argument("--one-liner", dest="one_liner", default="")
    p.add_argument("--ref", default="")
    p.add_argument("--id", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("verify", help="跑门槛断言套件")
    common(p)
    p.add_argument("--evidence", help="把报告写成 Markdown")
    p.add_argument("--json", action="store_true")
    p.add_argument("--group", action="append", choices=["schema", "core", "content"])
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("stats", help="覆盖率审计")
    common(p)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("config", help="打印合并后的最终配置（继承调试）")
    common(p)
    p.add_argument("--chain", action="store_true", help="只打印继承链")
    p.set_defaults(func=cmd_config)

    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ProfileError as exc:
        _out(f"✗ profile 非法：{exc}")
        return 2
    except FileNotFoundError as exc:
        _out(f"✗ {exc}")
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
