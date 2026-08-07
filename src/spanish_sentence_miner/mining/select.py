"""i+1 sentence mining: pick sentences with exactly one worth-learning target word.

The heuristic favours sentences that teach a single new word in natural context — the
"i+1" principle from immersion learning. We filter out proper nouns, over-common and
ultra-rare words, dialogue fragments, and near-duplicates, then keep the best single
sentence per target lemma.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from spanish_sentence_miner.enrich.schema import Candidate, make_id
from spanish_sentence_miner.extract import ExtractedBook
from spanish_sentence_miner.nlp.frequency import band_for_word
from spanish_sentence_miner.nlp.morphology import analyze_grammar
from spanish_sentence_miner.nlp.pipeline import Sentence, Token, analyze_paragraph, norm_lemma

_TERMINAL = tuple(".!?…»\"'")
_DIALOGUE_START = ("—", "–", "-", "«", "“")
_PREFERRED_LEN = 12  # token count we consider the sweet spot for a card front


@dataclass(frozen=True)
class SelectionConfig:
    max_candidates_per_sentence: int = 1
    min_tokens: int = 6
    max_tokens: int = 30
    min_alpha_tokens: int = 4
    min_surface_len: int = 3
    require_finite_verb: bool = True
    target_bands: frozenset[str] = field(default_factory=lambda: frozenset({"mid", "rare"}))
    prefer_verbs: bool = False  # nudge selection toward verb targets (conjugation practice)
    verb_score_bonus: int = 3


# Back-compat alias; canonical implementation now lives in nlp.pipeline.
_norm_lemma = norm_lemma


def _difficulty_for_band(band: str) -> str:
    if band in ("very_common", "common"):
        return "easy"
    if band == "mid":
        return "medium"
    return "hard"


def _norm_hash(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.lower())
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch.isspace())
    normalized = " ".join(normalized.split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _clean_span(sentence: Sentence, target: Token) -> tuple[str, int, int]:
    """Left/right-strip the sentence text and shift the target span to match."""
    text = sentence.text
    lead = len(text) - len(text.lstrip())
    clean = text.strip()
    start = target.char_start - lead
    end = target.char_end - lead
    return clean, start, end


def _is_dialogue_only(sentence: Sentence) -> bool:
    stripped = sentence.text.strip()
    return stripped.startswith(_DIALOGUE_START)


def _sentence_ok(sentence: Sentence, cfg: SelectionConfig) -> bool:
    token_count = len(sentence.tokens)
    if not (cfg.min_tokens <= token_count <= cfg.max_tokens):
        return False
    if sentence.alpha_token_count < cfg.min_alpha_tokens:
        return False
    if cfg.require_finite_verb and not sentence.has_finite_verb:
        return False
    if not sentence.text.strip().endswith(_TERMINAL):
        return False
    if _is_dialogue_only(sentence):
        return False
    return True


def _analyze_book(nlp, extracted: ExtractedBook) -> list[tuple[int, int, int, Sentence]]:  # type: ignore[no-untyped-def]
    """Return (chapter_index, sentence_seq_in_chapter, paragraph_index, Sentence) per book."""
    out: list[tuple[int, int, int, Sentence]] = []
    for chapter in extracted.chapters:
        seq = 0
        for para_index, paragraph in enumerate(chapter.paragraphs):
            for sentence in analyze_paragraph(nlp, paragraph):
                out.append((chapter.index, seq, para_index, sentence))
                seq += 1
    return out


def _local_frequencies(sentences: list[tuple[int, int, int, Sentence]]) -> Counter[str]:
    """Count content-lemma occurrences across the whole book."""
    counter: Counter[str] = Counter()
    for *_, sentence in sentences:
        for tok in sentence.tokens:
            if tok.is_study_candidate:
                counter[_norm_lemma(tok.lemma)] += 1
    return counter


def select_candidates(
    nlp,  # type: ignore[no-untyped-def]
    extracted: ExtractedBook,
    known: set[str],
    cfg: SelectionConfig | None = None,
) -> list[Candidate]:
    """Mine i+1 cloze candidates from an extracted book. One card per target lemma."""
    cfg = cfg or SelectionConfig()
    sentences = _analyze_book(nlp, extracted)
    local_freq = _local_frequencies(sentences)

    # best candidate per lemma, plus dedup of near-identical sentences
    best: dict[str, tuple[int, Candidate]] = {}  # lemma -> (score, Candidate)
    seen_hashes: set[str] = set()

    for chapter_index, seq, para_index, sentence in sentences:
        if not _sentence_ok(sentence, cfg):
            continue

        # gather the sentence's study-candidate targets (post known/frequency filter)
        targets: list[tuple[Token, float, str]] = []
        for tok in sentence.tokens:
            if not tok.is_study_candidate:
                continue
            lemma = _norm_lemma(tok.lemma)
            if lemma in known:
                continue
            if len(tok.text) < cfg.min_surface_len:
                continue
            zipf, band = band_for_word(lemma)
            if band not in cfg.target_bands:
                continue
            targets.append((tok, zipf, band))

        if len(targets) != cfg.max_candidates_per_sentence:
            continue
        # exactly one target (given default config)
        target, zipf, band = targets[0]
        lemma = _norm_lemma(target.lemma)

        shash = _norm_hash(sentence.text)
        if shash in seen_hashes:
            continue

        clean_sentence, start, end = _clean_span(sentence, target)
        candidate = Candidate(
            id=make_id(extracted.book_id, chapter_index, seq),
            book_id=extracted.book_id,
            book_title=extracted.title,
            sentence=clean_sentence,
            target_lemma=lemma,
            target_surface=clean_sentence[start:end],
            token_index=target.char_start,
            char_start=start,
            char_end=end,
            local_freq=local_freq.get(lemma, 1),
            external_zipf=round(zipf, 3),
            external_band=band,
            difficulty_hint=_difficulty_for_band(band),
            pos=target.pos,
            grammar=analyze_grammar(sentence, target),
            para_index=para_index,
        )
        score = -abs(len(sentence.tokens) - _PREFERRED_LEN)
        if cfg.prefer_verbs and target.pos in ("VERB", "AUX"):
            score += cfg.verb_score_bonus
        existing = best.get(lemma)
        if existing is None or score > existing[0]:
            best[lemma] = (score, candidate)
            seen_hashes.add(shash)

    # deterministic order by id
    return sorted((c for _, c in best.values()), key=lambda c: c.id)
