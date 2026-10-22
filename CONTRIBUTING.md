# Contributing

Thanks for wanting to make retrieval less biased. This project is deliberately small — please keep it that way.

## Ground rules

1. **Zero runtime dependencies.** `dependencies = []` in `pyproject.toml` is a product decision, not an accident. If your change needs a library, it belongs in `[project.optional-dependencies]` behind a flag, or it does not belong here. `dev` extras are fine — the *runtime* requirements must stay empty. CI asserts this by filtering out anything marked `extra ==`.
2. **Determinism is a feature.** No `random`, no built-in `hash()` (it is salted per process — use `hashlib`). Same input must yield byte-identical output.
3. **Every new behaviour needs an assertion.** If you add a mechanism, add a check in `src/seedbrain/verify.py` that can actually fail. A check that can never fail is worse than no check.
4. **No content, only rules.** `profiles/*.json` may contain parsing rules and quotas. It must not contain curated seed entries from upstream corpora.

## Development setup

No install needed to run the test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Optional (linting / packaging checks):

```bash
pip install -e ".[dev]"
ruff check src tests examples
python -m build
```

## The three checks CI runs

```bash
# 1. index is in sync with sources (catches "changed the docs, forgot to rebuild")
python -m seedbrain.cli build --profile profiles/example.json
git diff --exit-code -- tests/fixtures/mini-domain/

# 2. tests
PYTHONPATH=src python -m unittest discover -s tests

# 3. the library's own bias assertions
python -m seedbrain.cli verify --profile profiles/example.json
```

All three must pass. If `verify` fails, **do not lower the threshold** — find out whether it is the implementation or the assertion that is wrong. Both have happened before (see `docs/METHODOLOGY.md` §8).

## Commit messages

Conventional Commits, English or Chinese body, imperative mood:

```
feat(score): 两阶段配额改为先保底后补满
fix(profile): root 推断不再硬假设 profiles/ 子目录
docs(methodology): 补充 IDF 在小语料上的失效边界
test(cli): 覆盖坏 profile 的退出码
```

Breaking changes get a `!` (`feat(core)!: ...`) and a `BREAKING CHANGE:` footer.

## Pull request checklist

- [ ] `unittest` passes on your Python version
- [ ] `seedbrain verify` passes (28/28 on the example profile)
- [ ] New mechanism has a failing-if-broken assertion
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No curated seed content added to the repository
- [ ] No new runtime dependency

## Licensing

This project is licensed under **CC BY-NC-SA 4.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
Commercial use requires a separate written commercial license.

By submitting a pull request you agree that:

1. You have the right to submit the contribution.
2. Your contribution is licensed to this project under CC BY-NC-SA 4.0.
3. **You grant the maintainer a perpetual, worldwide, royalty-free, irrevocable
   license to relicense your contribution under any terms, including a
   commercial license.** Without this, a single commercial license covering the
   whole codebase would be impossible once outside contributions are merged.
4. You do not add text, code, or data whose license forbids redistribution here.

Do not paste text from other websites, books, or datasets unless you can point to
a license that permits redistribution here.

## Reporting bugs

Open an issue with:

- the exact command you ran
- `python -c "import sys, seedbrain; print(sys.version, seedbrain.__version__)"`
- the output of `seedbrain verify --profile <your profile> --json`

For security issues, see [SECURITY.md](SECURITY.md).
