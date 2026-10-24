# CHANGE-20261022-seed-brain-sdk — 把两套复制粘贴的检索层收敛成领域无关 SDK

```yaml
change_id: CHG-20261022-seed-brain-sdk
title: 把「种子大脑」从两个领域仓库里的复制粘贴脚本，抽成领域无关、配置驱动的 source-available SDK
status: INTENT_ALIGNED
owner: user
created_at: 2026-10-22
evidence_date: 2026-10-22
supersedes: null
```

## 1. 问题（Problem）

同一个检索层，已经在两个领域仓库里被写了**两遍**：

| 仓库 | 脚本 | 收敛状态 |
|---|---|---|
| `agent-taste-seed-system`（美学大脑） | `scripts/seed_brain.py` + `scripts/seed_brain_selftest.py` | v0.1.0 |
| `agent-math-seed-system`（数学大脑） | 同上 + `scripts/check_counts.py` | v0.1.0，**md5 与美学侧完全一致** |

一致性靠人手工维护（`md5sum` 对比）。这带来四条结构性债务：

| # | 债务 | 表现 |
|---|---|---|
| D1 | **算法与领域配置耦合** | `PROFILES` / `PROBES` / `LEGACY_SHELF` / `EXPECTED_FILES` 全部硬编码在脚本顶部 |
| D2 | **改一处要改两处** | 修一个 IDF 或配额 bug，必须同步两个仓库，否则 md5 漂移 |
| D3 | **领域接入 = 复制 1000 行** | 想加第三个领域（写作/音乐/健身），只能整份复制再改常量 |
| D4 | **验证套件不可复用** | 27 项断言与本仓库的相对路径硬绑（`sys.path.insert` + `import seed_brain`） |

**根本原因（根因）**：把「**领域知识如何被解析**」和「**领域知识如何被检索**」写进了同一份代码。
前者是每个领域都不同的（正则、分层、信号词表、配额），后者是每个领域都相同的（n-gram、IDF、配额分配、时间衰减、断言框架）。

**对照证据**：这三份脚本里，真正领域无关的部分占 ~75%（`grams` / `build_idf` / `novelty` / `rank` / `Report` / `merge_seeds` / `find_duplicate`），
领域相关的部分只有 ~25%（4 张常量表 + 2 个正则）。**比例本身就是抽象的依据。**

## 2. 期望结果（Outcome）

1. **单一源**：检索算法只有一个实现、一个版本号、一条发布流水线。
2. **领域零改代码**：接入新领域 = 写一份 `profiles/<domain>.json`（解析规则 + 分层配额 + 探针），不需要碰 Python。
3. **内容与算法彻底分离**：SDK 仓库**不包含任何上游种子内容**。引擎与语料同为 CC BY-NC-SA 4.0，但是两份**相互独立的版权客体**；混同会让再许可与商业授权的边界失去可追溯性。
4. **可验证**：把上游项目的 27 项行为断言 + math 的 11 项内容断言抽象成**可配置的验证套件**，新领域复用同一套门槛。
5. **零依赖、可复现**：纯 stdlib，Python 3.9+；同一输入必得同一输出（不引入随机数）。
6. **能力提升可测量**：README 说清「为什么这个 SDK 能让任意 harness / 任意模型变强」——因为它把「靠模型记忆碰运气」换成「查库 + 约束 + 自检」。

## 3. 当前行为（Current Behavior）

- 每个领域仓库各自持有一份 `seed_brain.py`，通过 `detect_profile()` 用硬编码字典区分领域。
- `python3 scripts/seed_brain.py match "…"` 只能在自己的仓库根下跑（`ROOT = Path(__file__).parent.parent`）。
- 增量池 `references/seed-additions.jsonl` 与状态文件 `references/.seed-usage.json` 都是仓库内相对路径。
- 验证套件 `seed_brain_selftest.py` 用 `sys.path.insert` 导入同目录脚本，无法作为库使用。
- 没有 `pyproject.toml`、没有 `py.typed`、没有公开 API、没有版本导出。

## 4. 非目标（Non-goals）

- **不搬内容**：SDK 不打包美学大脑 / 数学大脑的任何种子条目、章节原文、实测日志。
- **不做语义检索**：保持字符 n-gram + IDF（零依赖、可解释、可复现）；向量检索作为可选后端留到 v2，不在本 CHG。
- **不做服务端**：不提供 HTTP / daemon / 数据库；纯本地库 + CLI。
- **不改上游的四层知识库契约**（`references/` 分层、相对引用、按需加载）。
- **不做自动改写上游**：本 CHG 只交付 SDK 仓库本身；上游改为依赖 SDK 是**后续独立变更**（见 SPEC §7 迁移）。
- **不引入第三方依赖**（含 `tomli`、`pydantic`、`click`）——这是本项目的核心卖点之一。

## 5. 约束（Constraints）

| ID | 约束 | 来源 |
|---|---|---|
| C1 | CC BY-NC-SA 4.0（非商业 + 相同方式共享），且不含上游种子内容；贡献者授予再许可权 | 保留商业授权能力（双授权） |
| C2 | 零第三方运行时依赖 | 跨 harness / 无网环境部署 |
| C3 | Python ≥ 3.9（`tomllib` 只有 3.11+ → 配置文件用 JSON） | 兼容面 |
| C4 | 同一输入必得同一输出（无 `random`、无 `hash()`） | 可复现性断言 T8 |
| C5 | 所有验证必须可离线执行（CI 不联网取数） | 供应链安全 |

## 6. 验收（Acceptance）

| # | 验收项 | 判定方式 |
|---|---|---|
| A1 | 新领域接入不写 Python | 只用 `profiles/example.json` + `seedbrain build/verify` 跑通 |
| A2 | 上游能力不回退 | 用 SDK 驱动美学大脑，27 项断言与改造前逐项一致 |
| A3 | 许可干净 | 仓库内 `git grep -l "art-seeds\|赛博霓虹"` 为空（除 profile 的解析规则示例） |
| A4 | 零依赖 | `pip install .` 后 `pip show agent-seed-brain` 的 Requires 为空 |
| A5 | 首版即绿 | 首次 push 后 CI 全绿，无失败 run 需要清理 |
