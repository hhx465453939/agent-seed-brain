<p align="right">
  <a href="../en/getting-started.md">English</a> · <b>简体中文</b> ·
  <a href="../../README.zh-CN.md">← README</a>
</p>

# 快速上手

从零到可用索引。下面每条命令都在已发布的包上实际跑过，不是设想。

---

## 1. 环境要求

| 项目 | 值 |
|---|---|
| Python | **3.9 – 3.13** |
| 运行时依赖 | **零**（只用标准库） |
| 安装体积 | 约 60 KB |
| 网络 / GPU | 永远不需要 |

`seedbrain` 不用 embedding，所以没有模型要下载、没有服务要连。内网、离线容器、
断网 CI 都能跑。

---

## 2. 安装

### 2.1 从 PyPI（作为库使用，推荐）

```bash
pip install agent-seed-brain
seedbrain --version
```

### 2.2 从 PyPI 装成独立 CLI（只用命令行，推荐）

```bash
pipx install agent-seed-brain
seedbrain --version
```

`pipx` 把 CLI 放进独立虚拟环境，不会和你现有环境互相污染。

### 2.3 从源码（想用仓库自带的示例域，推荐）

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
pip install -e .
seedbrain --version
```

### 2.4 零安装

引擎可以直接从检出目录导入：

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
PYTHONPATH=src python examples/minimal.py
```

---

## 3. 装完之后包里到底有什么

这一点最容易被误解，值得说清。

| 路径 | wheel（pip 安装） | 仓库（git clone） |
|---|---|---|
| `seedbrain/`（引擎 + CLI） | ✅ | ✅ |
| `seedbrain/data/base.json` | ✅ | ✅ |
| `seedbrain/data/probes/core.json` | ✅ | ✅ |
| `profiles/example.json` | ❌ | ✅ |
| `tests/fixtures/mini-domain/` | ❌ | ✅ |

**直接后果**：`pip install` 之后不能跑
`seedbrain build --profile profiles/example.json` —— 那个文件属于仓库，不属于安装包。
你需要自己写一份 profile（见第 4 节）。自带示例只有从仓库检出才能用。

包里真正随版本分发的是复用所需的部分：`builtin:base`（公共默认值）和
`builtin:probes/core`（8 条跨领域探针）。这两个在普通 `pip install` 之后就能用。

---

## 4. 五分钟走完（pip 安装路径）

建目录、放几条内容、写一份 profile 指过去。

```bash
mkdir my-brain && cd my-brain
mkdir notes
```

**`notes/methods.md`** —— 源文件。格式由你定，profile 负责声明怎么解析。这里用
紧凑的条目式：

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

**`seedbrain.json`** —— profile。`builtin:base` 提供 norms / paths / 阈值，
所以只写本域特有的部分：

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
seedbrain build  --profile seedbrain.json
seedbrain match  "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5
```

输出形态：

```
✓ 12 粒种子
  分层：method 12
  → references/seed-index.jsonl
  → references/SEED-INDEX.md
```

```
 #  层              得分    新颖  id                         命中信号
─────────────────────────────────────────────────────────────────────────
 1  method        4.9  1.00  m-randomized-sketch        压缩·1.4  矩阵·1.4  降维压·0.7
 2  method        4.4  1.00  m-matrix-decomposition     分解·1.9  压缩·1.4  降维·1.4  矩阵·1.4
```

---

## 5. 证明它真的在工作

```bash
seedbrain verify --profile seedbrain.json
```

上面的示例会报 **27/27 通过**。两点说明：

- 是 27 不是 28：`T9 去中心化`需要 `verify.legacy_shelf`（你的「旧首选表」）。
  没配就**跳过**，而不是假装通过 —— 一个永远不会失败的检查比没有检查更坏。
- **极小的库会让 `T5` 失败，这是设计如此。** T5 要求 6 次连选中出现 4 个不同
  的 top1；只有 3 粒种子时这在算术上不可能。门槛不会为玩具数据下调。如果你
  只是想先试结构，用 `--group schema` 只跑结构性检查。

留一份机器可读的记录：

```bash
seedbrain verify --profile seedbrain.json --json > verify.json
seedbrain verify --profile seedbrain.json --evidence reports/verify.md
```

> `--json` 会先打印人类可读的进度行，再输出 JSON 对象。要纯 JSON 就从第一个
> `{` 截取：
> `seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq .`

---

## 6. 接下来读什么

| 目标 | 读这篇 |
|---|---|
| CLI 与库 API 完整参考 | [usage.md](usage.md) |
| 写一份真正的 profile（卡片 / 分层 / 配额 / extends） | [profiles.md](profiles.md) |
| 理解它为什么这样排序 | [methodology.md](methodology.md) |
| 排障与已知边界 | [faq.md](faq.md) |

---

## 7. 排障

**`seedbrain: command not found`**
入口脚本在环境的 `bin/`（Windows 是 `Scripts\`）。要么激活虚拟环境，要么用
`python -m seedbrain.cli`，要么用 `pipx install`。

**`✗ profile 非法：... 不是合法 JSON`**
两个常见原因：Windows 路径写了单反斜杠；正则写了单反斜杠。JSON 里每个反斜杠
都要写成两个：`"^##\\s+(?P<group>.*)$"`。

**`源 '...' 解析出 0 条种子`**
`entry_re` 没匹配上。最常见的是破折号：默认模式要的是全角双破折号 `——`，不是
单个 `—`。把源文件里的一行原样打出来，逐字符比对。

**`✗ 索引不存在：...（先跑 build）`**
`match` / `verify` / `stats` 读的是构建产物。先 `seedbrain build`。`build` 是
幂等的，跑两次输出逐字节一致。

**装了新版本但行为没变**
可能跑的是另一个解释器。用
`python -c "import seedbrain, sys; print(seedbrain.__file__, sys.version)"` 确认。

---

## 8. 卸载

```bash
pip uninstall agent-seed-brain
```

你的语料、profile、生成的 `references/` 都是普通文件，不会被删 —— 包从不写入
profile 之外声明的路径。
