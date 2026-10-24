# AGENTS.md

`seedbrain` —— 把任意领域的知识编译成可**无偏检索**、可**增量演进**、可**自我验证**的种子索引。
零运行时依赖，纯标准库，Python 3.9–3.13。

**本文件是项目治理的唯一权威。**
细节分别落在 [CONTRIBUTING.md](CONTRIBUTING.md)（贡献流程）、
[docs/](docs/)（双语使用文档）、[tasks/archive/](tasks/archive/)（立项与决策存档，已完成项归档于此）。
冲突时以本文件为准。

---

## 一、五条硬约束（不可谈判）

违反任意一条，CI 会红；如果 CI 没红，说明断言不够，那是更严重的问题。

| # | 约束 | 为什么 | 怎么验证 |
|---|---|---|---|
| 1 | **零运行时依赖** `dependencies = []` | 这是产品决定，不是巧合。装不上 = 用不了 | `python -c "import importlib.metadata as m,sys; r=[x for x in (m.requires('agent-seed-brain') or []) if 'extra ==' not in x]; sys.exit(1 if r else 0)"` |
| 2 | **确定性**：禁 `random`、禁内置 `hash()` | 内置 hash 按进程加盐，同输入会给出不同排序 | `python -m unittest discover -s tests`（含两次排序一致性断言） |
| 3 | **Python 3.9 是地板** | 本地 3.13 通过 ≠ 3.9 通过 | 见下方「3.9 禁用清单」 |
| 4 | **每个新机制必须有一条能失败的断言** | 永远绿的测试比没测试更坏 | 在 `src/seedbrain/verify.py` 加检查，并确认它真的会 FAIL |
| 5 | **仓库只放规则，不放内容** | 许可边界：引擎与语料是两份独立版权客体 | CI `内容边界守卫`（license-guard job） |

### 3.9 禁用清单

- `Path.write_text(newline=...)`（3.10+）
- `str.removeprefix` / `str.removesuffix`（3.9 无）
- 结构化 `match`（3.10+）
- 运行时求值的 `X | Y` 类型联合（注解里可以，因为全模块有 `from __future__ import annotations`）
- 任何 3.10+ 的 `itertools` / `typing` 新名称

### 约束 4 的操作含义

新增行为时，问自己：**"如果实现写错，哪条断言会红？"**
答不出来就先补断言，再写实现。历史上三个真 bug 都是被断言抓出来的：

1. 配额只有上限没有下限 → 弱层有货却拿不到位
2. novelty 下限乘完次数惩罚掉到 0.11 → 复现能力失效
3. 旧货架样本引用了不存在的 id → 下游断言恒真（永远 PASS）

---

## 二、命令

```bash
# 测试（不需要安装任何东西）
PYTHONPATH=src python -m unittest discover -s tests        # 107 tests, 期望 OK

# 静态检查
ruff check src tests examples

# CI 的三项闸门（必须全过）
python -m seedbrain.cli build --profile profiles/example.json
git diff --exit-code -- tests/fixtures/mini-domain/        # 索引必须与源同步
python -m seedbrain.cli verify --profile profiles/example.json   # 期望 28/28

# 打包自检
python -m build && python -m twine check dist/*

# 开发期常用
seedbrain config --profile profiles/example.json --chain   # 看继承链
seedbrain stats  --profile profiles/example.json           # 覆盖率审计
```

`build` 是幂等的：连跑两次产出逐字节一致。所以 `git diff --exit-code` 是**真检查** ——
谁改了源文件忘了重建，它立刻失败。

---

## 三、代码地图

引擎与内容严格分离。本仓库只有引擎与解析规则，**一根种子都不打包**。

| 文件 | 职责 | 改动风险 |
|---|---|---|
| `src/seedbrain/__init__.py` | `SeedBrain` 门面（库 API 的稳定面） | 高 —— 公共 API |
| `src/seedbrain/profile.py` | Profile：领域差异的唯一入口；加载 / `extends` 合并 / `probes_ref` 展开 / 校验 / 路径解析 | 高 —— 所有配置语义在此 |
| `src/seedbrain/parse.py` | Markdown → `Seed`，完全由 profile 的正则驱动（`table` / `card`） | 中 —— 格式契约 |
| `src/seedbrain/tokenize.py` | n-gram 分词 + IDF 构建。刻意不引分词器 | 高 —— 匹配底座 |
| `src/seedbrain/score.py` | 评分与排序：IDF / 长度归一 / 配额 / 衰减，四机制叠加处 | 高 —— 「无偏」的实现位置 |
| `src/seedbrain/index.py` | 索引构建：等距平铺 + 写出 + 读入，守三条不变量 | 中 |
| `src/seedbrain/additions.py` | 增量池：会话中新增种子的**唯一写入路径**，不改源文件 | 中 |
| `src/seedbrain/state.py` | 使用状态快照 `{seed_id: {count, last_ts, scores[], ...}}` | 中 |
| `src/seedbrain/verify.py` | 28 项门槛断言 + 分组（schema / core / content） | 高 —— 门槛不可下调 |
| `src/seedbrain/models.py` | dataclass 模型，尽量不可变（`Seed` / `Match` / `BuildResult` / …） | 中 |
| `src/seedbrain/cli.py` | 命令行入口，退出码 0 / 1（断言失败）/ 2（用法或 IO 错） | 低 |
| `src/seedbrain/data/` | 包内公共配置：`base.json`、`probes/core.json`。`builtin:` 引用靠它解析 | 高 —— 漏进 package-data 会在 pip 安装后失效 |

数据流：`profile.json` → `parse` → `Seed[]` → `index.build` → `index.jsonl` → `score.rank` → `Match[]`

---

## 四、文档体系（双语治理）

文档是**双轨制**，两条轨道必须一一对应。

```
README.md            ← 英文，GitHub 与 PyPI 的默认门面
README.zh-CN.md      ← 简体中文

docs/en/             ↔  docs/zh-CN/
  getting-started.md       getting-started.md    安装、首次建索引、排障、卸载
  usage.md                 usage.md              CLI 与库 API 全量参考
  profiles.md              profiles.md           profile schema / extends / probes_ref / builtin
  methodology.md           methodology.md        算法原理、取舍、已知边界
  faq.md                   faq.md                常见问题与排障
```

### 必须遵守

1. **文件名严格同名**，只换目录。不要出现 `methods.md` vs `methodology.md` 这种漂移。
2. **改一侧必须同步另一侧**。单边修改等于制造两套真相。
3. 每篇 docs 顶部三件事：语言切换链接、返回**同语言** README 的链接。
   - `docs/en/x.md` → `[简体中文](../zh-CN/x.md)` + `[← README](../../README.md)`
   - `docs/zh-CN/x.md` → `[English](../en/x.md)` + `[← README](../../README.zh-CN.md)`
4. **完整示例只维护一份**。最小可跑示例（源文件 + profile 全文）只放 README，
   `getting-started` 引用它并保留验收输出，避免四份副本漂移。
5. 新增一篇文档 = 同时新增两篇 + 更新两个 README 的文档索引表。

### 不属于双轨的文件

`CHANGELOG.md`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、`NOTICE`、
`tasks/archive/` —— 单语（现状：CHANGELOG 中文，其余英文），不要求对齐。

### 归档语义（`tasks/archive/`）

`tasks/archive/` 是**历史存档**，不是当前规范：

1. 文件内的**许可声明、版本号、路径都是当时的状态**，不代表当前事实。
   例如存档里写「CC BY-NC-SA 4.0」是事实，因为那时确实是；当前许可以根目录
   [`LICENSE`](LICENSE) 为准（Apache-2.0）。
2. **不改写存档**。改写等于伪造决策记录 —— 这与「调低 verify 阈值」同类。
3. 新决策开 `tasks/CHG-YYYYMMDD-<slug>/`，完成后**移入** `archive/`，不要直接建在 archive 里。
4. 索引与「读之前必须知道什么」见 [`tasks/README.md`](tasks/README.md)。

### 术语

| 中文 | English |
|---|---|
| 种子 / 粒 | seed |
| 层（分层） | layer |
| 配额 | quota |
| 探针 | probe |
| 增量池 | increment pool / additions |
| 无偏（等距平铺） | unbiased (flat layout) |
| 门槛断言 | threshold assertion |

---

## 五、变更流程

### 提交

Conventional Commits，body 可用中文：

```
feat(score): 两阶段配额改为先保底后补满
fix(profile): root 推断不再硬假设 profiles/ 子目录
docs: 双语文档体系
ci(release): 发布流水线幂等化
```

破坏性变更用 `!` 并写 `BREAKING CHANGE:` footer。

### 每次变更必须同时更新

- [ ] `CHANGELOG.md` 的 `## [Unreleased]`（Added / Changed / Fixed）
- [ ] 若行为变了：对应的 `docs/en` **和** `docs/zh-CN`
- [ ] 若新增机制：`verify.py` 里一条能失败的断言
- [ ] 若改了公共 API：`docs/*/usage.md` 与 README 的示例

### CI 闸门（`.github/workflows/ci.yml`）

| Job | 内容 |
|---|---|
| `test` | 3.9–3.13 × ubuntu + windows + macOS；装包、零依赖断言、build 幂等、unittest、verify |
| `lint` | `ruff check src tests examples` |
| `license-guard` | 断言代码与数据文件里不含上游策展内容 |

三个 job 全绿才能合入。

---

## 六、发布

**推 tag 即发布全链路**（`.github/workflows/release.yml`）：

```
verify → build → PyPI(skip-existing) → GitHub Release(存在则同步)
```

### 版本号出现在 2 个代码位置 + 2 个文档位置

版本号不是「一个字段」，是**四处必须同时改**的契约：

| 位置 | 字段 | 谁读它 |
|---|---|---|
| `pyproject.toml` | `[project].version` | 打包元数据；`release.yml` 用它断言 tag 一致 |
| `src/seedbrain/__init__.py` | `__version__` | `seedbrain --version`、`verify` 生成的证据头、issue 里的版本回报 |
| `CHANGELOG.md` | `## [X.Y.Z] - YYYY-MM-DD` | `release.yml` 从这里提取 Release notes |
| `AGENTS.md` 本文 §六 + §九 | 发布状态表 / 当前状态表 | 人与 agent 读的现状 |

发版前自检（两条命令必须都报同一个号）：

```bash
python -m seedbrain.cli --version                    # 来自 __version__
grep -m1 '^version' pyproject.toml                   # 来自 [project].version
```

> **真实事故（v0.5.0）**：只改了 `pyproject.toml`，漏了 `__version__`。
> 结果 PyPI 上的包是 0.5.0，`seedbrain --version` 却报 0.3.0；因为 PyPI 不可覆盖，
> 只能补发 0.5.1。**只改一处就发版 = 发了个自称旧版本的包。**

### 发版步骤

1. 上表四处同步（`CHANGELOG.md` 把 `[Unreleased]` 落成 `## [X.Y.Z] - YYYY-MM-DD`）
2. 本地跑完 `unittest` / `verify` / `ruff` / `build` 幂等
3. `git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z`

流水线会断言 **tag ↔ 包版本一致**，不一致直接拒绝 —— 因为 PyPI 不允许覆盖同名文件，
发错了只能 yank + 升版本。

流水线会断言 **tag ↔ 包版本一致**，不一致直接拒绝 —— 因为 PyPI 不允许覆盖同名文件，
发错了只能 yank + 升版本。

### 补发历史版本

```bash
gh workflow run release.yml --ref main -f tag=v0.1.1 -f publish=true
```

幂等：PyPI 已存在的文件跳过，GitHub Release 已存在则同步说明与产物。
**不要**本地 `twine upload` —— 会绕过版本闸门并留下无法追溯的产物。

### 当前发布状态

PyPI 与 GitHub Release 各 6 个版本对齐：`0.1.0 / 0.1.1 / 0.2.0 / 0.3.0 / 0.5.0 / 0.5.1`，Latest = `0.5.1`。
（从未发布 `0.4.0`：再许可直接跳到 `0.5.0`。`0.5.1` 仅修 `__version__` 字符串并归档 `tasks/`，无 API 变更。）

---

## 七、禁区

| 禁止 | 理由 |
|---|---|
| 往下调 `verify` 阈值让构建变绿 | 门槛是防退化的唯一手段。先判断是实现错还是断言错 |
| 往 `[project] dependencies` 加包 | 破坏产品承诺；CI 会红 |
| 用 `random` 或内置 `hash()` | 破坏确定性与可复现 |
| 把上游语料 / 种子内容搬进本仓库 | 许可边界不可追溯，license-guard 会红 |
| 单边改双语中的一侧 | 制造两套真相 |
| 手改 `references/*.jsonl` / `SEED-INDEX.md` | 它们是生成产物；改源文件后 `build` |
| 跳过 CHANGELOG 直接提交功能 | 发布时无版本说明可提取 |
| 在运行时求值位置写类型联合语法（`X 竖线 Y`） | Python 3.9 会炸 |
| 手改 `LICENSE` 正文（必须整份取自 apache.org） | 许可正文错一个字都是法律风险；正文要能逐字节与官方源核对 |
| 改写 `tasks/archive/` 内的存档文件 | 那是带日期的决策记录，改写等于伪造历史 |

---

## 八、真实踩过的坑（省下重复排查）

| 现象 | 根因 | 处理 |
|---|---|---|
| `seedbrain --version` 报旧版本号 | 只改了 `pyproject.toml`，漏了 `src/seedbrain/__init__.py` 的 `__version__` | 两处同步（§六）；v0.5.0 因此补发了 0.5.1 |
| `源 '...' 解析出 0 条种子` | `entry_re` 里的破折号是**双**全角 `——`，源文件只写了单 `—` | 逐字符比对一行真实内容 |
| `profile 不是合法 JSON` | JSON 里的正则写了单反斜杠 | 每个反斜杠写成 `\\` |
| pip 安装后跑不了 `profiles/example.json` | wheel 只含引擎与 `data/`，示例 profile 属于仓库 | 用 `builtin:base` 自己写 profile，或从源码安装 |
| `verify --json` 不是纯 JSON | 进度行先打到 stdout | 用 sed 从第一个 `{` 截取后再 `jq`（见 docs/zh-CN/faq.md） |
| 小库上 `T5` 必失败 | 需要 6 次连选出 4 个不同 top1 | 扩语料，或 `--group schema`；**不要**降门槛 |
| `T9` 总被跳过 | 未配置 `verify.legacy_shelf` | 补旧首选表，或接受跳过（跳过是诚实的） |
| `--root` 推断不合预期 | 规则是：显式参数 → profile 的 `root` 字段 → 父目录名为 `profiles/` 取上一级 → 否则 profile 所在目录 | `seedbrain config` 看合并结果 |

---

## 九、当前状态

| 项 | 值 |
|---|---|
| 版本 | `0.5.1`（PyPI 已发布） |
| 测试 | 107 个 unittest |
| 断言 | `verify` 28 项（示例域） |
| Python | 3.9 – 3.13 |
| 运行时依赖 | **0** |
| 许可 | Apache-2.0（OSI 认可的开源许可） |

贡献按 Apache-2.0 提供（inbound = outbound，无 CLA，见 `CONTRIBUTING.md`）。
v0.3.x 及更早版本曾以 CC BY-NC-SA 4.0 发布，旧版本继续按其原始许可。
