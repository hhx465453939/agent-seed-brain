<img src="assets/banner.svg" alt="seed brain" width="100%">

<p align="center">
  <a href="https://pypi.org/project/agent-seed-brain/"><img alt="PyPI" src="https://img.shields.io/pypi/v/agent-seed-brain?color=FFD400&labelColor=0A0A0A&style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%20~%203.13-00E5C0?style=flat-square&labelColor=0A0A0A">
  <img alt="Dependencies" src="https://img.shields.io/badge/runtime%20deps-0-7B5CFF?style=flat-square&labelColor=0A0A0A">
  <img alt="Tests" src="https://img.shields.io/badge/tests-107%20passing-FF2D78?style=flat-square&labelColor=0A0A0A">
  <img alt="License" src="https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-0A0A0A?style=flat-square&labelColor=FFFFFF">
  <img alt="Status" src="https://img.shields.io/badge/status-source--available-FF2D78?style=flat-square&labelColor=0A0A0A">
</p>

<h3 align="center">把任意领域的知识，编译成智能体可<b>无偏检索</b>、可<b>增量演进</b>、可<b>自我验证</b>的「种子大脑」。</h3>

<p align="center">
  <kbd>zero dependencies</kbd> · <kbd>deterministic</kbd> · <kbd>explainable</kbd> · <kbd>verifiable</kbd>
</p>

---

## 它到底提升了什么

大多数 agent 在"选方案"这一步，靠的是**预训练语料里最高频的那几个词**。
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

这条因果链是项目的存在理由：

```
「选得对不对」   ← 由索引质量 + 匹配算法决定   ← 与模型无关
「选完之后怎么做」← 由模型推理能力决定         ← 与模型有关
```

`seedbrain` 只负责前半段。所以它在 **任何 harness（Claude Code / Codex / pi / 自建循环）、任何模型（强或弱）** 上的效果是一致的：
弱模型从"瞎猜"变成"查到同样的候选集"，强模型从"选得还行"变成"选得可解释、可复现"。

---

## 安装

**① 从源码（当前可用，无需等 PyPI）**

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
pip install -e .
seedbrain --version
```

**② 从 PyPI**

```bash
pip install agent-seed-brain
```

> 发布由 `.github/workflows/release.yml` 完成（Trusted Publishing / OIDC，不需要 API token），
> 全链路幂等：验证 → 构建 → 发 PyPI（已存在的文件自动跳过）→ 建 GitHub Release（已存在则同步）。
>
> - **正常发版**：把 `pyproject.toml` 的 `version` 改好，打 tag（`v0.4.0`）并推送即可。
>   流水线会先断言 tag 与包版本一致，不一致直接拒绝发布。
> - **补发历史版本**：手动触发该 workflow，`tag` 填要补的版本（如 `v0.1.1`），
>   `publish` 决定是否同时发 PyPI。已存在的文件与 release 都会被跳过/更新，不会报错。

**③ 零安装试用**

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
PYTHONPATH=src python examples/minimal.py
```

---

## 部署到 agent harness

`seedbrain` 是**库 + CLI**，不绑定任何 harness。两种接法：

**A. 当作命令行工具（最常见）**

在 agent 的规则文件里加一句「选方案前先跑 `seedbrain match`」，它就会在执行前查库：

```bash
seedbrain match "科技感长图，深色底霓虹" \
  --profile profiles/taste.json \
  --root ~/agent-taste-seed-system \
  --k 8
```

**B. 当作库嵌入自建循环**

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("profiles/taste.json", root="~/agent-taste-seed-system")
for m in brain.match(task, k=8):
    ...
```

**接上已有的知识库（SDK 与内容分离）**

```bash
seedbrain build  --profile profiles/taste.json --root ~/agent-taste-seed-system
seedbrain verify --profile profiles/taste.json --root ~/agent-taste-seed-system
```

`--root` 指向**内容所在的仓库**。SDK 仓库里只有解析规则，不含任何种子内容——这是许可隔离的前提。

---

## 30 秒

```bash
pip install agent-seed-brain
```

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("profiles/example.json")   # 仓库内自带最小示例域
brain.build()

for m in brain.match("降维压缩，矩阵分解选型", k=5):
    print(f"{m.total:6.1f}  {m.seed.id:<24} {m.hits[:2]}")
#    6.5  tl-矩阵分解               (('矩阵', 1.8), ('阵分', 1.8))
#    4.1  tl-奇异值截断             (('降维', 1.8), ('压缩', 1.8))
```

想先看它体检？

```bash
seedbrain verify --profile profiles/example.json
```

---

## 它治的三个真实病灶

<table>
<tr><td width="33%" valign="top">

**① 首选表只有十几行**

人工写的"快速索引"结构性地让库里绝大多数条目**永远没有入口**。不是作者偏，是入口太窄。

</td><td width="33%" valign="top">

**② 同一个任务反复命中同一条**

没有状态记忆，模型每次都在同一批高频项里打转。

</td><td width="34%" valign="top">

**③ 改了库忘了重建索引**

检索层继续返回旧快照，新条目永远召不回来，**且不报错**。

</td></tr>
</table>

---

## 四个机制（都不靠随机）

| 机制 | 治什么 | 数学形式 |
|---|---|---|
| **IDF 加权** | 低频但精确的信号被高频通用词淹没 | `log(1 + N/(1+df))` |
| **跨层配额** | 条目多的层把条目少的层挤成药渣 | 两阶段：先按层保底，再全局补满 |
| **时间衰减** | 同一任务反复命中同一条 | `recovery × 次数惩罚`，14d 半衰，下限 0.15 |
| **增量等价** | 新增会打乱旧 ID 与历史引用 | 只加后缀不改写；split-half 逐位等价 |

**刻意不用随机数**：合适性由 IDF 决定（确定、可解释、可复现）；多样性由状态记忆产生——同一任务隔几天再跑，会拿到不同的**同等合适**候选，而不是随机的**不合适**候选。

---

## 验证：它自己证明自己

```bash
seedbrain verify --profile profiles/example.json --evidence docs/EVIDENCE.md
```

```
[PASS] T1a ID 唯一                  重复 0 个
[PASS] T2a 名字自召回@8              100.0%（漏 0）
[PASS] T3a 命中基尼系数               0.154
[PASS] T4a IDF 单调性                df=1「假设」2.48 vs df=19「信号」0.74
[PASS] T5  6 次连选的 top1 多样性      4 个不同
[PASS] T6a 层饥饿（有货却没给位）        0 次
[PASS] T9  top1 落在旧货架之外         50.0%
[PASS] T10 增量等价                 22/22 逐位一致
[PASS] T13 同义别名被识别             命中 cd-sampling（1.00）
...
结果：28/28 通过
```

配套 **91 个单元/集成测试**（标准库 `unittest`，不装任何东西就能跑）：

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

> 断言是真的会失败的。本项目在开发期就被自己的断言抓出过两个真 bug：
> 「配额只有上限没有下限」（弱层有货却拿不到位）、「novelty 下限乘完次数惩罚掉到 0.11」（复现失效）。

---

## 生产实例：美学大脑

<a href="https://github.com/hhx465453939/agent-taste-seed-system"><img src="https://img.shields.io/badge/agent--taste--seed--system-美学大脑-FF2D78?style=flat-square&labelColor=0A0A0A"></a>

[`agent-taste-seed-system`](https://github.com/hhx465453939/agent-taste-seed-system) 用这套引擎管理 **24 章 250+ 艺术家的风格种子库**（352 粒章档 + 12 张代码基因卡 + 10 份情绪档）。

它解决的问题是：不同视觉任务老是收敛到赛博霓虹 / 瑞士平面那几粒。

接入后的实测：

| 指标 | 数值 |
|---|---|
| top1 落在「旧首选表」之外 | **62.5%**（15/24 任务） |
| top1 自身多样性 | 21/24 个不同 |
| IDF 开/关 的 top1 命中率 | **100% vs 11.5%** |
| 同一任务连选 6 次的不同 top1 | 6 个 |

> SDK 与内容严格分离：本仓库只有引擎与解析规则，**一根种子都不打包**。
> 美学大脑的语料在它自己的仓库里，遵循 CC BY-NC-SA 4.0；本仓库同样采用
> CC BY-NC-SA 4.0，但两者是各自独立的版权客体。

---

## 接入你自己的领域

一个领域 = 一份 JSON。**不写一行 Python。**

```jsonc
{
  "schema_version": 1,
  "name": "my-domain",
  "sources": [
    {
      "kind": "table",                       // 单行速查总库
      "path": "docs/methods.md",
      "layer": "method",
      "group_re": "^##\\s+(?P<group>.*)$",
      "entry_re": "^-\\s*\\*\\*(?P<name>[^*]+?)\\*\\*\\s*·\\s*(?P<tag>[^—]+?)\\s*——\\s*(?P<desc>.+)$"
    },
    {
      "kind": "card",                        // 一张卡一粒种子
      "dir": "docs/cards",
      "layer": "card",
      "title_re": "^#\\s+(?P<title>.+)$",
      "field_re": "^>\\s*\\*\\*(?P<key>[^*]+?)\\*\\*\\s*[：:]\\s*(?P<val>.*)$"
    }
  ],
  "layers": {
    "method": { "prefix": "m",  "quota": 0.6 },
    "card":   { "prefix": "cd", "quota": 0.4 }
  },
  "paths": {
    "index_jsonl": ".seedbrain/index.jsonl",
    "index_md":    ".seedbrain/SEED-INDEX.md",
    "additions":   ".seedbrain/additions.jsonl",
    "state":       ".seedbrain/state.json"
  }
}
```

```bash
seedbrain build  --profile my-domain.json
seedbrain match  "你的任务描述" --profile my-domain.json
seedbrain verify --profile my-domain.json
```

**只写差异：`extends` 继承**

公共参数（`norms` / `paths` / 阈值）放进 `profiles/base.json`，领域 profile 只写差异：

```jsonc
{
  "extends": "base.json",
  "name": "my-domain",
  "sources": [ /* 本域特有 */ ],
  "layers":  { /* 本域特有 */ },
  "verify":  { "probes": [ /* list 整体替换 */ ] }
}
```

合并规则只有两条：**dict 递归合并，list 与标量整体替换**。
（list 不合并，是因为「想清空从 base 继承来的 probes」必须能表达。）

**探针也能复用：`probes_ref`**

`verify.probes` 是 list，按上表规则会被**整体替换** —— 所以它不能用 `extends` 继承。
探针复用走独立字段：

```jsonc
{
  "verify": {
    "probes_ref": "builtin:probes/core",           // 引用公共池（池在前）
    "probes": ["本域特有任务 1", "本域特有任务 2"]   // 追加（本域在后）
  }
}
```

`builtin:` 前缀解析到 SDK 包内 `seedbrain/data/`，所以领域仓库不用复制任何文件：

```jsonc
{ "extends": "builtin:base" }
```

这是跨仓库引用的正解 —— **零复制、零漂移、随 SDK 版本走**。

看不明白某个值从哪来？

```bash
seedbrain config --profile my-domain.json --chain   # 继承链：谁是父
seedbrain config --profile my-domain.json           # 合并后的最终配置
```

细节见 [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)。

---

## 运行时新增（不改源文件）

```bash
seedbrain add \
  --name "共形 PID 控制" \
  --layer method \
  --signals "在线控制,分布漂移,覆盖率保证" \
  --ref docs/methods.md
```

写入增量池 → 自动重建 → **立即可检索**。三道护栏：`ref` 必须真实存在（防静默断链）、同层查重（包含度 ≥0.75）、ID 撞车只加后缀不改写。

---

## 许可

| 资产 | 许可 |
|---|---|
| 本仓库代码（`src/`、`examples/`） | **CC BY-NC-SA 4.0** |
| `profiles/*.json` | CC BY-NC-SA 4.0（**只有解析规则，无种子内容**） |
| `tests/fixtures/` | CC BY-NC-SA 4.0（自写中性示例） |
| 名称「seed brain / 种子大脑」与 banner | **保留所有权利**（不在许可范围内） |
| 上游美学大脑的种子文本 | CC BY-NC-SA 4.0（**不在本仓库**） |

**这是 source-available，不是 OSI 认可的开源软件**（NC / SA 条款与开源定义不兼容）。
完整条款见 [`LICENSE`](LICENSE)，权利保留与来源说明见 [`NOTICE`](NOTICE)。

### 商业使用

本项目采用**非商业**许可。以下情形需要单独的商业授权：

- 集成进付费产品、SaaS、或企业内部生产系统
- 用它提供咨询、外包、培训等收费服务
- 在闭源产品中分发或嵌入

授权方式：开一个标题为 `commercial license` 的 issue 即可开始沟通。
贡献者已授予维护者再许可权（见 [`CONTRIBUTING.md`](CONTRIBUTING.md)），
因此单份商业许可可以覆盖整个代码库。

> 非商业用途（学习、研究、个人项目、非营利项目）无需授权，直接使用即可。

---

## 路线图

- [x] v0.1.0 — 等距平铺 / IDF 匹配 / 跨层配额 / 状态衰减 / 增量池 / 28 项断言 / CLI + 库 API
- [ ] v0.2.0 — profile 继承（领域公共配置复用）
- [ ] v0.3.0 — 可选向量后端（保持零依赖默认路径不变）
- [ ] v1.0.0 — API 冻结 + 迁移指南

---

<p align="center">
  <sub>Built with <a href="https://github.com/hhx465453939/agent-taste-seed-system">aesthetic-brain</a> · 
  CC BY-NC-SA 4.0 · source-available · zero runtime dependencies</sub>
</p>
