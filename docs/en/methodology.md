<p align="right">
  <b>English</b> · <a href="../zh-CN/methodology.md">简体中文</a> ·
  <a href="../../README.md">← README</a>
</p>

# Methodology — how it ranks, and where it breaks

> This document explains **why** the four mechanisms are built the way they are,
> and **when you should stop trusting them**. You can use the tool without
> reading it; after reading it, you will know when not to.

---

## 0. Why not semantic retrieval

The project deliberately uses **character n-grams + IDF** instead of embeddings.

1. **Zero dependencies.** No model weights, no network, no GPU. It runs in an
   air-gapped CI box, a container with no egress, a locked-down enterprise
   environment.
2. **Reproducibility.** Same input, same output. An embedding model upgrade
   reshuffles every historical ranking, and assertions can no longer be compared
   across versions.
3. **Explainability.** Every hit can be printed as `(signal, weight)`. A user can
   ask "why this one?" and get an answer.

The cost is explicit: **paraphrases are not guaranteed to match** ("austere" vs
"cold"). That is a conscious trade, discussed in §7.

---

## 1. Tokenisation: all of the 2-grams, a little of the 3-grams

Chinese has no word boundaries. Adding a segmenter adds a dictionary dependency,
and segmentation results drift with dictionary versions.

So: a sliding window over characters.

```
"赛博霓虹" → 2-grams: 赛博, 博霓, 霓虹    3-grams: 赛博霓, 博霓虹
```

- **2-gram weight 1.0** — `霓虹` matches 赛博霓虹, 雨夜霓虹, 霓虹倒影.
- **3-gram weight 0.35** — Chinese trigrams frequently straddle word boundaries
  (信息密度 → 息密), so they act as confirmation, not evidence.

Latin words are extracted separately and lowercased. Stop words (`style`, `的`,
`ai`, …) are dropped.

> `ai` is deliberately a stop word. In task descriptions "AI" means artificial
> intelligence; in the source library `` `AI:` `` is a prompt prefix. The rule
> came from a real false positive: the artist 艾未未 was recalled because the
> name contains `Ai`.

---

## 2. IDF: let rare but precise signals speak louder

```
idf(g) = log(1 + N / (1 + df(g)))
```

- `df = 1` (rare) → about `log(1 + N)`; for N = 200, ≈ 5.3
- `df = 100` (common) → about `log(1 + 2)` ≈ 1.1

That **3–5× weight gap** is the mathematical source of "unbiasedness". It does
not scramble results randomly; it lets rare signals dominate when they match.

### Why T4 is split into two assertions

An early version only compared end-to-end results (IDF on vs off, top-1 hit
rate). On small corpora both measured 72.7% — not because the algorithm was
broken, but because the rare probe word belonged only to the target seed, so
turning IDF off still left the target with that single point.

The end-to-end comparison depends on "a large corpus with lots of short text and
generic words", which a small fixture cannot manufacture. Therefore:

- **T4a (hard assertion)**: IDF monotonicity — smaller `df` implies larger
  `idf`. Deterministic, independent of corpus size, and it can genuinely fail.
- **T4b (non-regression check)**: end-to-end top-1 comparison, requiring only
  that IDF-on is not materially worse. It still catches large-corpus regressions.

---

## 3. Length normalisation: gentle, not punitive

```
score = raw / (1 + log1p(grams) / 10)
```

An early version used `sqrt(grams)`, which crushed layers whose entries were
longer and destroyed the "spread everything flat" property.

Long text carries more information and should be more likely to be relevant; the
only thing to defend against is stacking points by sheer gram count. So the
denominator is logarithmic and its coefficient is just 1/10.

---

## 4. Cross-layer quotas: guarantee first, fill later

`top-K` cannot be taken purely by score, or a large layer (352 chapter entries)
would squeeze out a small one (12 code-genre cards).

**Two-phase allocation:**

1. **Guarantee** — each layer takes `min(floor(k×quota), candidates)` by score.
2. **Fill** — remaining slots go to global score; a layer with no candidates
   yields its quota to layers that have some.

Then `sum(quota) ≤ K` is enforced by trimming the peak, otherwise the guaranteed
slots get truncated at the end anyway.

> The project's own assertion T6a caught a real bug here: the old implementation
> only prevented "a layer exceeding its quota", not "a layer with stock getting
> no slot". A single score-ordered scan put weak-layer candidates outside K, so
> the quota was configured but never honoured.

---

## 5. Time decay: the only source of diversity

```
recovery   = 1 - exp(-Δt / τ)          τ = 14 days
count_pen  = 1 / (1 + 0.5·ln(1+count))
novelty    = max(0.15, recovery × count_pen)
```

- Just used (Δt = 0) → `recovery = 0`, but the `0.15` floor keeps "reproduce last
  time's result" possible.
- After 14 days → `recovery ≈ 0.63`.
- After 60 days → `recovery ≈ 0.99` (then multiplied by the count penalty).

**The deliberate choice: no randomness.**

Randomness produces diversity, but it is *unsuitable but different*. Decay
produces *equally suitable but different*. Run the same task a few days apart and
the candidates rotate naturally; run it twice in one day and results are stable.

> The floor applies to the **final value**, not just to `recovery`. Written as
> `max(0.15, recovery) × count_pen`, a just-used seed dropped to 0.11 and
> reproducibility was effectively gone.

---

## 6. Incremental updates: three hard constraints

| Constraint | Why | Enforced by |
|---|---|---|
| **Existing IDs are never rewritten** | a changed ID breaks flavour logs, state memory, external references | T12 |
| **Incremental result ≡ full rebuild** | anything else means the index lies | T10 (split-half) |
| **`ref` must exist and stay in bounds** | a wrong path becomes a silent dead link | T1c + `Profile.resolve` |

The increment pool (`additions.jsonl`) is kept separate from source files:

- the source library is a **human-curated artifact**; blind script inserts break
  layering and formatting contracts;
- the pool is auditable, revertible, and reviewable in batches;
- deleting a line after backfilling leaves `build` output unchanged (idempotent).

### Why duplicate detection uses containment, not Jaccard

A new seed usually has only a name plus a few signals (short); an existing card
is long. Jaccard's union denominator dilutes similarity to ~0.05, so **duplicate
detection would never fire**.

```
containment = |A ∩ B| / min(|A|, |B|)
```

It answers the question that matters: "is this an alias of that existing one?"

---

## 7. Known limits — when not to trust it

| Limit | Symptom | Guidance |
|---|---|---|
| **Not semantic retrieval** | paraphrases ("austere" ↔ "cold") may miss | add common phrasings to `signals`; or wait for a vector backend |
| **2-gram straddles words** | 条件数 also yields 件数 | scoring is unaffected (IDF still points at the right cluster); display already de-duplicates |
| **IDF is weak on tiny corpora** | under ~30 seeds, rare words belong only to their own entry | T4b only requires "no regression"; real discrimination needs a real corpus |
| **Linear scan** | O(N) per query | under 1e4 seeds a query is <500 ms; beyond that needs an index (v0.4) |
| **State is local** | multiple machines/agents do not share usage | day-granularity reduces the impact; cross-machine sharing needs external state |

---

## 8. One design discipline

**An assertion must be able to fail.**

Development was caught by its own assertions three times:

1. quota had an upper bound but no lower bound → weak layers starved;
2. `novelty` floor multiplied by count penalty dropped to 0.11 → reproducibility lost;
3. the legacy-shelf sample referenced three non-existent IDs → the downstream
   decentralisation assertion was true by construction (always PASS).

The third is the most dangerous: **a permanently green test is worse than no
test.** That is why `verify` includes T1d, an assertion that checks the tests
themselves.

---

## 9. What this buys, in one line

Suitability is decided by IDF — deterministic, explainable, reproducible.
Diversity is produced by state memory — the same task a few days later returns
different *equally suitable* candidates, not random unsuitable ones.
