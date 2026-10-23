<p align="right">
  <b>English</b> · <a href="../zh-CN/getting-started.md">简体中文</a> ·
  <a href="../../README.md">← README</a>
</p>

# Getting started

This page takes you from zero to a working index. Every command below has been
executed against the released package — no aspirational examples.

---

## 1. Requirements

| Item | Value |
|---|---|
| Python | **3.9 – 3.13** |
| Runtime dependencies | **none** (standard library only) |
| Install size | ~60 KB |
| Network / GPU | not required, ever |

`seedbrain` does not use embeddings, so there is no model to download and no
service to reach. It runs in air-gapped CI, on a laptop, or inside a container
with no egress.

---

## 2. Install

### 2.1 From PyPI (recommended for library use)

```bash
pip install agent-seed-brain
seedbrain --version
```

### 2.2 From PyPI as an isolated CLI (recommended if you only use the command)

```bash
pipx install agent-seed-brain
seedbrain --version
```

`pipx` keeps the CLI in its own virtualenv so it cannot conflict with the rest
of your environment.

### 2.3 From source (recommended if you want the bundled example domain)

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
pip install -e .
seedbrain --version
```

### 2.4 Zero install

The engine is importable straight from a checkout:

```bash
git clone https://github.com/hhx465453939/agent-seed-brain
cd agent-seed-brain
PYTHONPATH=src python examples/minimal.py
```

---

## 3. What is actually inside the installed package

This trips people up, so it is worth stating plainly.

| Path | In wheel (pip) | In repo (git clone) |
|---|---|---|
| `seedbrain/` (engine + CLI) | ✅ | ✅ |
| `seedbrain/data/base.json` | ✅ | ✅ |
| `seedbrain/data/probes/core.json` | ✅ | ✅ |
| `profiles/example.json` | ❌ | ✅ |
| `tests/fixtures/mini-domain/` | ❌ | ✅ |

**Consequence:** after `pip install`, you cannot run
`seedbrain build --profile profiles/example.json` — that file belongs to the
repository, not to the installed package. You create your own profile instead
(step 4). The bundled example is only reachable from a checkout.

What *is* shipped inside the package is the part that matters for reuse:
`builtin:base` (shared defaults) and `builtin:probes/core` (eight cross-domain
probes). Those work after a plain `pip install`.

---

## 4. Five-minute walkthrough (pip install path)

Create a directory, add a few entries, point a profile at them.

```bash
mkdir my-brain && cd my-brain
mkdir notes
```

**`notes/methods.md`** — the source. The format is your choice; the profile
declares how to parse it. This example uses the compact table style:

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

**`seedbrain.json`** — the profile. `builtin:base` supplies norms, paths and
thresholds, so you only write what is domain-specific:

```json
{
  "extends": "builtin:base",
  "name": "numerics",
  "label": "Numerical Methods",
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
    "method": { "prefix": "m", "quota": 1.0, "label": "Methods" }
  },
  "verify": {
    "probes_ref": "builtin:probes/core",
    "probes": ["降维压缩，矩阵分解选型"]
  }
}
```

Now build and query:

```bash
seedbrain build  --profile seedbrain.json
seedbrain match  "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5
```

Expected shape of the output:

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

## 5. Prove it works

```bash
seedbrain verify --profile seedbrain.json
```

On the example above this reports **27/27 passed**. Two notes:

- It is 27, not 28, because the `T9 decentralization` check requires a
  `verify.legacy_shelf` list. Without one, T9 is skipped rather than faked —
  a check that cannot fail is worse than no check.
- **Very small corpora fail `T5` by design.** T5 requires four distinct top-1
  picks across six consecutive runs; with three entries that is physically
  impossible. The threshold is not lowered to accommodate toy data. If you are
  experimenting with a handful of entries, add `--group schema` to run only the
  structural checks.

To keep a machine-readable record:

```bash
seedbrain verify --profile seedbrain.json --json > verify.json
seedbrain verify --profile seedbrain.json --evidence reports/verify.md
```

> `--json` prints the human-readable progress lines first and the JSON object
> afterwards. If you need pure JSON, slice from the first `{`:
> `seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq .`

---

## 6. Where to go next

| Goal | Read |
|---|---|
| Full CLI and library API reference | [usage.md](usage.md) |
| Write a real profile (cards, layers, quotas, `extends`) | [profiles.md](profiles.md) |
| Understand why it ranks the way it does | [methodology.md](methodology.md) |
| Troubleshooting and known limits | [faq.md](faq.md) |

---

## 7. Troubleshooting

**`seedbrain: command not found`**
The entry point lives in the environment's `bin/` (`Scripts\` on Windows).
Either activate the virtualenv, use `python -m seedbrain.cli`, or install with
`pipx`.

**`✗ profile 非法：... 不是合法 JSON`**
Two usual causes: a Windows path written with single backslashes, and regexes
written with single backslashes. Inside JSON every backslash must be doubled:
`"^##\\s+(?P<group>.*)$"`.

**`源 '...' 解析出 0 条种子`**
Your `entry_re` does not match the file. The most common mismatch is the dash:
the default pattern expects a full-width double em dash `——`, not a single
`—`. Print one line of your source and compare character by character.

**`✗ 索引不存在：...（先跑 build）`**
`match` / `verify` / `stats` read the built index. Run `seedbrain build` first.
`build` is idempotent — running it twice produces byte-identical output.

**Installed a new version but behaviour did not change**
You may be running a different interpreter. Check with
`python -c "import seedbrain, sys; print(seedbrain.__file__, sys.version)"`.

---

## 8. Uninstall

```bash
pip uninstall agent-seed-brain
```

Your corpus, profiles and generated `references/` are plain files and are left
untouched — the package never writes outside the paths declared in the profile.
