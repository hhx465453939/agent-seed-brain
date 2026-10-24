# SPEC-20261022-seed-brain-sdk — 工程契约

```yaml
change_id: CHG-20261022-seed-brain-sdk
version: 1
status: approved
prd_ref: PRD.md
health_ref: HEALTH.md
approved_by: user
approved_at: 2026-10-22
```

## 0. 阅读顺序

`CHANGE.md`（为什么）→ `HEALTH.md`（现状债）→ `PRD.md`（对外承诺）→ 本文件（怎么建）→ `TRACEABILITY.md`（怎么验）。

## 1. 目标与非目标

### 1.1 目标

| ID | 目标 |
|---|---|
| E1 | 检索算法单一源，可 `pip install`，带 `__version__` 与 `py.typed` |
| E2 | 领域差异 100% 外置到 `profiles/*.json`：新增领域不写 Python |
| E3 | 提供库 API（可嵌入任意 harness）+ CLI（可脚本化） |
| E4 | 验证套件参数化：同一套断言适用于任意 profile，门槛可配 |
| E5 | SDK 仓库零上游内容（许可隔离） |
| E6 | `--root` 驱动外部仓库，实现「算法在 SDK、内容在上游」 |
| E7 | 零运行时依赖，Python 3.9+ |
| E8 | 首版 CI 全绿（3.9~3.13 矩阵 + 自验证） |

### 1.2 非目标

- 不做语义/向量检索（v2 再说）
- 不做服务端、数据库、daemon
- 不打包任何上游种子内容
- 不自动改写上游仓库（迁移是独立变更，见 §7）

## 2. 约束

| ID | 约束 | 来源 | 违反后果 |
|---|---|---|---|
| C1 | CC BY-NC-SA 4.0；内容与引擎许可隔离；贡献者授予再许可权 | 保留商业授权能力 | 无法提供单份商业许可，整仓商业价值受损 |
| C2 | 零第三方运行时依赖 | NFR-1 | 失去核心卖点 |
| C3 | 配置格式 = JSON（非 TOML） | 3.9 无 `tomllib` | 需引入依赖或放弃 3.9 |
| C4 | 确定性：无 `random`、无内置 `hash()` | NFR-3 | 断言 T8 失败 |
| C5 | 一切 I/O 必须显式带 `encoding="utf-8"` | Windows GBK 默认 | 中文路径读失败 |
| C6 | `ref` 必须是 root 内相对路径 | 安全 | 路径穿越 |

## 3. 架构

```
agent-seed-brain/
├── src/seedbrain/
│   ├── __init__.py      # 公开 API 再导出 + __version__
│   ├── models.py        # Seed / Match / BuildResult / VerifyReport / Check
│   ├── profile.py       # Profile.load() + 校验（正则可编译、源存在）
│   ├── tokenize.py      # grams() / grams_cached() / build_idf()
│   ├── parse.py         # parse_table() / parse_cards()（由 profile 的正则驱动）
│   ├── index.py         # build_index() / write_jsonl() / write_flat_md()
│   ├── score.py         # score_seed() / novelty() / rank()
│   ├── state.py         # load_state() / save_state()
│   ├── additions.py     # load/save additions, merge_seeds(), find_duplicate()
│   ├── verify.py        # CheckSuite：通用断言 + profile 声明的内容断言
│   └── cli.py           # argparse 子命令：build/match/pick/add/verify/stats
├── profiles/
│   ├── example.json     # 最小可用示例（无上游内容）
│   └── taste.json       # 美学大脑的解析规则（只含规则，不含种子）
├── tests/
│   ├── fixtures/mini-domain/   # 自写 22 条中性种子（CC BY-NC-SA 4.0）
│   ├── test_tokenize.py … test_cli.py
│   └── test_upstream_regression.py  # @upstream：可选，跑真实仓库
├── examples/
│   └── minimal.py       # 5 行代码用库 API
├── docs/
│   ├── METHODOLOGY.md   # 算法原理（IDF / 配额 / 衰减）
│   └── EVIDENCE.md      # 验证报告（对 fixture 域跑出）
├── assets/banner.svg    # README hero（手写矢量，无外部依赖）
└── pyproject.toml
```

**依赖方向**（单向，无环）：`cli → {index, score, verify, state, additions} → {parse, tokenize, profile} → models`。

## 4. Profile schema（核心抽象）

```json
{
  "schema_version": 1,
  "name": "taste",
  "label": "审美种子大脑",
  "sources": [
    {
      "kind": "table",
      "path": "references/art-seeds.md",
      "layer": "chapter",
      "group_re": "^##\\s+(?P<group>.*)$",
      "entry_re": "^🎨\\s*\\*\\*(?P<name>[^*]+?)\\*\\*(?:（(?P<years>[^）]*)）)?\\s*·?\\s*(?P<tag>[^—]*?)\\s*——\\s*(?P<desc>.+)$",
      "aux_re": "^`AI:\\s*(?P<kw>.+?)`"
    },
    { "kind": "card", "dir": "references/code-genes", "layer": "code-gene" }
  ],
  "layers": {
    "chapter":   { "prefix": "ch", "quota": 0.42, "label": "风格章档" },
    "code-gene": { "prefix": "cg", "quota": 0.33, "label": "代码基因卡" },
    "mood":      { "prefix": "md", "quota": 0.25, "label": "情绪档" }
  },
  "paths": {
    "index_jsonl": "references/seed-index.jsonl",
    "index_md": "references/SEED-INDEX.md",
    "additions": "references/seed-additions.jsonl",
    "state": "references/.seed-usage.json"
  },
  "norms": {
    "decay_tau_days": 14.0,
    "count_penalty": 0.5,
    "max_hits": 5,
    "gram_weights": { "2": 1.0, "3": 0.35 },
    "dup_threshold": 0.75
  },
  "verify": {
    "probes": ["科技产品发布会 KV，冷光未来感", "…"],
    "generic_fill": ["设计", "页面", "内容", "风格"],
    "legacy_shelf": ["cg-02-赛博霓虹"],
    "thresholds": {
      "recall_name": 0.98, "recall_feature": 0.60, "gini_max": 0.80,
      "idf_top1_gain": 0.15, "layer_dominance_max": 0.70,
      "rotation_min": 4, "decenter_min": 0.50
    },
    "content": {
      "dirs": { "references/code-genes": 12, "references/moods": 10 },
      "fields": ["一句话", "何时用"],
      "docs": ["README.md"]
    }
  }
}
```

**校验规则**（`Profile.load` 必须做，失败即报错）：
1. `schema_version == 1`
2. 每个 `layer` 在 `layers` 里声明了 `prefix`
3. 所有 `*_re` 能 `re.compile` 成功且含命名组
4. `sources[].path` / `dir` 在 root 内且存在
5. `quota` 之和 ≤ 1.0（允许 < 1，余量由「补满」阶段分配）

## 5. 公开 API

```python
from seedbrain import SeedBrain, __version__

brain = SeedBrain.load("profiles/taste.json", root="/path/to/agent-taste-seed-system")

brain.build()                       # -> BuildResult(total, added, collided, layers)
brain.match("科技感长图", k=8)        # -> list[Match]
brain.pick("cg-02-赛博霓虹", score=5, note="深底霓虹一次过")
brain.add(name="…", layer="chapter", signals=["…"], ref="references/…")
brain.verify()                      # -> VerifyReport(passed, failed, checks)
brain.stats()                       # -> Stats(by_layer, by_group, blind, top)
```

`Match` 字段：`seed: Seed` / `total: float` / `base: float` / `novelty: float` / `hits: list[tuple[str, float]]`。

**不可变约定**：`build()` 之后 `brain.seeds` 是只读快照；`add()` 会自动重建。

## 6. CLI 契约

```
seedbrain build   [--profile P] [--root R] [--quiet]
seedbrain match   "<task>" [--k N] [--profile P] [--root R]
seedbrain pick    <id> [--score 0-5] [--note S]
seedbrain add     --name N --layer L [--signals a,b] [--one-liner S] [--ref R] [--force] [--dry-run]
seedbrain verify  [--evidence PATH] [--json] [--profile P] [--root R]
seedbrain stats
```

退出码：`0` 成功 / `1` 校验失败 / `2` 输入非法（未知层、ref 不存在、疑似重复）。

**默认 profile 查找顺序**：`--profile` → `./seedbrain.json` → 报错并提示 `seedbrain init`。

## 7. 迁移策略（上游如何改为依赖 SDK）

**本 CHG 只交付 SDK；上游迁移是后续独立变更。** 迁移步骤（写进 README，供使用者参考）：

1. 上游保留 `references/`、`SKILL.md`、`CONTRIBUTING.md` —— **内容不动**
2. 删除 `scripts/seed_brain.py` / `seed_brain_selftest.py`
3. 加 `profiles/<domain>.json`（从 SDK 的 `profiles/` 复制后改路径）
4. CI 改为：`pip install -e ../agent-seed-brain` → `seedbrain build --root .` → `git diff --exit-code` → `seedbrain verify`
5. 逐项比对迁移前后的 38 项断言输出，必须一致

## 8. 测试策略（本地全绿才算完成）

| 层 | 内容 | 门槛 |
|---|---|---|
| 单测 | `tokenize` / `parse` / `score` / `state` / `additions` 纯函数 | 覆盖率 ≥ 85% |
| 集成 | `tests/fixtures/mini-domain/`：build → match → pick → add → verify 全链路 | 无异常 + 断言全绿 |
| 契约 | Profile 校验的 5 条规则各有失败用例 | 全部覆盖 |
| 回归（可选） | `@pytest.mark.upstream` 用真实美学大脑跑 27 项 | 与改造前一致 |
| CI | Python 3.9 / 3.10 / 3.11 / 3.12 / 3.13 矩阵 + lint + `seedbrain verify` | 全绿 |

**为什么本地全绿这么看重**：首次 push 必须就是绿的——这样不需要 force push 清理历史，也不需要删除失败 run。工程痕迹本身也是质量的一部分。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 正则外置后错配 → 静默空索引 | `build` 断言「每个 source 解析出 ≥ 1 条」，否则报错 |
| 抽象过度 | 只外置**已在两个领域验证过**的差异；`schema_version` 为未来演进留位 |
| 3.9 兼容性 | CI 矩阵最小版本即 3.9；禁用 `match` 语句、`X \| Y` 类型注解在运行时求值 |
| 上游回填失败 | 迁移前冻结上游 commit；逐项比对断言输出 |

## 10. 版本策略

- SemVer；首版 `0.1.0`（API 未稳定）
- `0.x` 期间 minor 可破坏，patch 不破坏
- 每个 release 必须有 `CHANGELOG.md` 条目 + 通过全部 CI 矩阵
