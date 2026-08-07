"""spaCy Spanish analysis: paragraphs → sentences → tokens with sentence-local spans.

Token character spans are relative to their *sentence* text (not the paragraph), so
downstream cloze wrapping can slice the sentence directly and robustly, even when the
target surface form repeats elsewhere in the sentence.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from spanish_sentence_miner.config import SPACY_MODEL

# UPOS tags we treat as learnable "content" words worth studying.
CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})
# Named-entity types (spaCy Spanish) whose tokens must never become cloze targets.
ENTITY_TYPES = frozenset({"PER", "LOC", "ORG", "MISC"})


@dataclass(frozen=True)
class Token:
    text: str  # surface form
    lemma: str
    pos: str  # UPOS
    is_alpha: bool
    is_stop: bool
    is_propn: bool
    ent_type: str
    char_start: int  # offset within the sentence text
    char_end: int
    #: spaCy morphological features as a sorted tuple of (key, value) — a tuple (not a
    #: dict) so Token stays frozen/hashable. e.g. (("Mood","Sub"),("Tense","Pres"),...)
    morph: tuple[tuple[str, str], ...] = ()

    @property
    def morph_dict(self) -> dict[str, str]:
        return dict(self.morph)

    @property
    def is_content(self) -> bool:
        return self.pos in CONTENT_POS

    @property
    def is_entity(self) -> bool:
        return self.is_propn or self.ent_type in ENTITY_TYPES

    @property
    def is_study_candidate(self) -> bool:
        """A token eligible (before known/frequency filters) to be a cloze target."""
        return self.is_content and self.is_alpha and not self.is_stop and not self.is_entity


@dataclass(frozen=True)
class Sentence:
    text: str
    tokens: tuple[Token, ...]

    @property
    def has_finite_verb(self) -> bool:
        return any(t.pos in ("VERB", "AUX") for t in self.tokens)

    @property
    def alpha_token_count(self) -> int:
        return sum(1 for t in self.tokens if t.is_alpha)


class SpacyModelMissing(RuntimeError):
    """Raised when the Spanish spaCy model isn't installed."""


@functools.lru_cache(maxsize=1)
def load_nlp():  # type: ignore[no-untyped-def]
    """Load (and cache) the Spanish spaCy pipeline, or raise a clear install hint."""
    import spacy

    try:
        return spacy.load(SPACY_MODEL)
    except OSError as exc:  # model not installed
        raise SpacyModelMissing(
            f"spaCy model {SPACY_MODEL!r} is not installed. Run:\n"
            f"    poetry run python -m spacy download {SPACY_MODEL}"
        ) from exc


def analyze_paragraph(nlp, text: str) -> list[Sentence]:  # type: ignore[no-untyped-def]
    """Segment a paragraph into sentences of tokens with sentence-local char spans."""
    doc = nlp(text)
    sentences: list[Sentence] = []
    for sent in doc.sents:
        base = sent.start_char
        tokens = tuple(
            Token(
                text=tok.text,
                lemma=tok.lemma_,
                pos=tok.pos_,
                is_alpha=tok.is_alpha,
                is_stop=tok.is_stop,
                is_propn=tok.pos_ == "PROPN",
                ent_type=tok.ent_type_,
                char_start=tok.idx - base,
                char_end=tok.idx - base + len(tok.text),
                morph=tuple(sorted(tok.morph.to_dict().items())),
            )
            for tok in sent
            if not tok.is_space
        )
        stripped = sent.text.strip()
        if stripped:
            sentences.append(Sentence(text=sent.text, tokens=tokens))
    return sentences


def norm_lemma(lemma: str) -> str:
    """Normalize a spaCy lemma for keying/dedup.

    Spanish spaCy splits clitic verbs into multi-token lemmas ("deshacerte" →
    "deshacer tú", "riéndose" → "reir él"); keep only the head token so the
    known-words store, per-lemma dedup, and infinitive display collapse correctly.
    """
    return lemma.split()[0].lower() if lemma else lemma
