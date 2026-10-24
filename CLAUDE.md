# CLAUDE.md

@AGENTS.md

本文件是 Claude Code 的入口。**规则以 [AGENTS.md](AGENTS.md) 为唯一权威**，
本文件只补充 Claude 侧的工作流约定，不另立一套。

---

## 一句话

`seedbrain`：零依赖的领域知识编译器。引擎在本仓库，语料在各自的内容仓库。
任何改动都要能通过 `verify` 的 28 项断言。

---

## 五条硬约束（速查，全文见 AGENTS.md §一）

| # | 约束 | 违反后果 |
|---|---|---|
| 1 | 运行时依赖必须为空 | CI 红 + 破坏产品承诺 |
| 2 | 禁 `random` / 内置 `hash()` | 确定性丢失，测试不稳定 |
| 3 | Python 3.9 是地板 | CI 的 3.9 job 红 |
| 4 | 新机制必须配一条**能失败**的断言 | 退化无法被发现 |
| 5 | 仓库只放规则，不放语料 | 许可边界崩溃 |

---

## Claude 工作流

### 探索代码

本项目已在知识图谱中索引（项目名 `E-Development-agent-seed-brain`）。
**先查图谱再读文件**：

- `search_graph` —— 找函数 / 类 / 路由
- `trace_path` —— 谁调用谁、影响面
- `get_code_snippet` —— 拿到精确源码与签名
- `query_graph` —— 复杂聚合（如所有 Method 签名）

图谱给出的文件路径可直接作为读取许可。若图谱无结果，先 `detect_changes` 判断索引是否过期，
而不是立刻跳到 grep。

### 改动循环

```bash
# 0. 建立基线（重要：先知道当前是不是绿的）
PYTHONPATH=src python -m unittest discover -s tests
python -m seedbrain.cli verify --profile profiles/example.json

# 1. 改代码

# 2. 三项闸门
python -m seedbrain.cli build --profile profiles/example.json
git diff --exit-code -- tests/fixtures/mini-domain/
PYTHONPATH=src python -m unittest discover -s tests
python -m seedbrain.cli verify --profile profiles/example.json
ruff check src tests examples
```

`build` 是确定性的，所以第二步的 `git diff` 是**真检查**：
改了源文件或解析逻辑却没重建索引，它会立刻失败。不要用 `git checkout` 抹掉这个 diff ——
那是掩盖问题。

### 文档同步

改行为 → 同时改四处，缺一不可：

```
README.md           README.zh-CN.md
docs/en/*.md        docs/zh-CN/*.md
```

文件名必须同名（`getting-started` / `usage` / `profiles` / `methodology` / `faq`）。
单边修改会被视为缺陷。

改完跑一遍相对链接检查（历史上这里出过错：`docs/zh-CN/` 到根目录要 `../../`，不是 `../`）。

### 发布

版本号有**两处代码位置**，必须同时改 —— v0.5.0 就是漏了第二处，被迫补发 0.5.1：

```
pyproject.toml             [project].version    打包元数据 + release.yml 的 tag 断言
src/seedbrain/__init__.py  __version__          seedbrain --version / verify 证据头
```

发版前两条命令必须报同一个号：

```bash
python -m seedbrain.cli --version
grep -m1 '^version' pyproject.toml
```

推 tag 即全自动（verify → build → PyPI → GitHub Release）。补发历史版本：

```bash
gh workflow run release.yml --ref main -f tag=vX.Y.Z -f publish=true
```

幂等，不会因 PyPI 已存在而报错。**不要**本地 `twine upload`。

---

## 判断边界

| 情况 | 做法 |
|---|---|
| `verify` 变了红 | 先判断是**实现**错还是**断言**错。两者都真实发生过 |
| 想让构建变绿 | 绝不通过下调阈值实现。可以扩语料，或 `--group schema` |
| 文档与代码不一致 | 以**可执行的事实**为准（跑一遍命令），然后修文档 |
| 小语料上 `T5` 失败 | 这是设计如此（6 次连选需 4 个不同 top1）。扩语料，不改门槛 |
| 拿不准某条约束的边界 | 读 `CONTRIBUTING.md` 与 `docs/*/methodology.md`，不要猜 |

---

## 别做

- 别在没有基线的情况下声称"修好了"——先跑测试和 verify
- 别把 `tests/fixtures/` 的 diff 当作噪声清掉
- 别引入任何第三方包，包括"只是开发期用"的断言类库（`dev` extras 除外）
- 别把上游美学大脑的种子文本复制进来
- 别只改 `pyproject.toml` 就发版（还有 `__version__`，见「发布」）
- 别手改 `LICENSE` 正文或 `tasks/archive/` 里的存档
- 别在 `docs/` 里新建单语文件
