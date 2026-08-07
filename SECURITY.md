# Security Policy

## Supported versions
The latest released `0.x` line receives fixes. Pre-1.0: APIs may change between minor versions.

## Reporting a vulnerability
Please report privately via GitHub Security Advisories
("Report a vulnerability" on the repo's **Security** tab) rather than a public issue.
Expect an initial response within a few days.

## Scope notes
This library parses **user-supplied EPUB files** with `ebooklib`/`lxml`/BeautifulSoup and runs
a spaCy pipeline. Treat untrusted EPUBs as untrusted input. It performs no network I/O and
stores no credentials.
