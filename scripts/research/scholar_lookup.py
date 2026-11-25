#!/usr/bin/env python3
"""Look up scholarly works through open APIs and print research-team source records.

Bibliographic fields come from the registries, not from a model's memory.
A record from here is metadata (plus an abstract when the registry has one):
it does not count as having read the paper, so `fetched` stays false.

Usage:
    python3 scripts/research/scholar_lookup.py search "<query>" [--source openalex|crossref|jstage] [--rows 5]
    python3 scripts/research/scholar_lookup.py doi <doi>

No API key and no contact details are sent. Rules: .github/skills/research-team/SKILL.md
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "research-team-lookup/1.0"
TIMEOUT = 30
ABSTRACT_LIMIT = 1500
OPENALEX_FIELDS = "id,doi,title,publication_year,type,open_access,authorships,primary_location,abstract_inverted_index"
CROSSREF_FIELDS = "DOI,title,author,issued,container-title,type,abstract,URL"
TYPES = {
    "article": "paper", "journal-article": "paper", "review": "paper", "proceedings-article": "paper",
    "preprint": "preprint", "posted-content": "preprint",
    "book": "book", "book-chapter": "book", "monograph": "book", "edited-book": "book",
    "report": "report", "dataset": "data",
}
ATOM = "{http://www.w3.org/2005/Atom}"
PRISM = "{http://prismstandard.org/namespaces/basic/2.0/}"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def clean_doi(value: object) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", str(value or "").strip(), flags=re.I)


def record(**fields: object) -> dict:
    doi = clean_doi(fields.get("doi"))
    out = {
        "type": fields.get("type") or "paper",
        "title": " ".join(str(fields.get("title") or "").split()),
        "authors": [a for a in fields.get("authors") or [] if a],
        "year": fields.get("year"),
        "venue": fields.get("venue") or "",
        "doi": doi,
        "url": fields.get("url") or (f"https://doi.org/{doi}" if doi else ""),
        "fetched": False,
        "registry": fields.get("registry"),
    }
    if fields.get("oa_url"):
        out["oa_url"] = fields["oa_url"]
    if fields.get("abstract"):
        text = str(fields["abstract"])
        out["abstract"] = text if len(text) <= ABSTRACT_LIMIT else text[:ABSTRACT_LIMIT].rstrip() + "…"
    return out


def openalex_abstract(index: object) -> str:
    if not isinstance(index, dict):
        return ""
    words = sorted((pos, word) for word, positions in index.items() for pos in positions)
    return " ".join(word for _, word in words)


def from_openalex(work: dict) -> dict:
    location = work.get("primary_location") or {}
    access = work.get("open_access") or {}
    return record(
        type=TYPES.get(str(work.get("type")), "paper"),
        title=work.get("title"),
        authors=[(a.get("author") or {}).get("display_name") for a in work.get("authorships") or []],
        year=work.get("publication_year"),
        venue=(location.get("source") or {}).get("display_name"),
        doi=work.get("doi"),
        url=location.get("landing_page_url") or work.get("id"),
        oa_url=access.get("oa_url"),
        abstract=openalex_abstract(work.get("abstract_inverted_index")),
        registry="openalex",
    )


def from_crossref(work: dict) -> dict:
    authors = [", ".join(p for p in (a.get("family"), a.get("given")) if p) or a.get("name") for a in work.get("author") or []]
    parts = ((work.get("issued") or {}).get("date-parts") or [[None]])[0]
    abstract = html.unescape(re.sub(r"<[^>]+>", " ", str(work.get("abstract") or "")))
    return record(
        type=TYPES.get(str(work.get("type")), "paper"),
        title=(work.get("title") or [""])[0],
        authors=authors,
        year=parts[0] if parts else None,
        venue=(work.get("container-title") or [""])[0],
        doi=work.get("DOI"),
        url=work.get("URL"),
        abstract=" ".join(abstract.split()),
        registry="crossref",
    )


def _lang(node: ET.Element | None, tag: str = "") -> str:
    """J-STAGE wraps values in <ja>/<en>; prefer Japanese, fall back to English."""
    if node is None:
        return ""
    for lang in ("ja", "en"):
        child = node.find(lang)
        if child is not None:
            target = child.find(tag) if tag else child
            if target is not None and (target.text or "").strip():
                return target.text.strip()
    return ""


def from_jstage(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    out = []
    for entry in root.iter(f"{ATOM}entry"):
        authors = []
        author = entry.find(f"{ATOM}author")
        if author is not None:
            block = author.find(f"{ATOM}ja") if author.find(f"{ATOM}ja") is not None else author.find(f"{ATOM}en")
            if block is not None:
                authors = [(n.text or "").strip() for n in block.findall(f"{ATOM}name")]
        year = (entry.findtext(f"{ATOM}pubyear") or "").strip()
        out.append(
            record(
                title=_lang(_strip(entry.find(f"{ATOM}article_title"))) or entry.findtext(f"{ATOM}title"),
                authors=authors,
                year=int(year) if year.isdigit() else None,
                venue=_lang(_strip(entry.find(f"{ATOM}material_title"))),
                doi=entry.findtext(f"{PRISM}doi"),
                url=_lang(_strip(entry.find(f"{ATOM}article_link"))),
                registry="jstage",
            )
        )
    return out


def _strip(node: ET.Element | None) -> ET.Element | None:
    """Drop the Atom namespace from a small subtree so <ja>/<en> lookups stay simple."""
    if node is None:
        return None
    for item in node.iter():
        item.tag = item.tag.split("}", 1)[-1]
    return node


def search(query: str, source: str, rows: int) -> list[dict]:
    q = urllib.parse.quote(query)
    if source == "openalex":
        data = json.loads(fetch(f"https://api.openalex.org/works?search={q}&per-page={rows}&select={OPENALEX_FIELDS}"))
        return [from_openalex(w) for w in data.get("results") or []]
    if source == "crossref":
        data = json.loads(fetch(f"https://api.crossref.org/works?query.bibliographic={q}&rows={rows}&select={CROSSREF_FIELDS}"))
        return [from_crossref(w) for w in (data.get("message") or {}).get("items") or []]
    if source == "jstage":
        return from_jstage(fetch(f"https://api.jstage.jst.go.jp/searchapi/do?service=3&text={q}&count={rows}"))
    raise SystemExit(f"unknown source: {source}")


def by_doi(doi: str) -> list[dict]:
    doi = clean_doi(doi)
    path = urllib.parse.quote(doi, safe="/")
    found = []
    for url, parse in (
        (f"https://api.openalex.org/works/doi:{path}?select={OPENALEX_FIELDS}", lambda b: from_openalex(json.loads(b))),
        (f"https://api.crossref.org/works/{path}", lambda b: from_crossref(json.loads(b).get("message") or {})),
    ):
        try:
            found.append(parse(fetch(url)))
        except Exception as error:  # one registry missing a DOI is normal; report and keep going
            print(f"warning: {url.split('/')[2]}: {error}", file=sys.stderr)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("search")
    cmd.add_argument("query")
    cmd.add_argument("--source", choices=("openalex", "crossref", "jstage"), default="openalex")
    cmd.add_argument("--rows", type=int, default=5)
    cmd = sub.add_parser("doi")
    cmd.add_argument("doi")
    args = parser.parse_args(argv)
    try:
        results = search(args.query, args.source, max(1, min(args.rows, 25))) if args.command == "search" else by_doi(args.doi)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
