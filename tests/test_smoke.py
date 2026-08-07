"""Smoke tests for the mining-core public surface.

Deliberately dependency-light: these cover the pure-Python contract (ids, banding, the
Candidate/EnrichedItem schema round-trip) and need neither a spaCy model nor network.
spaCy-dependent behaviour (extraction, selection, morphology) is exercised by the host
applications' integration tests against fixture EPUBs.
"""

from __future__ import annotations

from pathlib import Path

from spanish_sentence_miner import (
    Candidate,
    EnrichedItem,
    GrammarInfo,
    band_for_zipf,
    load_candidates,
    load_enriched,
    make_id,
    write_jsonl,
)


def test_make_id_is_zero_padded_and_stable() -> None:
    assert make_id(355, 7, 142) == "355:0007:0142"
    assert make_id(1, 0, 0) == "1:0000:0000"


def test_band_for_zipf_bounds() -> None:
    assert band_for_zipf(7.9) == "very_common"
    assert band_for_zipf(5.0) == "common"
    assert band_for_zipf(4.0) == "mid"
    assert band_for_zipf(3.0) == "rare"
    assert band_for_zipf(1.2) == "very_rare"


def _candidate(cid: str = "1:0000:0000") -> Candidate:
    return Candidate(
        id=cid,
        book_id=1,
        book_title="Libro",
        sentence="Ella comió una manzana.",
        target_lemma="comer",
        target_surface="comió",
        token_index=5,
        char_start=5,
        char_end=10,
        local_freq=3,
        external_zipf=4.1,
        external_band="mid",
        difficulty_hint="medium",
        pos="VERB",
        grammar=GrammarInfo(kind="verb", infinitive="comer", tense="preterite", label="preterite"),
    )


def test_candidate_jsonl_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "candidates.jsonl"
    assert write_jsonl(path, [_candidate("1:0000:0000"), _candidate("1:0000:0001")]) == 2
    loaded = load_candidates(path)
    assert set(loaded) == {"1:0000:0000", "1:0000:0001"}
    assert loaded["1:0000:0000"].grammar.tense == "preterite"


def test_enriched_jsonl_roundtrip_skips_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "enriched.jsonl"
    write_jsonl(path, [EnrichedItem(id="1:0000:0000", english_gloss="to eat")])
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ not valid json\n")
    items, bad = load_enriched(path)
    assert bad == 1
    assert items["1:0000:0000"].english_gloss == "to eat"
