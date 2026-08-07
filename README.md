# spanish-sentence-miner

[![CI](https://github.com/cuttlefisch/spanish-sentence-miner/actions/workflows/ci.yml/badge.svg)](https://github.com/cuttlefisch/spanish-sentence-miner/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/cuttlefisch/spanish-sentence-miner?sort=semver)](https://github.com/cuttlefisch/spanish-sentence-miner/releases)
[![License: GPL v3+](https://img.shields.io/badge/license-GPLv3+-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](pyproject.toml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://www.conventionalcommits.org)

Mine **i+1 Spanish study sentences** from EPUBs, with deterministic morphology and
word-frequency banding. A small, tool-agnostic library: give it an EPUB, get back clean
sentences that each teach one worth-learning content word, annotated with conjugation/gender
grammar and a difficulty band.

It powers an Anki deck builder and a typing-practice platform — nothing here is tied to Anki,
Calibre, or any personal data.

## What it does
- **`extract_book`** — clean prose out of an EPUB (spine order, front/back-matter stripped).
- **`load_nlp` / `analyze_paragraph`** — spaCy Spanish pipeline → sentences of tokens with
  sentence-local character spans and morphology.
- **`select_candidates`** — i+1 selection: sentences with exactly one worth-learning target
  (filters proper nouns, over-common/ultra-rare words, dialogue, near-duplicates).
- **`analyze_grammar`** — deterministic tense/mood/person/number/gender + cue phrases
  (subjunctive triggers, preterite/imperfect aspect, ser/estar).
- **`band_for_word`** — coarse frequency bands via `wordfreq`.
- **`KnownStore`** — SQLite set of already-known lemmas so re-runs never re-mine them.
- **`Candidate` / `EnrichedItem`** — the shared, JSONL-serialisable data contract.

## Install
```sh
# git-only for now (pin to a release tag):
pip install "git+https://github.com/cuttlefisch/spanish-sentence-miner.git@v0.1.0"
python -m spacy download es_core_news_md   # the model is NOT a PyPI dependency
```

## Usage
```python
from pathlib import Path
from spanish_sentence_miner import extract_book, load_nlp, select_candidates, SelectionConfig

nlp = load_nlp()
book = extract_book(book_id=1, title="Título", authors="Autor", epub_path=Path("book.epub"))
candidates = select_candidates(nlp, book, known=set(), cfg=SelectionConfig(prefer_verbs=True))

for c in candidates[:3]:
    print(c.sentence)
    print("  target:", c.target_surface, "→", c.target_lemma, "|", c.grammar.label)
```

Each `Candidate` carries the sentence, the target span (`char_start`/`char_end`), the
`grammar` analysis, and frequency metadata — enough to build a cloze card, a fill-in-the-blank
typing question, or a grammar-aware grader.

## Contributing
Commits follow [Conventional Commits](https://www.conventionalcommits.org); releases are
automated with [release-please](https://github.com/googleapis/release-please). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License
[GPL-3.0-or-later](LICENSE). Free software, free society.
