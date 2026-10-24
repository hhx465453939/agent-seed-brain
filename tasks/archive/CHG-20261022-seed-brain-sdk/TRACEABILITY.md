# TRACEABILITY-20261022-seed-brain-sdk — 追溯矩阵

> 本文件回答一个问题：**每一条承诺，靠什么证明它兑现了。**
> 三列贯通：PRD 的承诺 → SPEC 的设计 → 测试/验收的证据。

## 1. 功能需求追溯

| PRD | SPEC 章节 | 实现模块 | 测试 | 验收 |
|---|---|---|---|---|
| FR-1 `build` | §3 架构 / §4 profile | `index.py` + `parse.py` | `test_index.py` | AC-1 |
| FR-2 `match` | §5 API | `score.py` + `tokenize.py` | `test_score.py`（含 IDF 对照） | AC-1 |
| FR-3 `pick` | §5 API | `state.py` | `test_state.py`（时间衰减） | AC-2 |
| FR-4 `add` | §5 API / §6 CLI | `additions.py` | `test_additions.py`（ref 校验 / 查重 / 撞车） | AC-1 |
| FR-5 `verify` | §8 测试策略 | `verify.py` | `test_verify.py`（断言本身可失败） | AC-2 |
| FR-6 `stats` | §6 CLI | `verify.py::stats` | `test_stats.py` | — |
| FR-7 库 API | §5 | `__init__.py` | `test_api.py`（5 行示例可跑） | AC-6 |
| FR-8 profile 校验 | §4 校验规则 1~5 | `profile.py` | `test_profile.py`（5 条规则各有失败用例） | AC-1 |
| FR-9 `--root` | §6 CLI | `profile.py` + 全模块 | `test_cli.py::test_external_root` | AC-1 |
| FR-10 ref 越界 | §2 C6 | `profile.py::resolve_ref` | `test_profile.py::test_ref_escape` | — |
| FR-11 索引幂等 | §6 CLI | `index.py`（确定性排序） | `test_index.py::test_build_idempotent` | AC-5 |
| FR-12 内容层校验 | §4 `verify.content` | `verify.py::CheckSuite.content` | `test_verify_content.py` | AC-2 |

## 2. 非功能需求追溯

| NFR | 落地手段 | 如何验 |
|---|---|---|
| NFR-1 零依赖 | `pyproject.toml` 的 `dependencies = []` | CI 步骤：`pip show agent-seed-brain` 断言 Requires 为空 |
| NFR-2 ≥3.9 | CI 矩阵 3.9~3.13；配置用 JSON | 矩阵最小版本通过 |
| NFR-3 确定性 | 禁 `random`；`hashlib.md5` 替代 `hash()` | 断言 T8 + `test_score.py::test_deterministic` |
| NFR-4 可解释 | `Match.hits` 暴露 `(信号, 权重)` | `test_score.py::test_hits_exposed` |
| NFR-5 离线 | CI 不联网；fixture 全本地 | CI 无网络依赖步骤 |
| NFR-6 性能 | `grams_cached` + 单次扫描 | `test_bench.py`（1e4 粒 < 500ms，标记 `slow`） |

## 3. 债务清偿对照（HEALTH → 交付）

| 债 | 清偿方式 | 验证证据 |
|---|---|---|
| D1 两份脚本靠 md5 对齐 | 收敛为单一包，`__version__` 单点 | 仓库内只有一个 `seedbrain/`；`pip show` 版本一致 |
| D2 `PROFILES` 硬编码 | 全部外置到 `profiles/*.json` | `test_profile.py` 用纯 JSON 驱动全流程，无 Python 改动 |
| D3 验证套件不可复用 | `verify.CheckSuite` 作为库 API | `test_verify.py` 在 fixture 域上跑通 |
| D4 无包结构 | `src/` 布局 + `pyproject.toml` + `py.typed` | `pip install .` 后 `import seedbrain` |
| D5 无公开 API | `SeedBrain.load()` 等 6 个方法 | `examples/minimal.py` |
| D6 无版本导出 | `__version__` + CHANGELOG + tag | `python -c "import seedbrain; print(seedbrain.__version__)"` |
| D7 报告类不统一 | 单一 `Check` / `VerifyReport` 模型 | 全仓库只有一处 `class Report`（已删除） |

## 4. 断言追溯（上游 38 项 → SDK 参数化）

上游两个仓库共 38 项断言，在 SDK 里归为三组：

### 4.1 `core` 组（通用，任意领域都跑）—— 对应上游 27 项

| 上游 ID | SDK 断言 | 门槛来源 |
|---|---|---|
| T1a 唯一 / T1b 完整 / T1c ref 可解析 / T1d 非空壳 | `check_integrity` | 硬编码（不变量） |
| T1e 分层计数 / T1f 旧货架有效 | `check_layers` | `profile.verify.legacy_shelf` |
| T2a 名字召回 / T2b 特征词召回 | `check_recall` | `thresholds.recall_*` |
| T3a 基尼 / T3b 触达率 | `check_concentration` | `thresholds.gini_max` |
| T4 IDF top1 增益 | `check_idf` | `thresholds.idf_top1_gain` + `generic_fill` |
| T5 状态轮转 | `check_rotation` | `thresholds.rotation_min` |
| T6a 层饥饿 / T6b 垄断 | `check_balance` | `thresholds.layer_dominance_max` |
| T7a 边界输入 / T7b 状态缺字段 | `check_robustness` | 硬编码 |
| T8 确定性 | `check_determinism` | 硬编码 |
| T9a 去中心化 / T9b top1 多样性 | `check_decentralized` | `thresholds.decenter_min` + `legacy_shelf` |
| T10a/b/c 增量等价 | `check_incremental_equiv` | 硬编码 |
| T11a/b 增量无偏 | `check_incremental_unbiased` | `thresholds.recall_name` |
| T12 ID 稳定 | `check_id_stability` | 硬编码 |
| T13a/b 重复检测 | `check_dup_detection` | `norms.dup_threshold` |

### 4.2 `content` 组（可选，由 profile 声明）—— 对应上游 11 项

| 上游 ID | SDK 断言 | 配置项 |
|---|---|---|
| F 目录文件数 ×3 | `check_dirs` | `verify.content.dirs` |
| L1 条目数 | `check_entry_total` | `verify.content.expected_entries` |
| L2c 条目数 + 双向镜像 | `check_entry_mirror` | 同上 |
| S 分段自声明 | `check_section_declarations` | `verify.content.sections_re` |
| H1/H2 文件头声明 | `check_file_headers` | `verify.content.header_re` |
| SIX 六字段 | `check_fields` | `verify.content.fields` |
| DOC 文档声明 | `check_doc_declares` | `verify.content.docs` |

> 未声明 `verify.content` 的 profile 自动跳过该组（新领域可以只跑 core 组先上线）。

### 4.3 `schema` 组（profile 自身）

`check_profile_validity`：schema_version / layer-prefix 齐备 / 正则可编译 / 源存在 / quota 和 ≤ 1。

## 5. 验收对照

| AC | 证据 |
|---|---|
| AC-1 新领域零改代码 | `tests/test_profile.py::test_json_only_domain` + `profiles/example.json` |
| AC-2 上游不回退 | `tests/test_upstream_regression.py`（`@pytest.mark.upstream`）对比 27 项输出 |
| AC-3 零依赖 | CI `pip show` 断言 |
| AC-4 无内容污染 | CI `git grep` 白名单断言（只允许 `tests/fixtures/` 与 `profiles/` 出现示例词） |
| AC-5 首版即绿 | 首次 push 后 `gh run list` 全绿 |
| AC-6 README 自足 | 按 README 从零走到 `match` 成功 |

## 6. 变更历史

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-10-22 | v1 | 立项：五件套建立，未开始实现 |
