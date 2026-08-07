"""The known-words store: lemmas already studied, suppressed, or ignored.

Backed by a small SQLite DB so re-running the pipeline on more books never re-mines
vocabulary you've already got. Any lemma present in the store — whatever its status —
is excluded from future mining.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS known_words (
    lemma     TEXT PRIMARY KEY,
    status    TEXT NOT NULL,          -- 'studied' | 'suppressed' | 'ignored'
    added_utc TEXT NOT NULL,
    source    TEXT                     -- book title/id or 'manual'
);
"""

VALID_STATUSES = ("studied", "suppressed", "ignored")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class KnownStore:
    """A connection to the known-words SQLite DB. Use as a context manager."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def __enter__(self) -> KnownStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def known_lemmas(self) -> set[str]:
        """All lemmas in the store, regardless of status."""
        rows = self._conn.execute("SELECT lemma FROM known_words").fetchall()
        return {r[0] for r in rows}

    def add(self, lemmas: Iterable[str], *, status: str = "studied", source: str = "manual") -> int:
        """Upsert lemmas with the given status. Returns the number of rows written."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; expected one of {VALID_STATUSES}")
        now = _now()
        rows = [(lemma.lower(), status, now, source) for lemma in lemmas]
        with self._conn:  # single transaction
            self._conn.executemany(
                "INSERT INTO known_words (lemma, status, added_utc, source) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(lemma) DO UPDATE SET status=excluded.status, "
                "added_utc=excluded.added_utc, source=excluded.source",
                rows,
            )
        return len(rows)

    def list_all(self) -> list[tuple[str, str, str, str]]:
        """Return (lemma, status, added_utc, source) rows, ordered by lemma."""
        return self._conn.execute(
            "SELECT lemma, status, added_utc, source FROM known_words ORDER BY lemma"
        ).fetchall()

    def import_file(self, path: Path, *, status: str = "suppressed") -> int:
        """Import a plain wordlist (one lemma per line, '#' comments allowed)."""
        lemmas = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        return self.add(lemmas, status=status, source=f"import:{path.name}")
