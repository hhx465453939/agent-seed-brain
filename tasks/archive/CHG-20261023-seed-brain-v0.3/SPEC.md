# SPEC-20261023-seed-brain-v0.3 — 探针可组合化（立项阶段，未定稿）

> 状态：**方向已定，细节待实现时确认**。本文件只回答「打算怎么做、怎么验」，
> 不写具体行号级的实现步骤（那属于开工时的 PRD/TRACEABILITY）。

## 1. 设计方向

### 方案 A（推荐）：新字段 `probes_ref` + 现有 `probes` 作为追加

```jsonc
{
  "extends": "base.json",
  "verify": {
    "probes_ref": "probes/core.json",              // 引用公共池
    "probes": ["本域特有任务 1", "本域特有任务 2"]   // 追加
  }
}
```

合并结果 = 公共池探针（在前） + 本域 `probes`（在后）。

推荐理由：
- `probes` 类型不变（仍是 list）→ 现有 profile 零迁移
- `probes_ref` 语义单一（只做引用），与 `extends` 的 dict 合并互不干扰
- 来源可追溯：公共池改动会影响所有引用它的领域，这是**期望的**（指标可比）

### 方案 B（更强但破坏兼容）：`probes` 变成对象

```jsonc
"probes": { "use": ["core/dashboard", "core/timeseries"], "add": ["本域特有"] }
```

表达力更强（可按 key 选取公共池的一部分），但破坏类型兼容 → 需要迁移所有现有
profile → 与 C5 冲突。**留到 v0.4 或永远不做**。

### 方案 C（否决）：给 `extends` 加 `list_mode: "append"` 开关

一行解决所有 list 继承问题，但会让「这个 list 到底是替换还是追加」依赖**远端**的
base 配置 → 违背 v0.2 建立的可解释性原则（`config --show` 看得到值，但看不出语义）。

## 2. 要动的代码位置（预估）

| 文件 | 改动 | 预估行数 |
|---|---|---|
| `src/seedbrain/profile.py` | `_load_merged` 解析 `probes_ref`；新增 `_load_probe_pool` | ~40 |
| `src/seedbrain/cli.py` | `config` 输出标注探针来源（公共 N 条 + 本域 M 条） | ~10 |
| `tests/test_profile.py` | 新增探针引用用例（缺失 / 空池 / 追加顺序 / 去回归） | ~60 |
| `profiles/probes/core.json` | 新建：通用任务探针池 | 数据 |
| `profiles/base.json` | 可选：改为引用 core 探针池 | 1 行 |
| `README.md` / `docs/METHODOLOGY.md` | 新增一小节 | ~15 |

**不动 `verify.py`**：探针集合变了，但断言逻辑不变（这是本方案的一个优点）。

## 3. 验收标准

| AC | 判定 |
|---|---|
| AC-1 探针可引用 | 新领域 profile 写 `probes_ref` + 2 条自有探针即可跑通 verify |
| AC-2 引用缺失报错 | `probes_ref` 指向不存在的文件 → `ProfileError`，消息含路径 |
| AC-3 引用为空报错 | 公共池是空数组 → `ProfileError`（不能静默跑出零探针） |
| AC-4 向后兼容 | 不用 `probes_ref` 的三域 profile 结果不变（28/28、28/28、28/28） |
| AC-5 可解释 | `seedbrain config --show` 能看到合并后的完整探针列表与来源计数 |

## 4. 测试清单（对应 C3「断言必须能失败」）

- `test_probes_ref_appends` —— 公共 3 条 + 本域 2 条 = 5 条，顺序正确
- `test_probes_ref_missing_file` —— 报错且消息含文件路径
- `test_probes_ref_empty_pool` —— 报错（不是静默 0 条）
- `test_probes_ref_bad_json` —— 报错指向具体文件
- `test_probes_ref_absent_keeps_behaviour` —— 回归：不用该字段时结果与 v0.2 完全一致
- `test_config_show_reports_probe_sources` —— 输出含「公共 N / 本域 M」

## 5. 风险

| 风险 | 缓解 |
|---|---|
| 公共探针池成为「事实标准」，各领域盲目引用导致指标趋同 | 在文档里明确：公共池只放**跨领域通用任务**，领域特有任务必须自己写 |
| 引用链变长（base → probes_ref → 另一个池） | 只允许**单层引用**，不支持池引用池 |
| 探针池改动会静默改变所有领域的 verify 结果 | CI 里对三域都跑 verify；任何领域结果变化会在 PR 里暴露 |

## 6. 工作量估计

**小**：核心改动约 50 行 + 6 个测试用例 + 2 处文档。不改断言逻辑。
一个专注的工作时段可完成，加上三域回归验证。
