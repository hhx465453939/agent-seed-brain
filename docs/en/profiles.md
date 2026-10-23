<p align="right">
  <b>English</b> · <a href="../zh-CN/profiles.md">简体中文</a> ·
  <a href="../../README.md">← README</a>
</p>

# Profile reference

A profile is a single JSON file. It declares **where your knowledge lives, how
to parse it, and what "good" means**. Adding a domain requires no Python.

```bash
seedbrain config --profile your.json     # always inspect the merged result
```

---

## 1. Minimal profile

```json
{
  "schema_version": 1,
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
  }
}
```

That is enough to `build` and `match`. `verify` additionally wants probes and
thresholds — inherit them (§9) or write them explicitly.

---

## 2. Top-level fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `schema_version` | int | ✅ | — | must be `1` |
| `name` | str | — | profile filename stem | used in reports |
| `label` | str | — | `name` | human-facing title |
| `root` | str | — | see `--root` rules | knowledge-base root, relative to the profile |
| `extends` | str | — | — | inherit another profile (§8) |
| `sources` | list | ✅ | — | at least one |
| `layers` | dict | ✅ | — | at least one |
| `paths` | dict | — | `references/…` | output locations (§5) |
| `norms` | dict | — | sensible defaults | scoring constants (§6) |
| `verify` | dict | — | `{}` | probes and thresholds (§7) |
| `_comment` | any | — | — | ignored; use it to explain the file |

Unknown top-level keys are ignored, which keeps forward compatibility painless.

---

## 3. `sources[]`

Two kinds. Each source belongs to exactly one layer.

### 3.1 `kind: "table"` — many entries in one file

| Field | Required | Purpose |
|---|---|---|
| `kind` | ✅ | `"table"` |
| `path` | ✅ | file, relative to root |
| `layer` | ✅ | must exist in `layers` |
| `group_re` | — | captures `group` (section heading) |
| `entry_re` | ✅ | captures `name`, `tag`, `desc` |
| `aux_re` | — | captures `kw`; attaches a keyword to the **previous** entry |

The captured group names are a contract: `group`, `name`, `tag`, `desc`, `kw`.
Use them exactly, or the parse yields zero seeds and `build` fails loudly.

Example source line and the regex that matches it:

```
- **Matrix decomposition** · svd —— 奇异值分解，降维与压缩的通用手段
  ^-\\s*\\*\\*(?P<name>[^*]+?)\\*\\*\\s*·\\s*(?P<tag>[^—]+?)\\s*——\\s*(?P<desc>.+)$
     └ name: "Matrix decomposition"  └ tag: "svd"        └ desc: "奇异值分解…"
```

> **The dash is two characters.** `entry_re` expects a full-width double em
> dash `——` (U+2014 twice). A single `—` will silently match nothing. This is
> the single most common cause of "0 seeds parsed".

### 3.2 `kind: "card"` — one file per entry

| Field | Required | Purpose |
|---|---|---|
| `kind` | ✅ | `"card"` |
| `dir` | ✅ | directory of card files, relative to root |
| `layer` | ✅ | must exist in `layers` |
| `title_re` | — | captures `title` (usually the H1) |
| `field_re` | — | captures `key` / `val` from metadata lines |
| `list_re` | — | captures `item` from bullet lines |
| `template_parts` | — | substrings that mark a **template** file; those are skipped |

Cards are how the aesthetic brain stores 352 chapter entries: one file per
artist or style, with a metadata block at the top.

```json
{
  "kind": "card",
  "dir": "chapters",
  "layer": "chapter",
  "title_re": "^#\\s+(?P<title>.+)$",
  "field_re": "^>\\s*\\*\\*(?P<key>[^*]+?)\\*\\*\\s*[：:]\\s*(?P<val>.*)$",
  "list_re": "^>\\s*(?:[-*]|\\d+\\.)\\s+(?P<item>.+)$",
  "template_parts": ["template", "card"]
}
```

`template_parts` exists because a directory of cards almost always contains an
example file that is not real content. Without it, the template's name gets
indexed and starts competing with real entries.

---

## 4. `layers{}`

```json
"layers": {
  "method": { "prefix": "m",  "quota": 0.6, "label": "Methods" },
  "card":   { "prefix": "cd", "quota": 0.4, "label": "Deep dives" }
}
```

| Field | Required | Meaning |
|---|---|---|
| `prefix` | ✅ | ID prefix; `m-matrix-decomposition` |
| `quota` | — | share of `top-K`, `0..1`; should sum to ≤ 1.0 |
| `label` | — | display name in reports |

**Quotas are enforced in two phases:** every layer first gets
`min(floor(k×quota), available)`, then the remainder is filled by global score.
A layer with no candidates yields its slots to layers that have some — so a
small layer is never starved by a large one.

Prefixes must be unique. IDs are `prefix + "-" + slug(name)`.

---

## 5. `paths{}`

```json
"paths": {
  "index_jsonl": "references/seed-index.jsonl",
  "index_md":    "references/SEED-INDEX.md",
  "additions":   "references/seed-additions.jsonl",
  "state":       "references/.seed-usage.json"
}
```

All relative to `root`. The two index files are **generated artifacts** — commit
them if you want `git diff --exit-code` as an idempotency gate in CI (the repo
itself does exactly that). `additions` and `state` are append-only working
state; typically gitignored in consumer repos.

---

## 6. `norms{}`

| Field | Default | Meaning |
|---|---|---|
| `decay_tau_days` | `14.0` | time constant of novelty recovery |
| `count_penalty` | `0.5` | how hard repeated use is penalised |
| `max_hits` | `5` | max hit signals kept per match (display + score) |
| `gram_w2` | `1.0` | weight of 2-grams |
| `gram_w3` | `0.35` | weight of 3-grams |
| `dup_threshold` | `0.75` | containment above which `add` rejects as duplicate |

```python
recovery  = 1 - exp(-Δt / decay_tau_days)
count_pen = 1 / (1 + count_penalty * ln(1 + count))
novelty   = max(0.15, recovery * count_pen)
```

The `0.15` floor is not configurable on purpose: it preserves "I want the same
result as last time" as a legitimate request.

---

## 7. `verify{}`

```json
"verify": {
  "probes_ref": "builtin:probes/core",
  "probes": ["降维压缩，矩阵分解选型"],
  "generic_fill": ["方法", "计算", "结果", "分析"],
  "legacy_shelf": ["tl-矩阵分解", "tl-图遍历"],
  "thresholds": { "recall_name": 0.9 },
  "content": {}
}
```

| Field | Purpose |
|---|---|
| `probes` | representative task descriptions; drive recall/rotation checks |
| `probes_ref` | reference to a shared probe pool (§10) |
| `generic_fill` | words treated as generic when checking feature recall |
| `legacy_shelf` | the "old curated shortlist"; powers the decentralisation check `T9` |
| `thresholds` | overrides for any default threshold |
| `content` | optional content-integrity spec (directory counts, required fields) |

### Threshold defaults

| Key | Default | Check |
|---|---|---|
| `recall_name` | `0.98` | T2a name self-recall@8 |
| `recall_feature` | `0.60` | T2b feature recall |
| `gini_max` | `0.80` | T3a hit-distribution Gini |
| `idf_top1_gain` | `0.15` | T4b end-to-end IDF comparison |
| `layer_dominance_max` | `0.70` | T6 layer dominance |
| `rotation_min` | `4` | T5 distinct top-1 across rounds |
| `rotation_rounds` | `6` | T5 number of consecutive rounds |
| `decenter_min` | `0.50` | T9 share of top-1 outside `legacy_shelf` |

**Do not lower a threshold to make a build pass.** The project's own history
contains two real bugs that were only found because the threshold was *not*
lowered (see `methodology.md` §8).

---

## 8. `extends` — inherit, do not copy

```json
{
  "extends": "builtin:base",
  "name": "my-domain",
  "sources": [ /* only domain-specific */ ],
  "layers":  { /* only domain-specific */ }
}
```

**Merge rules — exactly two:**

1. dictionaries merge recursively;
2. lists and scalars are replaced wholesale.

Lists are not merged because "clear the inherited probes" must be expressible.
That consequence is why probes have a separate mechanism (§10).

Cycles are detected: `A → B → A` raises `ProfileError` with the full chain
instead of recursing until the stack dies.

Inspect the result:

```bash
seedbrain config --profile my.json --chain   # A → builtin:base
seedbrain config --profile my.json           # final merged config
```

The inheritance chain, not the source files, is the truth after merging. Never
debug a threshold by reading the profile you wrote — read `config` output.

---

## 9. `paths.root` and the `profiles/` convention

If your profile lives in a directory literally named `profiles/`, the root is
taken to be its parent. That makes the common layout work with no configuration:

```
repo/
  profiles/example.json     → root = repo/
  notes/methods.md          → declared as "notes/methods.md"
```

Any other location makes the profile's own directory the root. Override with
`--root` or a `"root"` field when neither fits.

---

## 10. `probes_ref` — share probes without copying

`verify.probes` is a list, so `extends` would replace it wholesale. Probe reuse
therefore has its own field:

```json
{
  "verify": {
    "probes_ref": "builtin:probes/core",
    "probes": ["domain-specific task one", "domain-specific task two"]
  }
}
```

Expansion order is **pool first, local second**. `seedbrain config` reports the
provenance:

```json
"probes_source": { "ref": "builtin:probes/core", "pool": 8, "local": 2 }
```

### `builtin:` resolution

`builtin:name` resolves inside the installed package (`seedbrain/data/`), with
`.json` optional:

```json
{ "extends": "builtin:base" }
```

This is how a domain repo references shared config with **zero copies, zero
drift, and version tracking through the SDK**. The file ships in the wheel, so
it works after a plain `pip install` — unlike `profiles/example.json`, which
belongs to the repository only.

Available today: `builtin:base`, `builtin:probes/core`.

---

## 11. Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `不是合法 JSON` | single backslashes in a regex | double every backslash inside JSON |
| `解析出 0 条种子` | `entry_re` mismatch, usually `—` vs `——` | compare one real line against the regex |
| `source.layer 未在 layers 中声明` | typo between `sources[].layer` and `layers{}` keys | they must match exactly |
| `layers.x.prefix 不能为空` | layer declared without `prefix` | add one |
| `schema_version 必须是 1` | copied from an older/newer doc | set `1` |
| Windows path breaks | `"C:\dir"` inside JSON | use forward slashes or `\\` |
| `T9` always skipped | no `legacy_shelf` | add your own old shortlist, or accept the skip |
| `T5` fails on a tiny corpus | fewer than ~4 competing seeds | grow the corpus; do not lower `rotation_min` |
