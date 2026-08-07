"""mining-core — mine i+1 Spanish study sentences from EPUBs, with morphology.

A language/tool-agnostic core: extract clean prose from an EPUB, segment with spaCy,
select "i+1" sentences (one worth-learning content word each), and attach deterministic
grammar analysis (tense/mood/person/number/gender + cue phrases) and frequency banding.

Downstream tools turn candidates into whatever they need — Anki cloze decks, a typing
practice platform, a reader — via the shared ``Candidate``/``EnrichedItem`` schema.

Typical use::

    from spanish_sentence_miner import extract_book, load_nlp, select_candidates, SelectionConfig

    nlp = load_nlp()
    book = extract_book(book_id=1, title="…", authors="…", epub_path=path)
    candidates = select_candidates(nlp, book, known=set(), cfg=SelectionConfig())
"""

from __future__ import annotations

from spanish_sentence_miner.enrich.schema import (
    Candidate,
    EnrichedItem,
    GrammarInfo,
    ParallelRef,
    load_candidates,
    load_enriched,
    make_id,
    write_jsonl,
)
from spanish_sentence_miner.extract import Chapter, ExtractedBook, extract_book
from spanish_sentence_miner.mining.known import KnownStore
from spanish_sentence_miner.mining.select import SelectionConfig, select_candidates
from spanish_sentence_miner.nlp.frequency import band_for_word, band_for_zipf
from spanish_sentence_miner.nlp.morphology import analyze_grammar
from spanish_sentence_miner.nlp.pipeline import (
    Sentence,
    SpacyModelMissing,
    Token,
    analyze_paragraph,
    load_nlp,
    norm_lemma,
)
from spanish_sentence_miner.textbook.schema import (
    Exercise,
    ExerciseItem,
    GrammarNote,
    Unit,
    exercise_id,
    item_id,
    load_exercises,
    load_grammar_notes,
    load_items,
    load_units,
)

__version__ = "0.1.2"  # x-release-please-version

__all__ = [
    "Candidate",
    "Chapter",
    "EnrichedItem",
    "Exercise",
    "ExerciseItem",
    "ExtractedBook",
    "GrammarInfo",
    "GrammarNote",
    "KnownStore",
    "ParallelRef",
    "Sentence",
    "SelectionConfig",
    "SpacyModelMissing",
    "Token",
    "Unit",
    "analyze_grammar",
    "analyze_paragraph",
    "band_for_word",
    "band_for_zipf",
    "exercise_id",
    "extract_book",
    "item_id",
    "load_candidates",
    "load_enriched",
    "load_exercises",
    "load_grammar_notes",
    "load_items",
    "load_units",
    "load_nlp",
    "make_id",
    "norm_lemma",
    "select_candidates",
    "write_jsonl",
]
