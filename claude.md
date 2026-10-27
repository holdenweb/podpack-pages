# Claude Code notes for podpack-pages

This file is loaded into every Claude Code conversation in this repository —
keep it short. It began as boilerplate from Wing IDE's Claude integration;
this is no longer a Wing project, and the file is maintained by hand. How each
app kind works, and the contracts it keeps, is in the README.

## Invariants

Always-on rules. Each prevents a silent-failure mode.

1. **Never modify the remote.** Commits are local. Reading the remote is fine
   — `git fetch`, `git pull` — but never write to it: no `git push`, and
   nothing else that changes it. Never edit the repository destructively
   either: history rewriting (`git rebase`, `git reset --hard`), low-level
   repository edits, or mass-adding files (`git add -A`, `git add .`). Ask
   before creating branches.

2. **Commit finished work, locally.** When a coherent change set is done and
   the checks below are clean, commit it: stage named paths, read
   `git status --short` and `git diff --cached --stat` first, and write a
   message that explains why — the diff already says what. Then say what is
   not yet pushed and why it matters; pushing is the user's alone. Never bump
   the version unasked.

3. **Test first, and verify by running.** Write the test for new behaviour or a
   reported bug before the code, and see it fail: a test that has never failed
   is not evidence. If a first fix does not work, get runtime evidence — a
   failing test, `pytest --pdb`, a breakpoint — before trying a second.

4. **Never silently swallow exceptions.** Handle the expected and log the
   unexpected at every catch. Prefer a conditional check to `try`/`except` for
   an expected condition (None, a type, a boundary).

## Checks

From the repository root. A change is not done until all three are clean:

```bash
uv run pytest -q
uv run mypy
uv run ruff check src tests
```
