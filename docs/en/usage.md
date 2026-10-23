<p align="right">
  <b>English</b> · <a href="../zh-CN/usage.md">简体中文</a> ·
  <a href="../../README.md">← README</a>
</p>

# Usage reference

Complete surface of the CLI and the library. Every signature on this page was
read from the released package, not from a design document.

---

## 1. Command overview

```
seedbrain [-h] [--version] {build,match,pick,add,verify,stats,config} ...
```

| Command | Purpose | Reads | Writes |
|---|---|---|---|
| `build` | Parse all sources → flat index | source files | `index_jsonl`, `index_md` |
| `match` | Task description → top-K candidates | index, state | — |
| `pick` | Record one use (drives decay) | index | `state` |
| `add` | Append a seed to the increment pool | sources | `additions`, then rebuild |
| `verify` | Run the assertion suite | index | optionally `--evidence` |
| `stats` | Coverage audit | index, state | — |
| `config` | Print the merged profile | profile chain | — |

### Global options

Every subcommand accepts these two:

| Option | Meaning |
|---|---|
| `--profile PATH` | Profile JSON. Default `./seedbrain.json`. |
| `--root PATH` | Knowledge-base root. Default resolution below. |

**`--root` resolution order** (this is the real rule; the `--help` string is a
simplification):

1. the explicit `--root` argument;
2. the `"root"` field inside the profile, relative to the profile's location;
3. if the profile's parent directory is named `profiles`, use its parent —
   the usual "one repo, several profiles" layout;
4. otherwise, the directory containing the profile.

Paths declared in the profile are resolved against this root. When in doubt,
ask the tool:

```bash
seedbrain config --profile profiles/example.json
```

---

## 2. `build`

```
seedbrain build [-h] [--profile PROFILE] [--root ROOT] [--quiet]
```

Parses every `sources` entry, assigns IDs, applies cross-layer quotas, and
writes the index. Idempotent: **running it twice yields byte-identical files**,
which is what CI asserts.

```bash
seedbrain build --profile seedbrain.json
seedbrain build --profile seedbrain.json --quiet   # no output, for scripts
```

Output on success:

```
✓ 12 粒种子
  分层：method 12
  → references/seed-index.jsonl
  → references/SEED-INDEX.md
```

A source that yields zero seeds is a hard error, not a warning — silence is how
indexes rot:

```
seedbrain.parse.ParseError: 源 'notes/methods.md' 解析出 0 条种子
  —— 请检查 profile 里的 entry_re 是否匹配实际格式
```

---

## 3. `match`

```
seedbrain match [-h] [--profile PROFILE] [--root ROOT] [--k K] [--json] task
```

`task` is free text in any language. Output columns:

| Column | Meaning |
|---|---|
| 得分 (`total`) | final score after IDF, length normalisation, and novelty |
| 新颖 (`novelty`) | decay factor in `[0.15, 1.0]`; lower means recently used |
| 命中信号 (`hits`) | `(signal, weight)` pairs that produced the score |

```bash
seedbrain match "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5
seedbrain match "降维压缩，矩阵分解选型" --profile seedbrain.json --k 5 --json
```

`--json` emits a pure JSON array:

```json
[
  { "id": "m-qr-iteration", "name": "QR iteration", "layer": "method", "score": 1.03 }
]
```

Use `--k` to widen the net. There is no `--no-decay` flag on purpose: if you
disable novelty you are testing a different tool.

---

## 4. `pick`

```
seedbrain pick [-h] [--profile PROFILE] [--root ROOT]
               [--score {0,1,2,3,4,5}] [--note NOTE] id
```

Records that a seed was used. This is what makes the *next* `match` prefer a
different-but-equally-fitted candidate. Without `pick`, every run returns the
same top-1 forever.

```bash
seedbrain pick m-matrix-decomposition --profile seedbrain.json \
  --score 5 --note "一次过，无需回退"
```

`--score` is your own quality judgement, stored for later audit. It does not
feed back into ranking; only the usage timestamp and count do.

---

## 5. `add`

```
seedbrain add [-h] [--profile PROFILE] [--root ROOT] --name NAME --layer LAYER
              [--signals SIGNALS] [--one-liner ONE_LINER] [--ref REF]
              [--id ID] [--force] [--dry-run]
```

Appends to the increment pool (`additions`), then rebuilds. Source files are
never modified — that separation is deliberate, so a curated corpus cannot be
silently corrupted by a script.

```bash
seedbrain add \
  --name "Conformal PID" \
  --layer method \
  --signals "在线控制,分布漂移,覆盖率保证" \
  --one-liner "用覆盖率保证替代固定增益" \
  --ref notes/methods.md \
  --profile seedbrain.json
```

Three guards fire before anything is written:

| Guard | Behaviour |
|---|---|
| `ref` must resolve | unknown path → `InvalidInputError`; prevents silent dead links |
| same-layer duplicate | containment ≥ `dup_threshold` (0.75) → `DuplicateError` |
| ID collision | suffix appended (`-2`, `-3`); existing IDs are **never** rewritten |

`--dry-run` prints what would happen and writes nothing. `--force` bypasses the
duplicate check (you will be asked why in review). `--id` pins an explicit ID.

---

## 6. `verify`

```
seedbrain verify [-h] [--profile PROFILE] [--root ROOT] [--evidence EVIDENCE]
                 [--json] [--group {schema,core,content}]
```

Runs the assertion suite. Exit code is **1 when any check fails** — this is
safe to use directly as a CI gate.

```bash
seedbrain verify --profile seedbrain.json
seedbrain verify --profile seedbrain.json --json
seedbrain verify --profile seedbrain.json --evidence reports/verify.md
seedbrain verify --profile seedbrain.json --group schema   # structural only
```

| Group | Contains |
|---|---|
| `schema` | profile validity, layer prefixes |
| `core` | ID uniqueness, fields, `ref` resolution, recall, IDF monotonicity, quotas, rotation, equivalence, increments |
| `content` | checks that need `verify.legacy_shelf` / probes, e.g. decentralisation |

> **`--json` is not pure JSON.** Progress lines are printed first; the JSON
> object follows. Parse from the first `{`:
>
> ```bash
> seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq .
> ```
>
> `match --json` does **not** have this caveat — it emits pure JSON.

### On small corpora

`T5` (rotation diversity) requires **four distinct top-1 picks across six
consecutive runs**. With fewer than ~10 well-connected seeds this cannot pass,
and the threshold will not be lowered to make toy data green. Options:

- grow the corpus (recommended);
- `--group schema` for a structural-only gate during early setup.

`T9` (decentralisation) is skipped, not passed, when `verify.legacy_shelf` is
absent. A skipped check is honest; a check that can never fail is not.

---

## 7. `stats`

```
seedbrain stats [-h] [--profile PROFILE] [--root ROOT]
```

Coverage audit — answers "which shelves have never been reached?".

```
全库 22 粒 ｜ 曾使用 1 粒 ｜ 覆盖率 4.5%
  card           0/6      0.0%
  tool           1/16     6.2%

零使用分组：4
  · cards
  · 三、统计
```

`Stats` fields: `total`, `used`, `by_layer`, `blind_groups`, `top_reused`.
`top_reused` is the early-warning signal for positive-feedback collapse.

---

## 8. `config`

```
seedbrain config [-h] [--profile PROFILE] [--root ROOT] [--chain]
```

Prints the profile **after** `extends` merging and `probes_ref` expansion — the
single most useful debugging command when a threshold "came from nowhere".

```bash
seedbrain config --profile seedbrain.json --chain   # inheritance chain only
seedbrain config --profile seedbrain.json           # final merged config
```

---

## 9. Exit codes

| Code | Meaning |
|---|---|
| `0` | success (including `verify` all-pass) |
| `1` | `verify` found failing assertions |
| `2` | usage / IO error — missing profile, missing index, unparsable JSON |

---

## 10. Library API

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("seedbrain.json")          # or SeedBrain.load(path, root=...)
```

### `SeedBrain.load(profile, root=None) → SeedBrain`

Loads and validates the profile (including `extends` and `probes_ref`).

### `brain.build() → BuildResult`

```python
r = brain.build()
print(r.total, r.added, r.collided, r.dropped, r.layers, r.groups)
```

| Field | Meaning |
|---|---|
| `total` | seeds in the index |
| `added` | seeds that came from the increment pool |
| `collided` | increment IDs that collided and got a suffix |
| `dropped` | duplicate names merged **within** the sources |

### `brain.match(task, k=8, *, debug=False) → list[Match]`

```python
for m in brain.match("降维压缩，矩阵分解选型", k=5):
    print(f"{m.total:6.1f}  {m.seed.id:<28} {m.hits[:2]}")
```

`Match` fields: `seed`, `total`, `base`, `novelty`, `hits`.
`seed` is a frozen `Seed` with `id`, `name`, `layer`, `group`, `one_liner`,
`text`, `grams`, `ref`, `origin`.

`debug=True` additionally prints the scoring breakdown to stderr.

### `brain.pick(seed_id, score=0, note="") → dict`

Records a use. Returns the updated state entry for that seed.

### `brain.add(*, name, layer, signals=(), one_liner="", ref="", seed_id="", force=False, dry_run=False) → Seed`

Same guards as the CLI. `dry_run=True` returns the would-be `Seed` without
touching the pool.

### `brain.verify(groups=("schema", "core", "content")) → VerifyReport`

```python
report = brain.verify()
print(report.passed, report.failed, report.ok)
for c in report.checks:
    print(c.id, c.name, c.metric, c.target, c.ok)
```

`VerifyReport` exposes `checks` plus the derived `passed` / `failed` / `ok`.

### `brain.stats() → Stats`

Fields: `total`, `used`, `by_layer`, `blind_groups`, `top_reused`.

### Attributes

| Attribute | Type | Notes |
|---|---|---|
| `brain.seeds` | `list[Seed]` | loaded from the index; empty before `build()` |
| `brain.state` | `dict` | usage state, loaded lazily |
| `brain.profile` | `Profile` | merged config, `profile.raw` is the dict |

### Exceptions

| Exception | Raised when |
|---|---|
| `SeedBrainError` | base class |
| `ProfileError` | profile missing / invalid JSON / bad schema / `extends` cycle |
| `ParseError` | a source parses to zero seeds, or a regex is invalid |
| `DuplicateError` | `add` finds an existing seed above `dup_threshold` |
| `InvalidInputError` | `add` references a non-existent `ref`, or bad input |

---

## 11. Recipes

### CI gate

```yaml
- name: index is in sync
  run: |
    seedbrain build --profile seedbrain.json
    git diff --exit-code -- references/

- name: assertions
  run: seedbrain verify --profile seedbrain.json
```

Because `build` is deterministic, `git diff --exit-code` after it is a real
check: it fails the moment someone edits a source and forgets to rebuild.

### Agent rule snippet

Add to the harness's rule file:

```
Before choosing an approach, run:
  seedbrain match "<one-line task description>" --profile <path> --k 8
Read the candidates and their hit signals. After delivering, run:
  seedbrain pick <id> --score <0-5>
```

### Batch query

```python
from seedbrain import SeedBrain

brain = SeedBrain.load("seedbrain.json")
if not brain.seeds:
    brain.build()

for task in tasks:
    ids = [m.seed.id for m in brain.match(task, k=3)]
    print(task, "→", ids)
```

### Reading JSON safely

```bash
seedbrain verify --profile seedbrain.json --json | sed -n '/^{/,$p' | jq '.passed'
```
