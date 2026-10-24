<img src="assets/banner.svg" alt="seed brain" width="100%">

<p align="center">
  <a href="https://pypi.org/project/agent-seed-brain/"><img alt="PyPI" src="https://img.shields.io/pypi/v/agent-seed-brain?color=FFD400&labelColor=0A0A0A&style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%20~%203.13-00E5C0?style=flat-square&labelColor=0A0A0A">
  <img alt="Dependencies" src="https://img.shields.io/badge/runtime%20deps-0-7B5CFF?style=flat-square&labelColor=0A0A0A">
  <img alt="Tests" src="https://img.shields.io/badge/tests-107%20passing-FF2D78?style=flat-square&labelColor=0A0A0A">
  <img alt="License" src="https://img.shields.io/badge/license-Apache_2.0-blue?style=flat-square&labelColor=FFFFFF">
  <img alt="Status" src="https://img.shields.io/badge/status-open--source-2EA44F?style=flat-square&labelColor=0A0A0A">
</p>

<p align="center">
  <a href="README.md">English</a> · <b>简体中文</b>
</p>

<h3 align="center">把任意领域的知识，编译成智能体可<b>无偏检索</b>、可<b>增量演进</b>、可<b>自我验证</b>的「种子大脑」。</h3>

<p align="center">
  <kbd>zero dependencies</kbd> · <kbd>deterministic</kbd> · <kbd>explainable</kbd> · <kbd>verifiable</kbd>
</p>

---

## 它到底提升了什么

大多数 agent 在「选方案」这一步，靠的是**预训练语料里最高频的那几个词**。
这就是为什么你让它做科技感海报，它永远给你赛博霓虹；让它做数值计算，它永远给你梯度下降。

`seedbrain` 不提升模型的推理能力。它做的是另一件事：

> **把「选什么」从模型权重里搬出来，搬进一份可检索、可审计、可验证的数据里。**

| 环节 | 模型自己硬扛 | 有种子大脑 |
|---|---|---|
| **选什么** | 语料里最高频的那几个 | 全库等距平铺 + IDF 加权，低频但精确的条目也能被选中 |
| **稳定性** | 同一模型不同会话给出不同答案 | 确定性打分：同输入必得同输出 |
| **可解释** | 说不出为什么选它 | 每次输出命中信号与权重（`霓虹·4.3  长图·3.3`） |
| **积累** | 会话结束即遗忘 | 增量池 + 状态记忆，越用越准 |
| **防退化** | 无 | 28 项门槛断言 + CI，算法退化立刻红 |

## 为什么收益与 harness、模型规模无关

```
「选得对不对」   ← 由索引质量 + 匹配算法决定   ← 与模型无关
「选完之后怎么做」← 由模型推理能力决定         ← 与模型有关
```

`seedbrain` 只负责前半段。所以它在 **任何 harness（Claude Code / Codex / pi /
自建循环）、任何模型（强或弱）** 上的效果是一致的：弱模型从「瞎猜」变成「查到同样的
候选集」，强模型从「选得还行」变成「选得可解释、可复现」。

---

## 安装

**① 从 PyPI**

```bash
pip install agent-seed-brain
seedbrain --version
```

只想要命令行、不想污染环境：

```bash
pipx install agent-seed-brain
```

**② 从源码** —— 想用仓库自带的示例域就得走这条，因为 `profiles/` 与
`tests/fixtures/` 在仓库里，不在 wheel 里：

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
pip install -e .
seedbrain --version
```

**③ 零安装试用**

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
PYTHONPATH=src python examples/minimal.py
```

> **wheel 里到底装了什么**：引擎、`seedbrain/data/base.json`、
> `seedbrain/data/probes/core.json`。所以普通 `pip install` 之后
> `builtin:base` 与 `builtin:probes/core` 可用，示例 profile 不可用。
> 详见 [docs/zh-CN/getting-started.md §3](docs/zh-CN/getting-started.md#3-装完之后包里到底有什么)。

### 发布流水线

发布由 `.github/workflows/release.yml` 完成（Trusted Publishing / OIDC，不需要
API token），全链路幂等：验证 → 构建 → 发 PyPI（已存在的文件自动跳过）→ 建
GitHub Release（已存在则同步）。

- **正常发版**：改好 `pyproject.toml` 的 `version`，打 tag（`v0.4.0`）并推送。
  流水线会先断言 tag 与包版本一致，不一致直接拒绝。
- **补发历史版本**：手动触发，`tag` 填要补的版本（如 `v0.1.1`）。已存在的文件与
  release 会被跳过或更新，不会报错。

---

## 快速开始（pip 路径）

五分钟版本。这是 `pip install` 之后能真正跑通的那条路，已端到端验证。

```bash
mkdir my-brain && cd my-brain && mkdir notes
```

写 `notes/methods.md` —— 格式随你定，只要 profile 会解析：

```markdown
# Numerical Methods

## Matrix & decomposition

- **Matrix decomposition** · svd —— 奇异值分解，把矩阵拆成低秩结构，降维与压缩的通用手段
- **Low-rank approximation** · truncated-svd —— 截断奇异值，只保留最大的若干个，用于压缩与去噪
- **QR iteration** · qr —— QR 迭代求特征值，适合中小规模稠密矩阵
- **PCA projection** · pca —— 主成分投影，用方差最大的方向做线性降维
- **Randomized sketch** · sketch —— 随机投影草图，用低维嵌入近似原矩阵，降维压缩的近似加速

## Optimization

- **Gradient descent** · gd —— 沿负梯度方向迭代，最基础的一阶优化
- **Newton step** · newton —— 用二阶信息校正步长，收敛快但需要 Hessian
- **Conjugate gradient** · cg —— 共轭方向法，解大型稀疏线性系统
- **Backtracking line search** · backtracking —— 回溯线搜索，保证每步充分下降

## Statistics

- **Bootstrap CI** · resample —— 重采样估计置信区间，不依赖分布假设
- **Jackknife** · leave-one-out —— 留一法估计偏差与方差
- **Permutation test** · shuffle-test —— 置换检验，用打乱标签构造零分布
```

写 `seedbrain.json`：

```json
{
  "extends": "builtin:base",
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
  },
  "verify": {
    "probes_ref": "builtin:probes/core",
    "probes": ["降维压缩，矩阵分解选型"]
  }
}
```

构建并查询：

```bash
seedbrain build --profile seedbrain.json
seedbrain match "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5
```

```
 #  层              得分    新颖  id                         命中信号
─────────────────────────────────────────────────────────────────────────
 1  method        4.9  1.00  m-randomized-sketch        压缩·1.4  矩阵·1.4  降维压·0.7
 2  method        4.4  1.00  m-matrix-decomposition     分解·1.9  压缩·1.4  降维·1.4  矩阵·1.4
```

证明它真的在工作：

```bash
seedbrain verify --profile seedbrain.json     # 这个示例 27/27 通过
```

（是 27 不是 28：`T9` 需要 `verify.legacy_shelf`，没配就跳过而不是假装通过。
极小的库会让 `T5` 失败，这是设计如此 —— 6 次连选出现 4 个不同 top1，三条数据
在算术上做不到。）

→ 完整走查、排障、卸载：[docs/zh-CN/getting-started.md](docs/zh-CN/getting-started.md)

---

## 部署到 agent harness

`seedbrain` 是**库 + CLI**，不绑定任何 harness。两种接法：

**A. 当作命令行工具（最常见）**

在 agent 的规则文件里加一句「选方案前先跑 `seedbrain match`」：

```bash
seedbrain match "科技感长图，深色底霓虹" \
  --profile profiles/taste.json \
  --root ~/agent-taste-seed-system \
  --k 8
```

**B. 当作库嵌入自建循环**

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("seedbrain.json")
if not brain.seeds:
    brain.build()

for m in brain.match("降维压缩，矩阵分解选型", k=5):
    print(f"{m.total:6.1f}  {m.seed.id:<28} {m.hits[:2]}")

brain.pick("m-matrix-decomposition", score=5, note="一次过")
```

`--root` 指向**内容所在的仓库**。SDK 仓库里只有解析规则，不含任何种子内容 ——
这是许可隔离的前提。

---

## 接入你自己的领域

一个领域 = 一份 JSON。**不写一行 Python。**

```jsonc
{
  "extends": "builtin:base",          // 公共 norms / paths / 阈值
  "name": "my-domain",
  "sources": [
    {
      "kind": "table",                // 单行速查总库
      "path": "docs/methods.md",
      "layer": "method",
      "group_re": "^##\\s+(?P<group>.*)$",
      "entry_re": "^-\\s*\\*\\*(?P<name>[^*]+?)\\*\\*\\s*·\\s*(?P<tag>[^—]+?)\\s*——\\s*(?P<desc>.+)$"
    },
    {
      "kind": "card",                 // 一张卡一粒种子
      "dir": "docs/cards",
      "layer": "card",
      "title_re": "^#\\s+(?P<title>.+)$",
      "field_re": "^>\\s*\\*\\*(?P<key>[^*]+?)\\*\\*\\s*[：:]\\s*(?P<val>.*)$"
    }
  ],
  "layers": {
    "method": { "prefix": "m",  "quota": 0.6 },
    "card":   { "prefix": "cd", "quota": 0.4 }
  }
}
```

合并规则只有两条：**dict 递归合并，list 与标量整体替换**。所以探针需要自己的字段：

```jsonc
{
  "verify": {
    "probes_ref": "builtin:probes/core",        // 池在前
    "probes": ["本域特有任务一", "本域特有任务二"]  // 本域在后
  }
}
```

`builtin:` 解析到安装包内部，所以领域仓库能引用公共配置而**零复制、零漂移**，
随 SDK 版本走。

看不明白某个值从哪来？

```bash
seedbrain config --profile my-domain.json --chain   # 继承链：谁是父
seedbrain config --profile my-domain.json           # 合并后的最终配置
```

→ 完整字段参考：[docs/zh-CN/profiles.md](docs/zh-CN/profiles.md)

---

## 它治的三个真实病灶

<table>
<tr><td width="33%" valign="top">

**① 首选表只有十几行**

人工写的「快速索引」结构性地让库里绝大多数条目**永远没有入口**。不是作者偏，
是入口太窄。

</td><td width="33%" valign="top">

**② 同一个任务反复命中同一条**

没有状态记忆，模型每次都在同一批高频项里打转。

</td><td width="34%" valign="top">

**③ 改了库忘了重建索引**

检索层继续返回旧快照，新条目永远召不回来，**且不报错**。

</td></tr>
</table>

## 四个机制（都不靠随机）

| 机制 | 治什么 | 数学形式 |
|---|---|---|
| **IDF 加权** | 低频但精确的信号被高频通用词淹没 | `log(1 + N/(1+df))` |
| **跨层配额** | 条目多的层把条目少的层挤成药渣 | 两阶段：先按层保底，再全局补满 |
| **时间衰减** | 同一任务反复命中同一条 | `recovery × 次数惩罚`，14d 半衰，下限 0.15 |
| **增量等价** | 新增会打乱旧 ID 与历史引用 | 只加后缀不改写；split-half 逐位等价 |

**刻意不用随机数**：合适性由 IDF 决定（确定、可解释、可复现）；多样性由状态记忆
产生 —— 同一任务隔几天再跑，会拿到不同的**同等合适**候选，而不是随机的**不合适**候选。

→ 推导、取舍与已知边界：[docs/zh-CN/methodology.md](docs/zh-CN/methodology.md)

---

## 验证：它自己证明自己

```bash
seedbrain verify --profile profiles/example.json
seedbrain verify --profile profiles/example.json --evidence reports/verify.md
```

```
[PASS] T1a ID 唯一                  重复 0 个
[PASS] T2a 名字自召回@8              100.0%
[PASS] T3a 命中基尼系数               0.154
[PASS] T4a IDF 单调性                df=1「假设」2.48 vs df=19「信号」0.74
[PASS] T5  6 次连选的 top1 多样性      4 个不同
[PASS] T6a 层饥饿（有货却没给位）        0 次
[PASS] T9  top1 落在旧货架之外         50.0%
[PASS] T10 增量等价                 22/22 逐位一致
...
结果：28/28 通过
```

配套 **107 个单元 / 集成测试**（标准库 `unittest`，不装任何东西就能跑）：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

> 断言是真的会失败的。本项目在开发期就被自己的断言抓出过两个真 bug：
> 「配额只有上限没有下限」（弱层有货却拿不到位）、「novelty 下限乘完次数惩罚掉到
> 0.11」（复现失效）。

→ 断言分组、退出码、CI 配方：[docs/zh-CN/usage.md](docs/zh-CN/usage.md)

---

## 生产实例：美学大脑

<a href="https://github.com/hhx465453939/agent-taste-seed-system"><img src="https://img.shields.io/badge/agent--taste--seed--system-美学大脑-FF2D78?style=flat-square&labelColor=0A0A0A"></a>

[`agent-taste-seed-system`](https://github.com/hhx465453939/agent-taste-seed-system)
用这套引擎管理 **24 章 250+ 艺术家的风格种子库**（352 粒章档 + 12 张代码基因卡 +
10 份情绪档）。

它解决的问题是：不同视觉任务老是收敛到赛博霓虹 / 瑞士平面那几粒。

| 指标 | 数值 |
|---|---|
| top1 落在「旧首选表」之外 | **62.5%**（15/24 任务） |
| top1 自身多样性 | 21/24 个不同 |
| IDF 开/关 的 top1 命中率 | **100% vs 11.5%** |
| 同一任务连选 6 次的不同 top1 | 6 个 |

> SDK 与内容严格分离：本仓库只有引擎与解析规则，**一根种子都不打包**。
> 美学大脑的语料在它自己的仓库里，适用那个仓库的许可；本仓库采用
> Apache-2.0。两者是各自独立的版权客体。

---

## 文档

| 主题 | English | 简体中文 |
|---|---|---|
| 安装、第一次建索引、排障 | [getting-started](docs/en/getting-started.md) | [快速上手](docs/zh-CN/getting-started.md) |
| CLI 与库 API 参考 | [usage](docs/en/usage.md) | [使用参考](docs/zh-CN/usage.md) |
| Profile schema、`extends`、`probes_ref` | [profiles](docs/en/profiles.md) | [Profile 参考](docs/zh-CN/profiles.md) |
| 算法、取舍、已知边界 | [methodology](docs/en/methodology.md) | [方法论](docs/zh-CN/methodology.md) |
| 常见问题与排障 | [faq](docs/en/faq.md) | [常见问题](docs/zh-CN/faq.md) |

贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md) · 变更记录：[CHANGELOG.md](CHANGELOG.md)
· 安全：[SECURITY.md](SECURITY.md) · 行为准则：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

---

## 许可

**Apache License 2.0** —— 覆盖整个仓库，不再按资产类型分治。

| 资产 | 许可 |
|---|---|
| 本仓库代码（`src/`、`examples/`） | **Apache-2.0** |
| `profiles/*.json` | Apache-2.0（**只有解析规则，无种子内容**） |
| `tests/fixtures/` | Apache-2.0（自写中性示例） |
| 名称「seed brain / 种子大脑」与 banner | **保留所有权利**（商标与视觉识别，不在许可范围内） |
| 上游美学大脑的种子文本 | **不在本仓库** —— 适用其自身仓库的许可 |

完整条款见 [LICENSE](LICENSE)，署名与保留标识见 [NOTICE](NOTICE)。

### 版本轨迹：v0.5.0 起再许可

**v0.3.x 及更早**版本以 **CC BY-NC-SA 4.0**（非商业 + 相同方式共享）发布，
这些旧版本继续适用其原始许可 —— 已经授予的许可不可撤销。
**自 v0.5.0 起整个仓库以 Apache-2.0 提供**，这是 OSI 认可的开源许可：
商业使用、修改与再分发均被允许，仅需遵守其署名与 NOTICE 要求。

从未发布过 v0.4.0；v0.5.0 直接跳到前面，路线图里的可选向量后端仍在待办。

---

## 路线图

- [x] v0.1.0 —— 等距平铺 / IDF 匹配 / 跨层配额 / 状态衰减 / 增量池 / 28 项断言 / CLI + 库 API
- [x] v0.2.0 —— profile 继承（`extends`）与 `seedbrain config`
- [x] v0.3.0 —— 探针可组合（`probes_ref`）与 `builtin:` 包内引用
- [ ] v0.4.0 —— 可选向量后端（保持零依赖默认路径不变）
- [ ] v1.0.0 —— API 冻结 + 迁移指南

---

<p align="center">
  <sub>Built with <a href="https://github.com/hhx465453939/agent-taste-seed-system">aesthetic-brain</a> ·
  Apache-2.0 · 开源 · 零运行时依赖</sub>
</p>
