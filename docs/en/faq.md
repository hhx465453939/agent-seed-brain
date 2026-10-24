<p align="right">
  <b>English</b> · <a href="../zh-CN/faq.md">简体中文</a> ·
  <a href="../../README.md">← README</a>
</p>

# FAQ and troubleshooting

---

## Is this a RAG system?

Not in the usual sense. RAG retrieves **passages** to put into a prompt. `seedbrain`
retrieves **options to choose from** — a shortlist of candidates with the signals
that matched, so the model picks one instead of inventing one.

| | RAG | seedbrain |
|---|---|---|
| Retrieval unit | text chunk | named seed (an option) |
| Goal | supply context | constrain the choice |
| Output | passage | `id`, `name`, score, hit signals |
| Failure mode | irrelevant context | no candidate matched |

It composes with RAG: retrieve candidates first, then retrieve detail for the
chosen one via its `ref`.

---

## Why not embeddings?

Because the goal is a **defensible, reproducible shortlist**, not fuzzy recall.
Embeddings buy paraphrase robustness and cost determinism, offline operation,
and explainability. See `methodology.md` §0 for the full trade and §7 for the
consequence: paraphrases may miss.

If you need paraphrase robustness, add common phrasings to `signals` — that is a
one-line data change, not an infrastructure change.

---

## Why zero runtime dependencies?

Three reasons that all come back to reliability:

1. installation cannot break on a transitive conflict;
2. it runs where package managers cannot reach;
3. the CI "no runtime deps" assertion makes the promise enforceable rather than
   aspirational.

The cost is that you get character n-grams instead of a tokenizer. For this tool's
job — matching short task descriptions against short seed names — that is a good
trade.

---

## How does it handle English and Chinese together?

2-grams and 3-grams are computed over characters, which works for CJK. Latin
words are extracted as whole tokens and lowercased. Mixed input is fine:

```bash
seedbrain match "降维压缩 PCA 选型" --profile seedbrain.json
```

Chinese 3-grams are down-weighted because Chinese trigrams often straddle word
boundaries. English has no such penalty.

---

## `match` returns nothing. Why?

Check, in order:

1. **Did you build?** `match` reads the index. `seedbrain build --profile …` first.
2. **Did the source parse?** `build` fails loudly on zero seeds; if it succeeded,
   look at `references/SEED-INDEX.md` and confirm your entries are there.
3. **Is the task wording disjoint from the seed text?** The matcher is lexical.
   If your library says "singular value decomposition" and the task says
   "dimensionality reduction", add the Chinese/English synonyms to the entry's
   `tag` or `desc`, or to `signals` via `seedbrain add`.
4. **Is `--k` too small?** Try `--k 20`.

---

## `verify` failed. Do I lower the threshold?

No. That is the one thing the project asks you not to do.

Work through it instead:

1. read the failing check's metric and target;
2. ask whether the **implementation** or the **assertion** is wrong — both have
   happened in this project's history;
3. if the corpus is a toy, the failure may be legitimate (§ next question) — use
   `--group schema` for a structural gate, or grow the corpus.

`docs/methodology.md` §8 documents three cases where the assertion caught a real
bug that would otherwise have shipped.

---

## Why does T5 fail on my five-entry test corpus?

T5 requires **four distinct top-1 picks across six consecutive runs**. With fewer
than ~4 competing candidates that is arithmetically impossible. The threshold is
not lowered, because lowering it would make the check unable to detect the real
regression it was written for (a layer starved by scoring order).

Grow the corpus, or run `--group schema`.

---

## `verify --json` is not valid JSON

Correct — progress lines are printed before the JSON object. Parse from the first
brace:

```bash
seedbrain verify --profile x.json --json | sed -n '/^{/,$p' | jq .
```

`match --json` emits pure JSON and has no such caveat.

---

## How fast is it?

Linear scan, no ANN index. Measured on a laptop:

| Corpus size | Query time |
|---|---|
| 1e3 seeds | single-digit ms |
| 1e4 seeds | under 500 ms |

Beyond that you want an index structure, which is on the roadmap (v0.4). For the
intended use — a few hundred to a few thousand seeds per domain — scanning is
not the bottleneck.

---

## Does the state sync across machines?

No. `state` is a local JSON file. Two agents on two machines keep independent
usage histories. Options: share the file over a mounted volume, accept the
divergence, or wait for a pluggable state backend.

Because decay uses **day granularity**, divergence between machines is far less
harmful than it would be with per-call counters.

---

## `add` versus editing the source file

`add` writes to the increment pool and rebuilds; it never touches your curated
sources. That is intentional:

- sources are human-reviewed artifacts with formatting contracts;
- the pool is auditable and revertible line by line;
- after you backfill an entry into the source file and delete the pool line, the
  build output is unchanged.

Use `add` for experiments and newly discovered entries; backfill into sources
once an entry proves itself.

---

## Can I use it on source code or documents?

Yes — the parser is generic. A "table" source is any file where one line holds a
name and a description; a "card" source is a directory where each file is one
entry. Code repositories, ADR collections, runbooks, prompt libraries all fit.

What does not fit: content whose meaning lives in paragraphs, where a one-line
description cannot stand in for the thing. That is what retrieval-augmented
generation is for.

---

## Is commercial use allowed?

Yes. From v0.5.0 the whole repository is **Apache License 2.0** — an OSI-approved
open source license that permits commercial use, modification, and redistribution,
as long as you keep the copyright and NOTICE attribution and comply with the
license terms. Versions up to and including v0.3.x were published under
CC BY-NC-SA 4.0 and keep that license. See `LICENSE` and `NOTICE`.

---

## Where do I report a bug?

Open an issue with:

- the exact command;
- `python -c "import sys, seedbrain; print(sys.version, seedbrain.__version__)"`;
- `seedbrain verify --profile <yours> --json`.

Security issues: see `SECURITY.md`.
