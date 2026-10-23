"""Profile —— 领域差异的唯一入口。

整个 SDK 不包含「领域」这个概念，只有 profile。新增一个领域 = 写一份 JSON，
不改任何 Python（SPEC E2）。这是本项目的核心抽象，也是最容易设计过度的位置，
所以 schema 里只放**已经在两个领域验证过**的差异（见 HEALTH §5「抽象过度」风险）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

#: 包内数据目录（builtin: 引用的落地位置）。
#: 为什么放包里而不是仓库 profiles/：领域仓库要能 `extends: "builtin:base"`，
#: 而包内资源随 SDK 版本走 —— 零复制、零漂移、可移植。
DATA_DIR = Path(__file__).resolve().parent / "data"


class ProfileError(ValueError):
    """profile 非法 —— 明确报错，绝不静默产出一个空索引。"""


# ── 子结构 ────────────────────────────────────────────────────────────────


@dataclass
class Source:
    """一个知识源。``table`` = 单行速查总库；``card`` = 卡片目录。"""

    kind: str
    layer: str
    path: str = ""
    dir: str = ""
    group_re: re.Pattern | None = None
    entry_re: re.Pattern | None = None
    aux_re: re.Pattern | None = None
    title_re: re.Pattern | None = None
    field_re: re.Pattern | None = None
    list_re: re.Pattern | None = None
    template_parts: list[str] = field(default_factory=list)


@dataclass
class LayerSpec:
    prefix: str
    quota: float
    label: str = ""


@dataclass
class Paths:
    index_jsonl: str = "seed-index.jsonl"
    index_md: str = "SEED-INDEX.md"
    additions: str = "seed-additions.jsonl"
    state: str = ".seed-usage.json"


@dataclass
class Norms:
    decay_tau_days: float = 14.0
    count_penalty: float = 0.5
    max_hits: int = 5
    gram_w2: float = 1.0
    gram_w3: float = 0.35
    dup_threshold: float = 0.75


@dataclass
class VerifySpec:
    probes: list[str] = field(default_factory=list)
    generic_fill: list[str] = field(default_factory=list)
    legacy_shelf: list[str] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)
    content: dict[str, Any] = field(default_factory=dict)


# ── Profile ───────────────────────────────────────────────────────────────


@dataclass
class Profile:
    name: str
    label: str
    sources: list[Source]
    layers: dict[str, LayerSpec]
    paths: Paths
    norms: Norms
    verify: VerifySpec
    schema_version: int = SCHEMA_VERSION
    root: Path = field(default_factory=lambda: Path.cwd())
    src_path: Path | None = None
    #: `extends` 继承链（不含自身），供 `config --show` 与断言使用
    extends_chain: list[str] = field(default_factory=list)
    #: 合并后的原始 dict（`config --show` 直接输出它，避免再转一次）
    raw: dict = field(default_factory=dict)
    #: 探针来源（`probes_ref` 展开后）：{"ref": ..., "pool": N, "local": M}
    probes_source: dict = field(default_factory=dict)

    # ── 加载 ──────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path, root: str | Path | None = None) -> Profile:
        """从 JSON 读入并完成全部校验。

        **root 推断顺序**（早期版本硬假设 ``<repo>/profiles/x.json``，
        把 default 写死为 ``p.parent.parent``，导致 profile 直接放在仓库根时
        源路径全部找不到）：

        1. 显式参数 ``root``；
        2. profile 内的 ``"root"`` 字段（相对 profile 位置）；
        3. 父目录名叫 ``profiles`` → 取上一级（单仓库多 profile 的常见布局）；
        4. 否则取 profile 所在目录。
        """
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise ProfileError(f"profile 不存在：{p}")

        # extends 在此处解析：递归合并 + 循环检测（见 _load_merged）。
        data, chain = _load_merged(p)
        data = _apply_probes_ref(data, p.parent)

        if root:
            base = Path(root).expanduser().resolve()
        elif data.get("root"):
            base = (p.parent / str(data["root"])).resolve()
        elif p.parent.name == "profiles":
            base = p.parent.parent
        else:
            base = p.parent
        prof = cls._from_dict(data, base, p)
        prof.extends_chain = list(chain)
        prof.raw = data
        prof.probes_source = dict((data.get("verify") or {}).get("_source") or {})
        prof.validate()
        return prof

    @classmethod
    def _from_dict(cls, d: dict[str, Any], root: Path, src: Path) -> Profile:
        layers: dict[str, LayerSpec] = {}
        for name, spec in (d.get("layers") or {}).items():
            if not isinstance(spec, dict):
                raise ProfileError(f"layers.{name} 必须是对象")
            layers[name] = LayerSpec(
                prefix=str(spec.get("prefix") or ""),
                quota=float(spec.get("quota", 0.0)),
                label=str(spec.get("label", "")),
            )

        sources: list[Source] = []
        for raw in d.get("sources") or []:
            sources.append(Source(
                kind=str(raw.get("kind", "")),
                layer=str(raw.get("layer", "")),
                path=str(raw.get("path", "")),
                dir=str(raw.get("dir", "")),
                group_re=_compile(raw.get("group_re"), "group_re"),
                entry_re=_compile(raw.get("entry_re"), "entry_re"),
                aux_re=_compile(raw.get("aux_re"), "aux_re"),
                title_re=_compile(raw.get("title_re"), "title_re"),
                field_re=_compile(raw.get("field_re"), "field_re"),
                list_re=_compile(raw.get("list_re"), "list_re"),
                template_parts=[str(x) for x in (raw.get("template_parts") or [])],
            ))

        p = d.get("paths") or {}
        paths = Paths(
            index_jsonl=str(p.get("index_jsonl", Paths.index_jsonl)),
            index_md=str(p.get("index_md", Paths.index_md)),
            additions=str(p.get("additions", Paths.additions)),
            state=str(p.get("state", Paths.state)),
        )

        n = d.get("norms") or {}
        norms = Norms(
            decay_tau_days=float(n.get("decay_tau_days", Norms.decay_tau_days)),
            count_penalty=float(n.get("count_penalty", Norms.count_penalty)),
            max_hits=int(n.get("max_hits", Norms.max_hits)),
            gram_w2=float(n.get("gram_w2", Norms.gram_w2)),
            gram_w3=float(n.get("gram_w3", Norms.gram_w3)),
            dup_threshold=float(n.get("dup_threshold", Norms.dup_threshold)),
        )

        v = d.get("verify") or {}
        verify = VerifySpec(
            probes=[str(x) for x in (v.get("probes") or [])],
            generic_fill=[str(x) for x in (v.get("generic_fill") or [])],
            legacy_shelf=[str(x) for x in (v.get("legacy_shelf") or [])],
            thresholds={k: float(val) for k, val in (v.get("thresholds") or {}).items()},
            content=v.get("content") or {},
        )

        return cls(
            name=str(d.get("name") or src.stem),
            label=str(d.get("label") or d.get("name") or ""),
            sources=sources,
            layers=layers,
            paths=paths,
            norms=norms,
            verify=verify,
            schema_version=int(d.get("schema_version", 0)),
            root=root,
            src_path=src,
        )

    # ── 校验（SPEC §4 五条规则）──────────────────────────────────────

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ProfileError(
                f"schema_version 必须是 {SCHEMA_VERSION}，实际 {self.schema_version}"
            )
        if not self.sources:
            raise ProfileError("至少需要一个 sources[]")
        if not self.layers:
            raise ProfileError("至少需要一个 layers{}")

        # 规则 2：source 的 layer 必须在 layers 里声明了 prefix
        for s in self.sources:
            if s.kind not in ("table", "card"):
                raise ProfileError(f"source.kind 只能是 table / card，实际 {s.kind!r}")
            spec = self.layers.get(s.layer)
            if spec is None:
                raise ProfileError(f"source.layer={s.layer!r} 未在 layers 中声明")
            if not spec.prefix:
                raise ProfileError(f"layers.{s.layer}.prefix 不能为空")

            target = s.path if s.kind == "table" else s.dir
            if not target:
                raise ProfileError(f"{s.kind} 源必须提供 {'path' if s.kind=='table' else 'dir'}")
            if not self.resolve(target).exists():
                raise ProfileError(f"源路径不存在：{target}（root={self.root}）")

            if s.kind == "table":
                if s.entry_re is None:
                    raise ProfileError(f"table 源 {target} 必须提供 entry_re")
                if "name" not in s.entry_re.groupindex:
                    raise ProfileError(f"table 源 {target} 的 entry_re 必须含命名组 (?P<name>…)")
            else:
                if s.title_re is None or "title" not in s.title_re.groupindex:
                    raise ProfileError(f"card 源 {target} 的 title_re 必须含命名组 (?P<title>…)")

        # 规则 5：quota 之和 ≤ 1.0
        total_quota = sum(spec.quota for spec in self.layers.values())
        if total_quota > 1.0 + 1e-9:
            raise ProfileError(f"layers 的 quota 之和为 {total_quota:.3f}，必须 ≤ 1.0")

    # ── 路径安全（SPEC C6）───────────────────────────────────────────

    def resolve(self, rel: str, *, allow_outside: bool = False) -> Path:
        """把 ``rel`` 解析为绝对路径。

        ``allow_outside=False``（默认）：**知识源**与 ``ref`` 必须落在 root 内，防路径穿越。
        ``allow_outside=True``：**I/O 位置**（索引 / 状态 / 增量池）允许任意路径 ——
        输出位置是 profile 自己声明的，用户有权指定到仓库外（测试隔离与 CI 都依赖这点）。
        """
        raw = Path(rel)
        p = raw.resolve() if raw.is_absolute() else (self.root / raw).resolve()
        if allow_outside:
            return p
        try:
            p.relative_to(self.root)
        except ValueError:
            raise ProfileError(f"路径越界：{rel}（root={self.root}）") from None
        return p

    def resolve_output(self, rel: str) -> Path:
        """I/O 位置：允许 root 外 —— 与知识源的严格校验刻意分开。"""
        return self.resolve(rel, allow_outside=True)

    def rel(self, p: Path) -> str:
        """绝对路径 → root 相对的 POSIX 路径（写进索引时用，跨平台一致）。"""
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.as_posix()

    # ── 便捷访问 ─────────────────────────────────────────────────────

    @property
    def layer_order(self) -> list[str]:
        """稳定的层顺序（按 quota 降序），用于索引分节与配额分配。"""
        return sorted(self.layers, key=lambda k: (-self.layers[k].quota, k))

    def prefix_of(self, layer: str) -> str:
        spec = self.layers.get(layer)
        return spec.prefix if spec else layer


def _compile(pattern: Any, field_name: str) -> re.Pattern | None:
    if pattern is None or pattern == "":
        return None
    try:
        return re.compile(str(pattern), re.MULTILINE)
    except re.error as exc:
        raise ProfileError(f"{field_name} 不是合法正则：{exc}") from exc


# ── extends 继承 ───────────────────────────────────────────────────────────


def _resolve_ref(ref: str, base_dir: Path) -> Path:
    """解析 ``extends`` / ``probes_ref`` 的引用。

    两种形式：

    * ``builtin:name`` → 包内 ``seedbrain/data/name``（随 SDK 版本走，零漂移）
    * 其他 → 相对**引用者所在目录**（与 import 语义一致，不依赖 root）
    """
    s = str(ref)
    if s.startswith("builtin:"):
        name = s.split(":", 1)[1]
        # 允许省略 .json 后缀（builtin:base 与 builtin:base.json 等价）
        for cand in (DATA_DIR / name, DATA_DIR / f"{name}.json"):
            if cand.is_file():
                return cand.resolve()
        raise ProfileError(
            f"内置配置不存在：builtin:{name}（查找于 {DATA_DIR}，也试过 {name}.json）"
        )
    p = (base_dir / s).resolve()
    if not p.is_file():
        raise ProfileError(f"引用指向的文件不存在：{p}")
    return p


def _apply_probes_ref(data: dict, base_dir: Path) -> dict:
    """把 ``verify.probes_ref`` 展开成 ``verify.probes``（池在前 + 本域在后）。

    为什么单独成函数而不塞进 ``_from_dict``：这里的合并是**数组拼接**，
    与 ``extends`` 的 dict 合并是两种规则。混在一起会让 ``_from_dict``
    承担两套语义，而两套语义的例外情况迟早会打架。
    """
    verify = data.get("verify")
    if not isinstance(verify, dict):
        return data
    ref = verify.pop("probes_ref", None)
    if not ref:
        return data

    pool_path = _resolve_ref(str(ref), base_dir)
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"探针池不是合法 JSON：{pool_path}（{exc}）") from exc
    if not isinstance(pool, list) or not pool:
        raise ProfileError(f"探针池必须是非空数组：{pool_path}")

    local = [str(x) for x in (verify.get("probes") or [])]
    verify["probes"] = [str(x) for x in pool] + local
    verify["_source"] = {"ref": str(ref), "pool": len(pool), "local": len(local)}
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    """dict 递归合并；list 与标量整体替换。

    为什么 list 整体替换而不合并：合并会让「想清空从 base 继承来的 probes」
    变得不可能，而配置里 list 的语义通常是「这是我的完整清单」。
    """
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_merged(path: Path, chain: tuple = ()) -> tuple:
    """读 JSON 并递归应用 ``extends``，返回 ``(合并后的 dict, 继承链)``。

    三条硬约束：

    * ``extends`` 相对**当前 profile 所在目录**解析（与 import 语义一致，不依赖 root）；
    * 循环继承直接报错，不递归到栈溢出；
    * merge 规则固定：dict 递归、list / 标量替换。
    """
    if path in chain:
        names = " → ".join(p.name for p in chain + (path,))
        raise ProfileError(f"profile 继承出现循环：{names}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"profile 不是合法 JSON：{path}（{exc}）") from exc
    if not isinstance(raw, dict):
        raise ProfileError(f"profile 顶层必须是对象：{path}")

    parent_rel = raw.get("extends")
    data = {k: v for k, v in raw.items() if k != "extends"}
    if not parent_rel:
        return data, []

    base_path = _resolve_ref(str(parent_rel), path.parent)
    base_data, base_chain = _load_merged(base_path, chain + (path,))
    return _deep_merge(base_data, data), base_chain + [str(parent_rel)]
