# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
