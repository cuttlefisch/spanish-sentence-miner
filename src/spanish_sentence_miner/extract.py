"""Chapter-aware EPUB text extraction with ebooklib + BeautifulSoup.

We iterate the EPUB's document spine, drop front/back-matter (cover, TOC, copyright,
index, glossary, appendices…), surgically remove footnotes/tables/superscripts, and
emit clean prose paragraphs. Plain ``ebook-convert`` collapses everything into one
blob with no way to skip matter by role — hence the manual pass.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import ebooklib
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub

# We deliberately parse XHTML with the lenient HTML parser (better entity handling);
# silence bs4's advisory that the input looked like XML.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Document filenames / ids that signal non-prose matter we should skip entirely.
# Matter-detection by filename. NOTE: deliberately does NOT include bare "index" —
# Calibre routinely names *main content* index.html / index_split_NNN.html, so matching
# "index" drops whole books. Real indexes/TOCs are caught by epub:type + <nav> stripping.
_MATTER_NAME = re.compile(
    r"cover|titlepage|\btoc\b|contents|copyright|colophon|imprint|"
    r"acknowledg|dedicat|glossary|appendix|biblio|"
    r"cubierta|portada|creditos|créditos|"
    r"agradecim|glosario|apendice|apéndice|nota[s]?_",
    re.IGNORECASE,
)

# epub:type values (on <section>/<nav>/<aside>) that mark matter or notes.
_MATTER_EPUB_TYPE = {
    "cover", "frontmatter", "backmatter", "toc", "landmarks", "copyright-page",
    "titlepage", "index", "glossary", "appendix", "acknowledgments", "dedication",
    "colophon", "bibliography",
}
_NOTE_EPUB_TYPE = {"footnote", "footnotes", "endnote", "endnotes", "rearnote", "noteref", "note"}

# class / id substrings that mark footnotes, TOC scaffolding, etc.
_STRIP_CLASS = re.compile(
    r"footnote|foot-note|\bnota\b|\bnotas\b|endnote|calibre_toc|toc|index", re.I
)

_SOFT_HYPHEN = "­"
_WS = re.compile(r"\s+")
_HYPHEN_BREAK = re.compile(r"(\w)-\s+(\w)")  # word-broken across a line


@dataclass
class Chapter:
    index: int
    name: str
    paragraphs: list[str]


@dataclass
class ExtractedBook:
    book_id: int
    title: str
    authors: str
    chapters: list[Chapter]

    @property
    def paragraph_count(self) -> int:
        return sum(len(c.paragraphs) for c in self.chapters)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedBook:
        return cls(
            book_id=data["book_id"],
            title=data["title"],
            authors=data["authors"],
            chapters=[Chapter(**c) for c in data["chapters"]],
        )


def _clean_text(text: str) -> str:
    text = text.replace(_SOFT_HYPHEN, "")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _WS.sub(" ", text).strip()
    return unicodedata.normalize("NFC", text)


def _epub_types(el) -> set[str]:  # type: ignore[no-untyped-def]
    """Lowercased epub:type tokens of an element, robust to elements with no attrs."""
    attrs = getattr(el, "attrs", None) or {}
    return set(str(attrs.get("epub:type", "")).lower().split())


def _is_matter(item: epub.EpubHtml, soup: BeautifulSoup) -> bool:
    """True if this document is front/back matter we should skip wholesale."""
    if _MATTER_NAME.search(item.get_name() or ""):
        return True
    for el in soup.find_all(attrs={"epub:type": True}):
        if _MATTER_EPUB_TYPE.intersection(_epub_types(el)):
            return True
    return False


def _strip_noise(soup: BeautifulSoup) -> None:
    """Remove footnotes, superscripts, tables, figures, and TOC/index scaffolding."""
    for tag in soup.find_all(["sup", "table", "figure", "figcaption", "nav"]):
        tag.decompose()
    for el in soup.find_all(attrs={"epub:type": True}):
        if _NOTE_EPUB_TYPE.intersection(_epub_types(el)):
            el.decompose()
    for el in soup.find_all(attrs={"class": _STRIP_CLASS}):
        el.decompose()
    for el in soup.find_all(id=_STRIP_CLASS):
        el.decompose()


def _paragraphs(soup: BeautifulSoup) -> list[str]:
    """Extract prose paragraphs, preferring <p>; fall back to body block text."""
    nodes = soup.find_all("p")
    if not nodes:
        body = soup.body or soup
        raw = body.get_text(separator="\n")
        candidates = [line for line in raw.split("\n")]
    else:
        candidates = [p.get_text(separator=" ") for p in nodes]
    out = []
    for c in candidates:
        cleaned = _clean_text(c)
        if cleaned:
            out.append(cleaned)
    return out


def _spine_documents(book: epub.EpubBook):  # type: ignore[no-untyped-def]
    """Yield document items in SPINE (reading) order, not manifest order.

    ``get_items_of_type`` returns manifest order, which for many EPUBs scrambles the
    chapters (e.g. this library's El Hobbit). The spine defines the real reading order;
    aligning to a counterpart translation is meaningless without it.
    """
    seen: set[str] = set()
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, (tuple, list)) else entry
        item = book.get_item_with_id(idref)
        if item is not None and item.get_type() == ebooklib.ITEM_DOCUMENT:
            seen.add(item.get_id())
            yield item
    # fallback: any documents not referenced by the spine, in manifest order
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        if item.get_id() not in seen:
            yield item


def extract_book(
    *, book_id: int, title: str, authors: str, epub_path: Path
) -> ExtractedBook:
    """Read an EPUB and return cleaned, matter-filtered chapters of prose paragraphs."""
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB not found: {epub_path}")
    # An EPUB is a zip; validate the magic bytes so a PDF/MOBI/KEPUB gives a clear error
    # instead of a cryptic ebooklib parse failure deep in the pipeline.
    with epub_path.open("rb") as fh:
        if fh.read(2) != b"PK":
            raise ValueError(
                f"{epub_path} is not a valid EPUB (missing zip signature). "
                "Only EPUB is supported — convert PDF/MOBI/KEPUB in Calibre first."
            )

    book = epub.read_epub(str(epub_path), options={"ignore_ncx": True})
    chapters: list[Chapter] = []
    index = 0
    for item in _spine_documents(book):
        soup = BeautifulSoup(item.get_content(), "lxml")
        if _is_matter(item, soup):
            continue
        _strip_noise(soup)
        paras = _paragraphs(soup)
        if not paras:
            continue
        name = item.get_name() or f"doc{index}"
        chapters.append(Chapter(index=index, name=name, paragraphs=paras))
        index += 1

    return ExtractedBook(book_id=book_id, title=title, authors=authors, chapters=chapters)
