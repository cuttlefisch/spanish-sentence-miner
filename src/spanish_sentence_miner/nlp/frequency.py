"""External Spanish word-frequency banding via the ``wordfreq`` library.

``zipf_frequency`` returns a Zipf value roughly in [0, 8]: higher = more common
("el" ~7.9, a rare technical term <2). We bucket it into coarse bands used both to
grade card difficulty and to drive the enrichment model-dispatch convention.
"""

from __future__ import annotations

from wordfreq import zipf_frequency

# Ordered from most to least common. The band name is the stable contract value.
BANDS = ("very_common", "common", "mid", "rare", "very_rare")


def zipf_for(word: str) -> float:
    """Zipf frequency of a Spanish word (0.0 if unknown)."""
    return zipf_frequency(word.lower(), "es")


def band_for_zipf(zipf: float) -> str:
    """Map a Zipf value to a coarse frequency band."""
    if zipf >= 5.5:
        return "very_common"
    if zipf >= 4.5:
        return "common"
    if zipf >= 3.5:
        return "mid"
    if zipf >= 2.5:
        return "rare"
    return "very_rare"


def band_for_word(word: str) -> tuple[float, str]:
    """Convenience: return ``(zipf, band)`` for a word."""
    z = zipf_for(word)
    return z, band_for_zipf(z)
