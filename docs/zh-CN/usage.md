<p align="right">
  <a href="../en/usage.md">English</a> · <b>简体中文</b> ·
  <a href="../../README.zh-CN.md">← README</a>
</p>

# 使用参考

CLI 与库的全部接口。本页每个签名都从已发布的包里读出来，不是设计稿。

---

## 1. 命令总览

```
seedbrain [-h] [--version] {build,match,pick,add,verify,stats,config} ...
```

| 命令 | 作用 | 读 | 写 |
|---|---|---|---|
| `build` | 解析全部源 → 等距平铺索引 | 源文件 | `index_jsonl`、`index_md` |
| `match` | 任务描述 → top-K 候选 | 索引、状态 | — |
| `pick` | 记录一次使用（驱动衰减） | 索引 | `state` |
| `add` | 往增量池追加一粒种子 | 源文件 | `additions`，随后重建 |
| `verify` | 跑门槛断言套件 | 索引 | 可选 `--evidence` |
| `stats` | 覆盖率审计 | 索引、状态 | — |
| `config` | 打印合并后的 profile | 继承链 | — |

### 全局参数

每个子命令都接受这两个：

| 参数 | 含义 |
|---|---|
| `--profile PATH` | profile JSON。默认 `./seedbrain.json`。 |
| `--root PATH` | 知识库根目录。默认规则见下。 |

**`--root` 的真实推断顺序**（`--help` 里那句话是简化版）：

1. 显式 `--root` 参数；
2. profile 内的 `"root"` 字段（相对 profile 所在位置）；
3. profile 的父目录名恰好是 `profiles` → 取它的上一级（「单仓库多 profile」的常见布局）；
4. 否则取 profile 所在目录。

profile 里声明的路径都相对这个 root 解析。不确定时直接问工具：

```bash
seedbrain config --profile profiles/example.json
```

---

## 2. `build`

```
seedbrain build [-h] [--profile PROFILE] [--root ROOT] [--quiet]
```

解析每个 `sources` 条目、分配 ID、应用跨层配额、写出索引。
**幂等**：跑两次产出逐字节一致，CI 就是靠这一点做断言的。

```bash
seedbrain build --profile seedbrain.json
seedbrain build --profile seedbrain.json --quiet   # 脚本里用，不输出
```

成功输出：

```
✓ 12 粒种子
  分层：method 12
  → references/seed-index.jsonl
  → references/SEED-INDEX.md
```

某个源解析出 0 条是**硬错误**，不是警告 —— 静默正是索引腐烂的方式：

```
seedbrain.parse.ParseError: 源 'notes/methods.md' 解析出 0 条种子
  —— 请检查 profile 里的 entry_re 是否匹配实际格式
```

---

## 3. `match`

```
seedbrain match [-h] [--profile PROFILE] [--root ROOT] [--k K] [--json] task
```

`task` 是任意语言的自然语言。输出列：

| 列 | 含义 |
|---|---|
| 得分（`total`） | IDF + 长度归一 + 新颖度之后的最终分 |
| 新颖（`novelty`） | `[0.15, 1.0]` 的衰减因子；越低表示刚用过 |
| 命中信号（`hits`） | 产生这个分数的 `(信号, 权重)` 对 |

```bash
seedbrain match "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5
seedbrain match "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5 --json
```

`--json` 输出纯 JSON 数组：

```json
[
  { "id": "m-qr-iteration", "name": "QR iteration", "layer": "method", "score": 1.03 }
]
```

`--k` 用来放宽候选面。刻意**没有** `--no-decay`：关掉新颖度等于在测另一个工具。

---

## 4. `pick`

```
seedbrain pick [-h] [--profile PROFILE] [--root ROOT]
               [--score {0,1,2,3,4,5}] [--note NOTE] id
```

记录「这粒被用过了」。这是让**下一次** `match` 优先给出「同等合适但不同」候选的
唯一机制。不 `pick`，每次都会返回同一个 top1。

```bash
seedbrain pick m-matrix-decomposition --profile seedbrain.json \
  --score 5 --note "一次过，无需回退"
```

`--score` 是你自己的质量判断，存下来备审计用，**不回流到排序**；只有使用时间和
次数参与衰减。

---

## 5. `add`

```
seedbrain add [-h] [--profile PROFILE] [--root ROOT] --name NAME --layer LAYER
              [--signals SIGNALS] [--one-liner ONE_LINER] [--ref REF]
              [--id ID] [--force] [--dry-run]
```

写入增量池（`additions`），随后自动重建。源文件永远不被修改 —— 这个隔离是刻意的，
否则脚本会静默破坏人工策展的语料。

```bash
seedbrain add \
  --name "共形 PID 控制" \
  --layer method \
  --signals "在线控制,分布漂移,覆盖率保证" \
  --one-liner "用覆盖率保证替代固定增益" \
  --ref notes/methods.md \
  --profile seedbrain.json
```

写入前有三道护栏：

| 护栏 | 行为 |
|---|---|
| `ref` 必须可解析 | 路径不存在 → `InvalidInputError`，防静默断链 |
| 同层查重 | 包含度 ≥ `dup_threshold`（0.75）→ `DuplicateError` |
| ID 撞车 | 只加后缀（`-2`、`-3`），已有 ID **绝不改写** |

`--dry-run` 只打印将要发生什么，不落盘。`--force` 绕过查重（评审时会被问到
为什么）。`--id` 指定显式 ID。

---

## 6. `verify`

```
seedbrain verify [-h] [--profile PROFILE] [--root ROOT] [--evidence EVIDENCE]
                 [--json] [--group {schema,core,content}]
```

跑断言套件。**任何一项失败时退出码为 1**，可以直接当 CI 闸门用。

```bash
seedbrain verify --profile seedbrain.json
seedbrain verify --profile seedbrain.json --json
seedbrain verify --profile seedbrain.json --evidence reports/verify.md
seedbrain verify --profile seedbrain.json --group schema   # 只跑结构性检查
```

| 组 | 包含 |
|---|---|
| `schema` | profile 合法性、层前缀齐备 |
| `core` | ID 唯一、字段非空、`ref` 可解析、召回、IDF 单调性、配额、轮转、等价性、增量 |
| `content` | 需要 `verify.legacy_shelf` / 探针的检查，如去中心化 |

> **`--json` 不是纯 JSON。** 进度行先打印，JSON 对象在后。从第一个 `{` 解析：
>
> ```bash
> seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq .
> ```
>
> `match --json` 没有这个问题，它输出纯 JSON。

### 关于小语料

`T5`（轮转多样性）要求**6 次连选中出现 4 个不同的 top1**。少于约 10 粒互相关联的
种子时，这在算术上无法通过，门槛也**不会**为了让玩具数据变绿而下调。可选：

- 扩充语料（推荐）；
- 早期搭建期用 `--group schema` 只做结构闸门。

`T9`（去中心化）在缺少 `verify.legacy_shelf` 时是**跳过**而非通过。跳过的检查是
诚实的；永远不会失败的检查不是。

---

## 7. `stats`

```
seedbrain stats [-h] [--profile PROFILE] [--root ROOT]
```

覆盖率审计 —— 回答「哪些货架从来没被够到」。

```
全库 22 粒 ｜ 曾使用 1 粒 ｜ 覆盖率 4.5%
  card           0/6      0.0%
  tool           1/16     6.2%

零使用分组：4
  · cards
  · 三、统计
```

`Stats` 字段：`total`、`used`、`by_layer`、`blind_groups`、`top_reused`。
`top_reused` 是正反馈收敛的早期预警。

---

## 8. `config`

```
seedbrain config [-h] [--profile PROFILE] [--root ROOT] [--chain]
```

打印 **`extends` 合并、`probes_ref` 展开之后**的 profile —— 当某个阈值「不知道
从哪冒出来」时，这是最有用的调试命令。

```bash
seedbrain config --profile seedbrain.json --chain   # 只打印继承链
seedbrain config --profile seedbrain.json           # 合并后的最终配置
```

---

## 9. 退出码

| 码 | 含义 |
|---|---|
| `0` | 成功（含 `verify` 全通过） |
| `1` | `verify` 有断言失败 |
| `2` | 用法 / IO 错误 —— profile 缺失、索引缺失、JSON 不可解析 |

---

## 10. 库 API

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("seedbrain.json")          # 或 SeedBrain.load(path, root=...)
```

### `SeedBrain.load(profile, root=None) → SeedBrain`

加载并校验 profile（含 `extends` 与 `probes_ref`）。

### `brain.build() → BuildResult`

```python
r = brain.build()
print(r.total, r.added, r.collided, r.dropped, r.layers, r.groups)
```

| 字段 | 含义 |
|---|---|
| `total` | 索引里的种子数 |
| `added` | 来自增量池的条数 |
| `collided` | 增量 ID 撞车、已加后缀的条数 |
| `dropped` | 源库内部重名被合并掉的条数 |

### `brain.match(task, k=8, *, debug=False) → list[Match]`

```python
for m in brain.match("降维压缩，矩阵分解选型", k=5):
    print(f"{m.total:6.1f}  {m.seed.id:<28} {m.hits[:2]}")
```

`Match` 字段：`seed`、`total`、`base`、`novelty`、`hits`。
`seed` 是不可变 `Seed`，含 `id`、`name`、`layer`、`group`、`one_liner`、`text`、
`grams`、`ref`、`origin`。

`debug=True` 会额外把打分过程打到 stderr。

### `brain.pick(seed_id, score=0, note="") → dict`

记录一次使用，返回该种子更新后的状态条目。

### `brain.add(*, name, layer, signals=(), one_liner="", ref="", seed_id="", force=False, dry_run=False) → Seed`

护栏与 CLI 相同。`dry_run=True` 返回「将要写入的」`Seed`，不碰增量池。

### `brain.verify(groups=("schema", "core", "content")) → VerifyReport`

```python
report = brain.verify()
print(report.passed, report.failed, report.ok)
for c in report.checks:
    print(c.id, c.name, c.metric, c.target, c.ok)
```

`VerifyReport` 暴露 `checks`，以及派生属性 `passed` / `failed` / `ok`。

### `brain.stats() → Stats`

字段：`total`、`used`、`by_layer`、`blind_groups`、`top_reused`。

### 属性

| 属性 | 类型 | 说明 |
|---|---|---|
| `brain.seeds` | `list[Seed]` | 从索引载入；`build()` 之前为空 |
| `brain.state` | `dict` | 使用状态，惰性载入 |
| `brain.profile` | `Profile` | 合并后的配置，`profile.raw` 是 dict |

### 异常

| 异常 | 触发条件 |
|---|---|
| `SeedBrainError` | 基类 |
| `ProfileError` | profile 缺失 / JSON 非法 / schema 错 / `extends` 成环 |
| `ParseError` | 某个源解析出 0 条，或正则非法 |
| `DuplicateError` | `add` 撞上超过 `dup_threshold` 的已有种子 |
| `InvalidInputError` | `add` 的 `ref` 不存在，或输入非法 |

---

## 11. 配方

### CI 闸门

```yaml
- name: index is in sync
  run: |
    seedbrain build --profile seedbrain.json
    git diff --exit-code -- references/

- name: assertions
  run: seedbrain verify --profile seedbrain.json
```

因为 `build` 是确定性的，后面的 `git diff --exit-code` 是真检查：谁改了源文件忘了
重建，它立刻失败。

### agent 规则片段

写进 harness 的规则文件：

```
选方案前先跑：
  seedbrain match "<一句话任务描述>" --profile <路径> --k 8
读候选与命中信号。交付后跑：
  seedbrain pick <id> --score <0-5>
```

### 批量查询

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("seedbrain.json")
if not brain.seeds:
    brain.build()

for task in tasks:
    ids = [m.seed.id for m in brain.match(task, k=3)]
    print(task, "→", ids)
```

### 安全地读 JSON

```bash
seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq '.passed'
```
