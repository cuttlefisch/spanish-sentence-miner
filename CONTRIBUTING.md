# Contributing

Thanks for your interest! This is a small, focused library — clarity and correctness over
features.

## Dev setup
```sh
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
python -m spacy download es_core_news_md   # needed only for spaCy-backed behaviour
```

## Checks (run before pushing)
```sh
ruff check .
pytest
mypy         # advisory
```

## Commits & releases
- Commit messages follow **[Conventional Commits](https://www.conventionalcommits.org)**
  (`feat:`, `fix:`, `docs:`, `refactor:`, `perf:`, `test:`, `chore:`, `ci:`). PR titles are
  linted since we squash-merge.
- Releases, version bumps, tags, and the changelog are **automated** by
  [release-please](https://github.com/googleapis/release-please): merging conventional commits
  to `main` opens/updates a release PR; merging that PR cuts the release.
- `feat:` → minor, `fix:`/`perf:` → patch. Breaking changes: add a `!` (e.g. `feat!:`) or a
  `BREAKING CHANGE:` footer.

## Scope
Keep the core language/tool-agnostic — no Anki, Calibre, web, or personal-setup coupling.
Downstream apps build on the `Candidate`/`EnrichedItem` contract.
