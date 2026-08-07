"""The file-based enrichment contract between the deterministic tool and Claude Code.

- ``Candidate``     — written by ``enrich-prep`` into ``candidates.jsonl``.
- ``EnrichedItem``  — written by Claude Code into ``enriched.jsonl``, echoing ``id``.

Both files are append-only JSONL keyed by ``id`` (last write wins on load), which is
what makes enrichment resumable and idempotent.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

SCHEMA_VERSION = 2

Band = str  # one of nlp.frequency.BANDS
Difficulty = str  # 'easy' | 'medium' | 'hard'


def make_id(book_id: int, chapter_index: int, sentence_index: int) -> str:
    """Stable, deterministic candidate id: ``{book}:{chapter:04d}:{sentence:04d}``."""
    return f"{book_id}:{chapter_index:04d}:{sentence_index:04d}"


class GrammarInfo(BaseModel):
    """Deterministic morphology of the cloze target (from spaCy ``token.morph``).

    Rich for verbs, light (gender/number) for nouns/adjectives. ``triggers`` are short
    deterministic cue strings Claude turns into the natural-language ``grammar_why``.
    """

    kind: str = "other"  # verb | noun | adjective | other
    infinitive: str | None = None  # verbs: normalized lemma
    tense: str | None = None  # present | preterite | imperfect | future | conditional | pluperfect
    mood: str | None = None  # indicative | subjunctive | imperative | conditional
    person: str | None = None  # '1st person' | '2nd person' | '3rd person'
    number: str | None = None  # singular | plural
    gender: str | None = None  # masculine | feminine
    verbform: str | None = None  # finite | infinitive | gerund | participle
    reflexive: bool = False
    label: str = ""  # human string, e.g. 'present subjunctive, 3rd person singular'
    triggers: list[str] = Field(default_factory=list)


class ParallelRef(BaseModel):
    """Pointer into a cached English counterpart bounding the reference-translation search."""

    eng_book_id: int
    chapter_index: int  # index into the cached EN extracted book's chapters
    para_start: int  # inclusive paragraph-window bound
    para_end: int  # exclusive


class Candidate(BaseModel):
    """One mined sentence with its cloze target — the tool's output, Claude's input."""

    id: str
    book_id: int
    book_title: str
    sentence: str
    target_lemma: str
    target_surface: str
    token_index: int
    char_start: int  # span of target_surface within `sentence`
    char_end: int
    local_freq: int  # occurrences of target_lemma within this book
    external_zipf: float
    external_band: Band
    difficulty_hint: Difficulty
    # --- v2 additions (defaulted for backward compatibility) ---
    pos: str = ""  # UPOS of the target (VERB/NOUN/ADJ/...)
    grammar: GrammarInfo = Field(default_factory=GrammarInfo)
    para_index: int | None = None  # paragraph index of the sentence within its chapter
    parallel_ref: ParallelRef | None = None


class EnrichedItem(BaseModel):
    """Claude Code's enrichment for a candidate, joined back on ``id``."""

    id: str
    # Defaults to "" so a Tier-0 (deterministic-only, no-AI) card can be built with no
    # gloss; the card templates hide an empty gloss via {{#Gloss}} and the gloss cache's
    # ``put_gloss`` filters empties, so relaxing this never weakens real enrichment.
    english_gloss: str = ""
    pos: str = ""
    note: str = ""
    example: str = ""
    difficulty: Difficulty = "medium"
    model_tier: str = ""  # provenance: 'cheap' | 'mid' | 'strong'
    # --- v2 additions ---
    translation_en: str = ""  # published EN sentence chosen by Claude from the parallel window
    grammar_why: str = ""  # NL explanation of the form, grounded in grammar.triggers
    #: Corrected conjugation label when spaCy's deterministic one is wrong (empty = trust spaCy).
    morph_label_override: str = ""
    schema_version: int = SCHEMA_VERSION


def write_jsonl(path: Path, models: Iterable[BaseModel]) -> int:
    """Write models as JSONL (one compact object per line). Returns the count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for model in models:
            fh.write(model.model_dump_json())
            fh.write("\n")
            count += 1
    return count


def _iter_json_lines(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_candidates(path: Path) -> dict[str, Candidate]:
    """Load candidates.jsonl into an ``id -> Candidate`` map (last write wins)."""
    out: dict[str, Candidate] = {}
    if not path.exists():
        return out
    for obj in _iter_json_lines(path):
        c = Candidate.model_validate(obj)
        out[c.id] = c
    return out


def load_enriched(path: Path) -> tuple[dict[str, EnrichedItem], int]:
    """Load enriched.jsonl into an ``id -> EnrichedItem`` map plus a count of bad lines.

    Invalid lines are skipped (not fatal) so one malformed row from the agent doesn't
    sink the whole batch; the caller reports the skip count.
    """
    out: dict[str, EnrichedItem] = {}
    bad = 0
    if not path.exists():
        return out, bad
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = EnrichedItem.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValidationError):
                bad += 1
                continue
            out[item.id] = item
    return out, bad
