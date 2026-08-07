"""Minimal configuration constants for the mining core.

Deliberately tiny: the library is a pure function of its inputs (an EPUB path, a set of
known lemmas, a ``SelectionConfig``) and holds no application/filesystem policy. Host
applications own paths, databases, and enrichment — see the consumers in
``calibre-to-anki-conversion`` and the typing platform's backend.
"""

from __future__ import annotations

#: spaCy Spanish model — NOT a PyPI dependency; install with
#: ``python -m spacy download es_core_news_md``. Overridable by callers that load their
#: own pipeline and pass it into ``select_candidates``/``analyze_paragraph``.
SPACY_MODEL = "es_core_news_md"
