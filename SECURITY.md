# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's [private vulnerability reporting](https://github.com/hhx465453939/agent-seed-brain/security/advisories/new)
(Security → Advisories → "Report a vulnerability"). If that is unavailable, open an issue
containing only "security contact requested" and a maintainer will reach out.

We aim to acknowledge within **72 hours** and to ship a fix or mitigation within **14 days**
for confirmed issues.

## Scope

This is a local library with no network access and no server. The realistic attack surface:

| Area | What we care about |
|---|---|
| **Path handling** | `Profile.resolve()` must reject paths escaping the knowledge-base root; `ref` values in profiles and addition records are untrusted input. |
| **Untrusted profile files** | A profile is code-adjacent: it supplies regular expressions. Catastrophic backtracking on a hostile regex would hang `build`. Reports of practical ReDoS against realistic source files are in scope. |
| **Untrusted seed sources** | Markdown/text files are parsed but never executed. Anything that turns a source file into code execution is in scope. |
| **Dependency supply chain** | Runtime dependencies are intentionally zero. If a dependency ever appears in `[project] dependencies`, that is a bug — please report it. |
| **Data exfiltration** | The library performs no network I/O. Any network call from `src/seedbrain/` is a bug. |

## Out of scope

- Prompt-injection content inside *your own* seed libraries (that is data, not code)
- Denial of service via an intentionally enormous corpus (documented scaling limits: `docs/en/methodology.md` §7)
- Issues that require an attacker to already control your filesystem or Python environment

## Hardening notes for users

- Treat third-party profiles as you would third-party code.
- Keep `references/` corpora under version control; `seedbrain build` is deterministic, so diffs are meaningful.
- `.seed-usage.json` and `seed-additions.jsonl` are local state — do not commit machine-specific usage history if you share a repo.
