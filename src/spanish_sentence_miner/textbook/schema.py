"""Portable structured form of a grammar textbook — the process-once learning corpus.

Unlike prose books (mined i+1 sentences), a grammar textbook is **exercise-based with an
answer key**: every item carries a ground-truth answer. This module is the app-agnostic
contract both the Anki deck builder and the typing-practice platform (and future methods)
consume, so the source EPUB is parsed only once. Append-only JSONL keyed by a stable id,
mirroring the ``Candidate``/``EnrichedItem`` contract in ``enrich.schema``.

Four record streams (one JSONL file each), all carrying ``book_id`` and joinable by id:
- ``Unit``         — one grammar chapter (``id`` = chapter number).
- ``GrammarNote``  — a heading + the book's own explanation prose (for card context / a
                     future "learn" view).
- ``Exercise``     — one exercise (``EJERCICIO {ch}·{n}``): instruction, kind, gradable flag.
- ``ExerciseItem`` — one numbered item: prompt + answer-key answer, joined item-for-item.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from spanish_sentence_miner.enrich.schema import write_jsonl

__all__ = [
    "Exercise",
    "ExerciseItem",
    "ExerciseKind",
    "GrammarNote",
    "TEXTBOOK_SCHEMA_VERSION",
    "Unit",
    "exercise_id",
    "item_id",
    "load_exercises",
    "load_grammar_notes",
    "load_items",
    "load_units",
    "write_jsonl",
]

TEXTBOOK_SCHEMA_VERSION = 1

#: Exercise flavour, inferred from the instruction. ``open`` = "answers will vary"
#: (not auto-gradable); ``other`` = anything unclassified.
ExerciseKind = Literal[
    "fill", "conjugation", "translation", "true_false", "reword", "spelling", "open", "other"
]


def exercise_id(book_id: int, chapter: int, exercise: int) -> str:
    """Stable exercise id: ``{book}:{chapter:02d}:{exercise:02d}``."""
    return f"{book_id}:{chapter:02d}:{exercise:02d}"


def item_id(book_id: int, chapter: int, exercise: int, item: int) -> str:
    """Stable item id: ``{book}:{chapter:02d}:{exercise:02d}:{item:03d}``."""
    return f"{book_id}:{chapter:02d}:{exercise:02d}:{item:03d}"


class Unit(BaseModel):
    """One grammar chapter/unit of the textbook."""

    id: int  # chapter number (1-based)
    book_id: int
    title: str
    source: str = ""  # originating document, e.g. "ch3.xhtml"


class GrammarNote(BaseModel):
    """A heading and the book's own explanation prose beneath it."""

    id: str  # stable: f"{book}:{chapter:02d}:g{index:03d}"
    book_id: int
    unit: int  # chapter number
    heading_path: list[str] = Field(default_factory=list)  # e.g. ["Present tense", "Irregulars"]
    level: int = 3  # heading level (h2=2 … h5=5)
    text: str = ""


class Exercise(BaseModel):
    """One exercise (``EJERCICIO {ch}·{n}``) — its instruction and classification."""

    id: str  # exercise_id(...)
    book_id: int
    unit: int  # chapter number
    number: int  # exercise number within the chapter
    label: str  # display form, e.g. "3·2"
    title: str = ""  # leading label, e.g. "Traducción"
    instruction: str = ""
    kind: ExerciseKind = "other"
    gradable: bool = True  # False for "answers will vary" / image-dependent
    heading_path: list[str] = Field(default_factory=list)  # grammar topic this sits under
    prompt_lang: str = "es"  # 'en' for English→Spanish translation prompts
    answer_lang: str = "es"
    schema_version: int = TEXTBOOK_SCHEMA_VERSION


class ExerciseItem(BaseModel):
    """One numbered item: the prompt and its answer-key answer (joined item-for-item)."""

    id: str  # item_id(...)
    exercise_id: str
    book_id: int
    unit: int  # chapter number
    number: int  # item number within the exercise
    prompt: str = ""
    answer: str = ""
    answer_note: str = ""  # e.g. a sample answer for open-ended items
    gradable: bool = True
    schema_version: int = TEXTBOOK_SCHEMA_VERSION


def _iter_lines(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                yield stripped


def _load[T: BaseModel](path: Path, model_cls: type[T]) -> tuple[list[T], int]:
    """Validate a JSONL file into models (last-write order preserved), counting bad lines.

    Invalid lines are skipped (not fatal), mirroring ``load_enriched`` — one bad row never
    sinks the batch; the caller reports the skip count.
    """
    out: list[T] = []
    bad = 0
    if not path.exists():
        return out, bad
    for line in _iter_lines(path):
        try:
            out.append(model_cls.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError):
            bad += 1
    return out, bad


def load_units(path: Path) -> tuple[dict[int, Unit], int]:
    """Load ``units.jsonl`` into a ``chapter -> Unit`` map (+ bad-line count)."""
    rows, bad = _load(path, Unit)
    return {u.id: u for u in rows}, bad


def load_grammar_notes(path: Path) -> tuple[dict[str, GrammarNote], int]:
    """Load ``grammar_notes.jsonl`` into an ``id -> GrammarNote`` map (+ bad-line count)."""
    rows, bad = _load(path, GrammarNote)
    return {g.id: g for g in rows}, bad


def load_exercises(path: Path) -> tuple[dict[str, Exercise], int]:
    """Load ``exercises.jsonl`` into an ``id -> Exercise`` map (+ bad-line count)."""
    rows, bad = _load(path, Exercise)
    return {e.id: e for e in rows}, bad


def load_items(path: Path) -> tuple[dict[str, ExerciseItem], int]:
    """Load ``items.jsonl`` into an ``id -> ExerciseItem`` map (+ bad-line count)."""
    rows, bad = _load(path, ExerciseItem)
    return {i.id: i for i in rows}, bad
