# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **双语文档体系**：`README.md` 改为英文（GitHub / PyPI 默认），新增
  `README.zh-CN.md` 中文版，两份顶部互相链接。
- **`docs/en/` 与 `docs/zh-CN/` 各五篇**：`getting-started`（安装与首次建索引）、
  `usage`（CLI + 库 API 全量参考）、`profiles`（schema / `extends` / `probes_ref` /
  `builtin:`）、`methodology`（原理与已知边界）、`faq`（排障）。各语言版本的 README
  只链接同语言的 docs。
- **README 补齐 pip 安装后的真实路径**：明确 wheel 里只有引擎与
  `data/`，不含 `profiles/example.json` 与测试夹具，并给出一条实测可跑通的
  最小示例（12 粒 → `build` / `match` / `verify` 27/27）。

### Changed

- **README 瘦身为「概览 + 可立即执行的命令」**，四个机制的推导、边界与排障细节
  下放到 `docs/`，README 只做引用。
- **删除 `docs/METHODOLOGY.md`**：内容已双语化迁入
  `docs/{en,zh-CN}/methodology.md`，跳转页无独家内容，留着只是第二个入口。
  同步修正 `CONTRIBUTING.md`、`SECURITY.md`、`src/seedbrain/__init__.py` 的引用。
- **消除文档重复**：完整最小示例（源文件 + profile 全文）此前在 README 与
  `docs/*/getting-started.md` 各存一份（双语共四份），现在只在 README 维护，
  getting-started 改为引用并保留验收输出。
- `MANIFEST.in` 纳入 `README.zh-CN.md`；sdist 同时携带两套 README。

### Fixed

- **`--root` 帮助文案与实现不一致**：实际规则是「显式参数 → profile 的 `root` 字段
  → 父目录名为 `profiles/` 时取上一级 → 否则取 profile 所在目录」，原文案只写了
  最后两条的特例。现已在 `--help` 与 `docs/*/usage.md` 中对齐。
- **发布流水线幂等化**：`pypa/gh-action-pypi-publish` 启用 `skip-existing`。
  此前重复触发同一版本的发布，PyPI 会返回 `400 File already exists`，把一条
  「其实早就发布成功」的 run 变成红叉 —— 红色只应代表真的出问题。
- **补上 GitHub Release 步骤**：`release.yml` 原先只发 PyPI，不创建 GitHub
  Release，导致 v0.1.0–v0.3.0 四个 tag 在 GitHub 上均无 release 页面、无产物下载。
  新增 `github-release` job：从 `CHANGELOG.md` 提取本版本小节作为 release 说明，
  附上 sdist + wheel，已存在则同步而非报错。
- **tag ↔ 包版本一致性闸门**：`verify` 在安装前断言 `ref` 与
  `pyproject.toml` 的 `version` 一致。补发历史版本时最容易 checkout 错 ref，
  把新代码以旧版本号推上 PyPI —— 而 PyPI 不允许覆盖同名文件，只能 yank + 升版本。
- **`workflow_dispatch` 支持指定 `tag` 与 `publish`**：补发历史版本时 checkout
  指定 tag，不再依赖「切到某分支再手动跑」这种容易搞错的姿势；也可只验证/构建而不发布。
- **tag 推送直接发布**：原先推 `v*` tag 只做验证与构建，必须再手动跑一次才发 PyPI，
  这个人工环节正是「漏发 / 重复补发」的温床。现在 tag 推送即完成全链路，
  手动触发保留为补发通道。

## [0.3.0] - 2026-10-23

### Added

- **`probes_ref`：探针池可组合**。`verify.probes_ref` 引用公共池，`verify.probes`
  作为本域追加（**池在前 + 本域在后**）。解决 v0.2 遗留问题：`extends` 对 list
  是整体替换，导致探针无法「继承公共 + 追加特有」。
- **`builtin:` 引用**：`extends` 与 `probes_ref` 都支持 `builtin:name` 前缀，
  解析到包内 `seedbrain/data/`。领域仓库可直接写 `"extends": "builtin:base"`，
  **零复制、零漂移、随 SDK 版本走** —— 跨仓库引用的正解。
- **包内数据**：`src/seedbrain/data/base.json`（公共配置）+
  `data/probes/core.json`（8 条跨领域任务形态探针），已写入 `package-data` 与
  `MANIFEST.in`（漏了会在 pip 安装后失效）。
- **`config --show` 报告探针来源**：`Profile.probes_source = {ref, pool, local}`。

### Changed

- `profiles/base.json` **移除**：改为包内 `data/base.json` 单一源，避免两份副本漂移。
- `profiles/example.json`：改为 `extends: "builtin:base"` +
  `probes_ref: "builtin:probes/core"`（探针 8 公共 + 4 本域 = 12 条）。
- 测试 99 → **107**（8 个 probes_ref / builtin 用例：追加顺序 / 缺失 / 空池 /
  坏 JSON / 回归 / builtin 解析 / builtin 缺失 / 来源记录）。

### Fixed

- **T5 状态轮转误判**：`check_rotation` 原先取 `probes[0]`，拼接探针池后第一条是
  抽象形态探针，对具体领域零命中 → 必然 0 个不同。改为**选命中数最多的探针**；
  若最佳探针只命中 < 2 粒，报 FAIL 并说明「探针太窄」——这是可诊断的失败，
  不是算法失效。

## [0.2.0] - 2026-10-23

### Added

- **profile 继承（`extends`）**：领域配置只写差异，公共的 `norms` / `paths` /
  `verify.thresholds` 从 `profiles/base.json` 继承。合并规则固定：
  **dict 递归合并，list 与标量整体替换**（list 不合并，是因为「想清空从 base
  继承来的 probes」必须能表达）。
- **`seedbrain config`**：打印合并后的最终配置；`--chain` 只打印继承链。
  继承最大的风险不是写错，而是**排不出来** —— 没有这条命令，出问题只能靠猜
  「这个阈值到底来自 base 还是自己写的」。
- **循环继承检测**：A→B→A 直接报错（带完整链路），不会递归到栈溢出。

### Changed

- `profiles/example.json` 改为继承 `profiles/base.json`，只保留本域差异。
- 测试 91 → **99**（新增 8 个继承用例：递归合并 / list 替换 / 不改 base /
  循环 / 缺失 base / 继承链记录 / base 正则报错 / 端到端等价）。

## [0.1.1] - 2026-10-22

### Fixed

- **card 层名字解析**：`_clean()` 的 docstring 写着「去掉 emoji」，实现里却没有 emoji 正则。
  卡片 H1 形如 `🧮 code-recipe · 01 线性代数与矩阵分解`，按 `·` 切出的第一段是
  `🧮 code-recipe`，与 `template_parts` 里的 `code-recipe` 不相等 → 模板段过滤失效 →
  种子名字变成 `🧮 code-recipe`。在数学域 204 粒中造成 9 粒「用名字召回失败」。
- **T2a / T11a 的统计口径**：单字名（如「群」）在 2-gram 方案下 `grams()` 为空，
  用名字召回是不可能的。现在排除出分母并在 metric 里报出排除数——降门槛或隐短样本都是放水。

### Verified

三域实测：example 28/28；数学 28/28（T2a 95.1% → 100%，排除 1 个单字名）；
美学 28/28（T2a 98.9% → 100%，T9 去中心化 75%）。

## [0.1.0] - 2026-10-22

### Fixed

- **Python 3.9 兼容**：`Path.write_text(newline=...)` 的 `newline` 参数是 3.10 才引入的，
  在 3.9 上抛 `TypeError`。影响面不止 `build` —— `pick`（写 state）与
  `verify --evidence`（写 Markdown）同样会炸，三条主路径在 3.9 上全不可用。
  统一改为 `Path.open(newline="\n")` + `write()`：3.9 支持，且保留显式 LF 语义，
  跨平台幂等不受影响。由 CI 的 `py3.9 / ubuntu-latest` 矩阵抓到。

首个公开版本。把「种子大脑」从两个领域仓库里的复制粘贴脚本，抽成领域无关的 SDK。

### Added

- **等距平铺索引**：全库每粒种子一行、同等曝光、无「首选 / 备选」层级；排序按层 + ID 字典序，刻意不按重要性。
- **IDF 加权匹配**：字符 2~3-gram + `log(1 + N/(1+df))` 加权，让低频但精确的信号浮上来。
- **跨层两阶段配额**：先按层保底、再全局补满 —— 弱层有货不会被强层饿死。
- **状态记忆与时间衰减**：14 天半衰 + 次数惩罚，下限 0.15 保住复现能力；多样性来自状态而非随机数。
- **增量池**：`add` 写入独立 JSONL，不改源文件；三条硬约束（老 ID 零改写 / 增量 ≡ 全量 / ref 必须存在）。
- **28 项验证断言**：可达性 / 集中度 / IDF 单调性 / 状态轮转 / 跨层均衡 / 鲁棒性 / 确定性 / 去中心化 / 增量等价 / 增量无偏 / ID 稳定 / 重复检测 / profile 合法性 / 内容层（可选）。
- **CLI 与库 API**：`seedbrain build|match|pick|add|verify|stats`，以及 `SeedBrain.load(...)` 门面。
- **profile 驱动的领域配置**：JSON schema，新增领域不写 Python。
- **91 个单元与集成测试**：标准库 `unittest`，无需安装任何测试框架。

### Security

- 知识源与 `ref` 强制落在 root 内（防路径穿越）；I/O 位置（索引/状态/增量池）允许外部路径。
- 增量查重用**包含度**而非 Jaccard，避免短候选 vs 长文档时永不告警。
- JSON 解析对损坏行优雅跳过，不阻塞主流程。

### License

- 采用 **CC BY-NC-SA 4.0**（署名 — 非商业性使用 — 相同方式共享）。
- 商业使用需单独书面授权；贡献者授予维护者再许可权，保证单份商业许可可覆盖全库。
- 名称「seed brain / 种子大脑」与 banner 不在许可范围内（保留所有权利）。
- 这是 **source-available** 软件，不是 OSI 认可的开源软件。

### Notes

- 与本仓库配套的生产实例是 [agent-taste-seed-system](https://github.com/hhx465453939/agent-taste-seed-system)（美学大脑）。
  它的种子文本为 CC BY-NC-SA 4.0，**不在本仓库分发**；本仓库只带解析规则 `profiles/taste.json`。
- 运行时零第三方依赖，支持 Python 3.9 ~ 3.13。

[Unreleased]: https://github.com/hhx465453939/agent-seed-brain/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/hhx465453939/agent-seed-brain/releases/tag/v0.1.0
