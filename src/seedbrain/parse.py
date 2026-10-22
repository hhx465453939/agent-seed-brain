"""源解析 —— 把 Markdown 变成 :class:`Seed`，完全由 profile 的正则驱动。

两种源：

* ``table``：单行速查总库（一个领域一行一粒的方法总表）
* ``card``：一张卡一粒种子（``code-genes/``、``recipes/``、``moods/``、``scenarios/``）

解析结果必须满足一条硬约束：**每种源至少解析出 1 粒**，否则报错。
静默产出空索引是最危险的失败模式——用户会以为「库里没有」，而不是「正则写错了」。
"""

from __future__ import annotations

from .models import Seed
from .profile import Profile, Source
from .tokenize import grams


class ParseError(RuntimeError):
    """源解析失败（通常是 profile 的正则与实际格式不匹配）。"""


def parse_source(prof: Profile, source: Source) -> list[Seed]:
    """解析一个 source，返回种子列表（id 尚未加层前缀）。"""
    seeds = _parse_table(prof, source) if source.kind == "table" else _parse_cards(prof, source)
    if not seeds:
        target = source.path if source.kind == "table" else source.dir
        raise ParseError(
            f"源 {target!r} 解析出 0 条种子 —— "
            f"请检查 profile 里的 {'entry_re' if source.kind == 'table' else 'title_re'} 是否匹配实际格式"
        )
    return seeds


# ── table：单行速查 ───────────────────────────────────────────────────────


def _parse_table(prof: Profile, src: Source) -> list[Seed]:
    text = prof.resolve(src.path).read_text(encoding="utf-8")
    lines = text.splitlines()

    seeds: list[Seed] = []
    group = ""
    pending: dict | None = None  # 等待 aux 行的条目
    seq = 0

    for raw in lines:
        line = raw.rstrip()

        if src.group_re is not None:
            m = src.group_re.match(line)
            if m:
                if pending is not None:
                    _finish(pending, seeds, prof, src)
                    pending = None
                group = _clean(m.groupdict().get("group", "")).split("（")[0].strip()
                continue

        if pending is not None and src.aux_re is not None:
            m = src.aux_re.match(line)
            if m:
                pending["aux"] = _clean(m.groupdict().get("kw", ""))
                continue
            _finish(pending, seeds, prof, src)
            pending = None

        m = src.entry_re.match(line)
        if not m:
            continue
        gd = m.groupdict()
        name = _clean(gd.get("name", ""))
        if not name:
            continue
        seq += 1
        pending = {
            "name": name,
            "tag": _clean(gd.get("tag", "")),
            "desc": _clean(gd.get("desc", "")),
            "aux": "",
            "group": group,
            "extra": _extras(gd),
            "seq": seq,
        }
        if src.aux_re is None:
            _finish(pending, seeds, prof, src)
            pending = None

    if pending is not None:
        _finish(pending, seeds, prof, src)
    return seeds


def _finish(entry: dict, out: list[Seed], prof: Profile, src: Source) -> None:
    """把一条暂存条目落成 Seed。

    ID 规则：ASCII 名优先（``Giotto`` → ``giotto``），否则用归一化后的本名。
    早期版本对纯中文名使用 ``001-矩阵分解`` 这种「序号+名」形式，运行时才发现
    ID 不可读、外部引用难写（旧货架样本 T1d 因此引用了不存在的 id）。
    重名由 ``_disambiguate`` 加后缀解决，不需要序号占位。
    """
    name = entry["name"]
    sid = _slug_from_name(name) or _slug(name) or f"{entry['seq']:03d}"
    text = " ".join(x for x in (name, entry["tag"], entry["desc"], entry["aux"], entry["group"]) if x)
    out.append(Seed(
        id=sid,
        name=name,
        layer=src.layer,
        group=entry["group"],
        one_liner=entry["desc"][:90],
        text=text,
        grams=len(grams(text)),
        ref=prof.rel(prof.resolve(src.path)),
        origin="source",
        extra=entry["extra"],
    ))


# ── card：一张卡一粒种子 ──────────────────────────────────────────────────


def _parse_cards(prof: Profile, src: Source) -> list[Seed]:
    directory = prof.resolve(src.dir)
    seeds: list[Seed] = []

    for path in sorted(directory.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = ""
        fields: dict[str, str] = {}
        current: str | None = None

        for line in lines[:80]:
            if not title and src.title_re is not None:
                m = src.title_re.match(line)
                if m:
                    title = _clean(m.groupdict().get("title", ""))
                    continue

            if src.field_re is not None:
                m = src.field_re.match(line)
                if m:
                    key = _clean(m.groupdict().get("key", ""))
                    val = _clean(m.groupdict().get("val", ""))
                    if key:
                        current = key
                        fields[key] = val
                    continue

            # 列表型字段续行：`> - 条目` 或 `> 1. 条目`
            if current and src.list_re is not None:
                m = src.list_re.match(line)
                if m:
                    item = _clean(m.groupdict().get("item", ""))
                    if item:
                        fields[current] = (fields[current] + " / " + item) if fields[current] else item
                    continue

            # 退出引用块 → 停止归并到上一个字段
            if line.strip() and not line.lstrip().startswith(">"):
                current = None

        name = _name_from_title(title, src.template_parts) or path.stem
        text = " ".join([title] + [f"{k} {v}" for k, v in fields.items()])
        seeds.append(Seed(
            id=_slug(path.stem),
            name=name,
            layer=src.layer,
            group=directory.name,
            one_liner=_pick_one_liner(fields),
            text=text,
            grams=len(grams(text)),
            ref=prof.rel(path),
            origin="source",
            extra={"fields": sorted(fields)},
        ))
    return seeds


# ── 文本工具 ──────────────────────────────────────────────────────────────

_MD_BOLD = None
_MD_LINK = None
_EMOJI = None


def _clean(text: str) -> str:
    """去掉 markdown 标记与行首 emoji，压平空白。

    行首 emoji 必须先剥：卡片 H1 形如 ``🧮 code-recipe · 01 线性代数与矩阵分解``，
    若不剥离，按 ``·`` 切出的第一段是 ``🧮 code-recipe``，与 ``template_parts``
    里的 ``code-recipe`` 不相等 → 模板段过滤失效 → 种子名字变成
    ``🧮 code-recipe``，用名字召回必然失败（实测 math 域 9/204 粒因此漏召回）。
    """
    global _MD_BOLD, _MD_LINK, _EMOJI
    if _MD_BOLD is None:
        import re
        _MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
        _MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
        # 盖 emoji 主体、变体选择符（U+FE0F）与零宽连接符（U+200D）
        _EMOJI = re.compile(r"^[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+\s*")
    text = _EMOJI.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = text.replace("`", "").strip()
    return text


def _slug(text: str) -> str:
    import re
    text = _clean(text)
    text = re.sub(r"[（）()《》「」【】\[\]：:；;，,。.、/\\|\"'’]", " ", text)
    text = re.sub(r"\s+", "-", text.strip())
    return re.sub(r"-{2,}", "-", text).strip("-").lower()


def _slug_from_name(name: str) -> str:
    """名字里的 ASCII 片段作为稳定 ID（``Giotto`` → ``giotto``）。"""
    import re
    parts = re.findall(r"[A-Za-z][A-Za-z0-9'\-\s\.]{2,}", name)
    return _slug(parts[0]) if parts else ""


def _name_from_title(title: str, template_parts: list[str]) -> str:
    """从 H1 取干净名字：按「带空格的 ·」切段，剔除模板段。

    中文名内部常见无空格 ``绢色·气口·印章``，不能切碎。
    """
    import re
    if not title:
        return ""
    parts = [p.strip() for p in re.split(r"\s+·\s+", _clean(title)) if p.strip()]
    skip = {p.lower() for p in template_parts}
    parts = [p for p in parts if p.lower() not in skip]
    return parts[0] if parts else ""


def _pick_one_liner(fields: dict[str, str]) -> str:
    """预览行：按优先级挑第一个有内容的字段。"""
    for key in ("适用产物", "适用场景", "典型任务", "覆盖工具", "问题信号", "读者该感受到", "激活词"):
        if fields.get(key):
            return fields[key][:90]
    return ""


def _extras(gd: dict[str, str]) -> dict[str, str]:
    """把正则里的额外命名组（如 years / sub / anchor）保留进 extra。"""
    keep = {}
    for k, v in gd.items():
        if k in ("name", "tag", "desc", "group", "kw"):
            continue
        if v:
            keep[k] = _clean(v)
    return keep
