<p align="right">
  <a href="../en/profiles.md">English</a> · <b>简体中文</b> ·
  <a href="../../README.zh-CN.md">← README</a>
</p>

# Profile 参考

一个领域 = 一份 JSON。它声明**知识在哪、怎么解析、什么算合格**。加一个领域不需要
写一行 Python。

```bash
seedbrain config --profile your.json     # 永远先看合并后的结果
```

---

## 1. 最小 profile

```json
{
  "schema_version": 1,
  "name": "numerics",
  "label": "数值方法",
  "sources": [
    {
      "kind": "table",
      "path": "notes/methods.md",
      "layer": "method",
      "group_re": "^##\\s+(?P<group>[^#].*)$",
      "entry_re": "^-\\s*\\*\\*(?P<name>[^*]+?)\\*\\*\\s*·\\s*(?P<tag>[^—]+?)\\s*——\\s*(?P<desc>.+)$"
    }
  ],
  "layers": {
    "method": { "prefix": "m", "quota": 1.0, "label": "方法" }
  }
}
```

这份就够 `build` 和 `match`。`verify` 还需要探针和阈值 —— 用继承（§8）拿，
或者显式写。

---

## 2. 顶层字段

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `schema_version` | int | ✅ | — | 必须是 `1` |
| `name` | str | — | profile 文件名 | 报告里显示 |
| `label` | str | — | `name` | 人类可读标题 |
| `root` | str | — | 见 `--root` 规则 | 知识库根，相对 profile |
| `extends` | str | — | — | 继承另一份 profile（§8） |
| `sources` | list | ✅ | — | 至少一条 |
| `layers` | dict | ✅ | — | 至少一层 |
| `paths` | dict | — | `references/…` | 输出位置（§5） |
| `norms` | dict | — | 合理默认 | 打分常数（§6） |
| `verify` | dict | — | `{}` | 探针与阈值（§7） |
| `_comment` | any | — | — | 被忽略，用来解释这份文件 |

未知的顶层键会被忽略，保证向前兼容不痛。

---

## 3. `sources[]`

两种。每个源只属于一个层。

### 3.1 `kind: "table"` —— 一个文件里多条

| 字段 | 必填 | 作用 |
|---|---|---|
| `kind` | ✅ | `"table"` |
| `path` | ✅ | 文件，相对 root |
| `layer` | ✅ | 必须在 `layers` 里存在 |
| `group_re` | — | 捕获 `group`（章节标题） |
| `entry_re` | ✅ | 捕获 `name`、`tag`、`desc` |
| `aux_re` | — | 捕获 `kw`，挂到**上一条**条目上 |

捕获组名是契约：`group`、`name`、`tag`、`desc`、`kw`。名字必须完全一致，否则
解析出 0 条，`build` 会大声失败。

示例源行与匹配它的正则：

```
- **Matrix decomposition** · svd —— 奇异值分解，降维与压缩的通用手段
  ^-\\s*\\*\\*(?P<name>[^*]+?)\\*\\*\\s*·\\s*(?P<tag>[^—]+?)\\s*——\\s*(?P<desc>.+)$
     └ name: "Matrix decomposition"  └ tag: "svd"        └ desc: "奇异值分解…"
```

> **破折号是两个字符。** `entry_re` 要的是全角双破折号 `——`（U+2014 两个）。
> 写成单个 `—` 会静默匹配不到。这是「解析出 0 条」最常见的原因。

### 3.2 `kind: "card"` —— 一个文件一粒

| 字段 | 必填 | 作用 |
|---|---|---|
| `kind` | ✅ | `"card"` |
| `dir` | ✅ | 卡片目录，相对 root |
| `layer` | ✅ | 必须在 `layers` 里存在 |
| `title_re` | — | 捕获 `title`（通常是 H1） |
| `field_re` | — | 从元数据行捕获 `key` / `val` |
| `list_re` | — | 从项目符号行捕获 `item` |
| `template_parts` | — | 标记「模板文件」的子串，这些文件会被跳过 |

美学大脑用卡片承载 352 粒章档：每个艺术家 / 风格一个文件，顶部是元数据块。

```json
{
  "kind": "card",
  "dir": "chapters",
  "layer": "chapter",
  "title_re": "^#\\s+(?P<title>.+)$",
  "field_re": "^>\\s*\\*\\*(?P<key>[^*]+?)\\*\\*\\s*[：:]\\s*(?P<val>.*)$",
  "list_re": "^>\\s*(?:[-*]|\\d+\\.)\\s+(?P<item>.+)$",
  "template_parts": ["template", "card"]
}
```

`template_parts` 的存在理由：卡片目录里几乎总有一个「示例 / 模板」文件，它不是
真内容。不排除的话，模板的名字会被索引并开始和真条目竞争。

---

## 4. `layers{}`

```json
"layers": {
  "method": { "prefix": "m",  "quota": 0.6, "label": "方法" },
  "card":   { "prefix": "cd", "quota": 0.4, "label": "专题卡" }
}
```

| 字段 | 必填 | 含义 |
|---|---|---|
| `prefix` | ✅ | ID 前缀，如 `m-matrix-decomposition` |
| `quota` | — | 占 `top-K` 的比例，`0..1`，建议总和 ≤ 1.0 |
| `label` | — | 报告里的显示名 |

**配额分两阶段执行**：每层先拿 `min(floor(k×quota), 该层候选数)`，剩余名额按全局
分数补满。某层没有候选时，它的名额自然让给有货的层 —— 小层永远不会被大层饿死。

前缀必须唯一。ID 形如 `prefix + "-" + slug(name)`。

---

## 5. `paths{}`

```json
"paths": {
  "index_jsonl": "references/seed-index.jsonl",
  "index_md":    "references/SEED-INDEX.md",
  "additions":   "references/seed-additions.jsonl",
  "state":       "references/.seed-usage.json"
}
```

全部相对 `root`。两个索引文件是**生成产物** —— 想用 `git diff --exit-code` 当幂等
闸门就提交它们（本仓库正是这么做的）。`additions` 与 `state` 是追加式工作状态，
消费方仓库通常 gitignore。

---

## 6. `norms{}`

| 字段 | 默认 | 含义 |
|---|---|---|
| `decay_tau_days` | `14.0` | 新颖度恢复的时间常数（天） |
| `count_penalty` | `0.5` | 重复使用的惩罚强度 |
| `max_hits` | `5` | 每次匹配保留的命中信号上限（展示 + 计分） |
| `gram_w2` | `1.0` | 2-gram 权重 |
| `gram_w3` | `0.35` | 3-gram 权重 |
| `dup_threshold` | `0.75` | 超过这个包含度时 `add` 判定为重复 |

```python
recovery  = 1 - exp(-Δt / decay_tau_days)
count_pen = 1 / (1 + count_penalty * ln(1 + count))
novelty   = max(0.15, recovery * count_pen)
```

`0.15` 的下限**故意不可配置**：它保住「我就想复现上次结果」这个正当请求。

---

## 7. `verify{}`

```json
"verify": {
  "probes_ref": "builtin:probes/core",
  "probes": ["降维压缩，矩阵分解选型"],
  "generic_fill": ["方法", "计算", "结果", "分析"],
  "legacy_shelf": ["tl-矩阵分解", "tl-图遍历"],
  "thresholds": { "recall_name": 0.9 },
  "content": {}
}
```

| 字段 | 作用 |
|---|---|
| `probes` | 代表性任务描述，驱动召回 / 轮转检查 |
| `probes_ref` | 引用公共探针池（§10） |
| `generic_fill` | 检查特征召回时被视为「通用词」的词 |
| `legacy_shelf` | 你的「旧首选表」，支撑去中心化检查 `T9` |
| `thresholds` | 覆盖任意默认门槛 |
| `content` | 可选的内容完整性规格（目录计数、必需字段） |

### 门槛默认值

| 键 | 默认 | 对应检查 |
|---|---|---|
| `recall_name` | `0.98` | T2a 名字自召回@8 |
| `recall_feature` | `0.60` | T2b 特征召回 |
| `gini_max` | `0.80` | T3a 命中分布基尼 |
| `idf_top1_gain` | `0.15` | T4b IDF 端到端对照 |
| `layer_dominance_max` | `0.70` | T6 层垄断 |
| `rotation_min` | `4` | T5 不同 top1 数 |
| `rotation_rounds` | `6` | T5 连续轮数 |
| `decenter_min` | `0.50` | T9 top1 落在 `legacy_shelf` 之外的比例 |

**不要为了让构建通过而下调门槛。** 本项目历史上两个真 bug 恰恰是因为**没有**下调
门槛才被抓到（见 `methodology.md` §8）。

---

## 8. `extends` —— 继承，而不是复制

```json
{
  "extends": "builtin:base",
  "name": "my-domain",
  "sources": [ /* 只写本域特有 */ ],
  "layers":  { /* 只写本域特有 */ }
}
```

**合并规则只有两条：**

1. dict 递归合并；
2. list 与标量整体替换。

list 不合并，是因为「想清空从 base 继承来的 probes」必须能表达。这个后果也是探针
需要单独机制（§10）的原因。

成环会被检测：`A → B → A` 抛 `ProfileError` 并带上完整链路，而不是递归到栈溢出。

看结果：

```bash
seedbrain config --profile my.json --chain   # A → builtin:base
seedbrain config --profile my.json           # 合并后的最终配置
```

合并之后，**继承链才是真相，不是你写的那个文件**。排查阈值别去读自己写的 profile，
要读 `config` 的输出。

---

## 9. `paths.root` 与 `profiles/` 约定

如果 profile 所在目录的名字恰好是 `profiles/`，root 取它的上一级。这样最常见的
布局零配置即可工作：

```
repo/
  profiles/example.json     → root = repo/
  notes/methods.md          → 声明为 "notes/methods.md"
```

其他位置则把 profile 自身所在目录当作 root。两者都不合适时用 `--root` 或
`"root"` 字段覆盖。

---

## 10. `probes_ref` —— 复用探针而不复制

`verify.probes` 是 list，按上表规则会被 `extends` **整体替换**。所以探针复用走
独立字段：

```json
{
  "verify": {
    "probes_ref": "builtin:probes/core",
    "probes": ["本域特有任务一", "本域特有任务二"]
  }
}
```

展开顺序是**池在前、本域在后**。`seedbrain config` 会报告来源：

```json
"probes_source": { "ref": "builtin:probes/core", "pool": 8, "local": 2 }
```

### `builtin:` 解析

`builtin:name` 解析到安装包内（`seedbrain/data/`），`.json` 可省略：

```json
{ "extends": "builtin:base" }
```

这是领域仓库引用公共配置的正解：**零复制、零漂移、随 SDK 版本走**。该文件会打进
wheel，所以普通 `pip install` 之后就能用 —— 而 `profiles/example.json` 只属于仓库。

目前可用：`builtin:base`、`builtin:probes/core`。

---

## 11. 常见错误

| 症状 | 原因 | 修法 |
|---|---|---|
| `不是合法 JSON` | 正则里写了单反斜杠 | JSON 内每个反斜杠写成两个 |
| `解析出 0 条种子` | `entry_re` 不匹配，通常是 `—` vs `——` | 拿一行真实内容逐字符比对 |
| `source.layer 未在 layers 中声明` | `sources[].layer` 与 `layers{}` 键名打错 | 必须完全一致 |
| `layers.x.prefix 不能为空` | 声明了层却没给 `prefix` | 补上 |
| `schema_version 必须是 1` | 从旧/新文档抄来 | 设为 `1` |
| Windows 路径报错 | JSON 里写了 `"C:\dir"` | 用正斜杠或 `\\` |
| `T9` 一直被跳过 | 没配 `legacy_shelf` | 补上你自己的旧首选表，或接受跳过 |
| `T5` 在小库上失败 | 互相竞争的种子少于约 4 粒 | 扩充语料；不要下调 `rotation_min` |
