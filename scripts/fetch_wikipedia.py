"""Fetch a revision-aware Wikipedia corpus from a versioned page manifest.

The script runs only at ingestion time. It writes one JSON record per article;
the normal DocsMind loader later converts article sections into Documents.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag
import httpx


API_URL = "https://en.wikipedia.org/w/api.php"
DEFAULT_MANIFEST = Path("data/wikipedia/volkswagen_pages.v1.json")
DEFAULT_OUTPUT = Path("data/wikipedia/volkswagen.wikipedia.jsonl")
DEFAULT_USER_AGENT = (
    "DocsMind/0.1 (https://github.com/ajmalrasi/docsmind) httpx"
)
LICENSE = "CC BY-SA 4.0"

_SPACE_RE = re.compile(r"\s+")
_EDIT_RE = re.compile(r"\s*\[edit\]\s*$", re.IGNORECASE)
_TEMPLATE_ARTIFACT_RE = re.compile(r"\{\{.*?\}\}")
_CONTENT_TAGS = {"p", "ul", "ol", "table"}
_EXCLUDED_SECTION_ROOTS = {
    "bibliography",
    "external links",
    "further reading",
    "references",
    "see also",
    "sources",
}


def _clean_text(value: str) -> str:
    without_template_artifacts = _TEMPLATE_ARTIFACT_RE.sub("", value)
    return _SPACE_RE.sub(" ", without_template_artifacts).strip()


def _table_text(table: Tag) -> str:
    rows: list[str] = []
    for row in table.find_all("tr"):
        cells = [
            _clean_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _element_text(element: Tag) -> str:
    if element.name == "table":
        return _table_text(element)
    if element.name in {"ul", "ol"}:
        items = [
            _clean_text(item.get_text(" ", strip=True))
            for item in element.find_all("li", recursive=False)
        ]
        return "\n".join(f"- {item}" for item in items if item)
    return _clean_text(element.get_text(" ", strip=True))


def wikipedia_html_to_sections(html: str) -> list[dict[str, str]]:
    """Normalize MediaWiki HTML into heading-aware text sections.

    Tables are retained as pipe-delimited rows because vehicle/platform/engine
    facts often live in infoboxes and specification tables.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup

    for selector in (
        "script",
        "style",
        "sup.reference",
        ".mw-editsection",
        ".reflist",
        ".references",
        ".navbox",
        ".vertical-navbox",
        ".authority-control",
        ".sistersitebox",
        ".shortdescription",
        ".noprint",
    ):
        for element in root.select(selector):
            element.decompose()

    sections: list[dict[str, str]] = []
    heading_path: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(part for part in buffer if part).strip()
        if text:
            sections.append(
                {
                    "title": " > ".join(heading_path) if heading_path else "Lead",
                    "text": text,
                }
            )
        buffer.clear()

    for element in root.find_all(["h2", "h3", "h4", "h5", "h6", *_CONTENT_TAGS]):
        if not isinstance(element, Tag):
            continue
        if element.name.startswith("h"):
            flush()
            level = int(element.name[1]) - 2
            heading = _EDIT_RE.sub("", _clean_text(element.get_text(" ", strip=True)))
            heading_path[level:] = [heading]
            continue

        # A paragraph/list nested inside a list or table would duplicate text
        # already emitted by its outer element.
        if element.find_parent(list(_CONTENT_TAGS)) is not None:
            continue
        text = _element_text(element)
        if text:
            buffer.append(text)

    flush()
    return [
        section
        for section in sections
        if section["title"].split(" > ", 1)[0].casefold()
        not in _EXCLUDED_SECTION_ROOTS
    ]


def _request_json(
    client: httpx.Client,
    params: dict[str, str],
    *,
    max_retries: int,
) -> dict:
    for attempt in range(max_retries + 1):
        response = client.get(API_URL, params=params)
        if response.status_code not in {429, 503}:
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                error = payload["error"]
                raise RuntimeError(
                    f"MediaWiki API error {error.get('code')}: {error.get('info')}"
                )
            return payload
        if attempt == max_retries:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else min(2**attempt, 30)
        time.sleep(delay)
    raise AssertionError("unreachable")


def fetch_wikipedia_page(
    client: httpx.Client,
    requested_title: str,
    *,
    language: str,
    max_retries: int = 4,
) -> dict:
    payload = _request_json(
        client,
        {
            "action": "parse",
            "page": requested_title,
            "prop": "text|revid|displaytitle",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
        },
        max_retries=max_retries,
    )
    parsed = payload["parse"]
    title = str(parsed["title"])
    html = str(parsed["text"])
    page_id = int(parsed["pageid"])
    revision_id = int(parsed["revid"])
    source_url = (
        f"https://{language}.wikipedia.org/wiki/"
        f"{quote(title.replace(' ', '_'), safe='()_-')}"
    )
    sections = wikipedia_html_to_sections(html)
    if not sections:
        raise RuntimeError(f"Wikipedia page produced no usable text: {requested_title}")

    return {
        "id": f"{language}wiki:{page_id}:{revision_id}",
        "requested_title": requested_title,
        "title": title,
        "page_id": page_id,
        "revision_id": revision_id,
        "source_url": source_url,
        "language": language,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "sections": sections,
    }


def load_manifest(path: Path) -> tuple[str, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    language = str(payload.get("language", "en"))
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError(f"Manifest must contain a non-empty pages list: {path}")
    titles = [str(title).strip() for title in pages]
    if any(not title for title in titles):
        raise ValueError(f"Manifest contains a blank page title: {path}")
    if len(titles) != len(set(titles)):
        raise ValueError(f"Manifest contains duplicate page titles: {path}")
    return language, titles


def validate_unique_records(records: list[dict]) -> None:
    """Reject manifests whose seed titles resolve to the same article."""
    requested_by_page: dict[int, str] = {}
    for record in records:
        page_id = int(record["page_id"])
        previous = requested_by_page.get(page_id)
        if previous is not None:
            raise ValueError(
                "Wikipedia seeds resolve to the same canonical page: "
                f"{previous!r} and {record['requested_title']!r}"
            )
        requested_by_page[page_id] = str(record["requested_title"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay-seconds", type=float, default=0.4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("WIKIMEDIA_USER_AGENT", DEFAULT_USER_AGENT),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    language, titles = load_manifest(args.manifest)
    if language != "en":
        raise ValueError("This fetcher currently targets the English Wikipedia API")
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        titles = titles[: args.limit]

    records: list[dict] = []
    with httpx.Client(
        headers={"User-Agent": args.user_agent},
        timeout=args.timeout_seconds,
        follow_redirects=True,
    ) as client:
        for index, title in enumerate(titles, start=1):
            print(f"[{index}/{len(titles)}] {title}")
            records.append(
                fetch_wikipedia_page(client, title, language=language)
            )
            if index < len(titles):
                time.sleep(args.delay_seconds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    validate_unique_records(records)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    temporary.replace(args.output)

    section_count = sum(len(record["sections"]) for record in records)
    text_chars = sum(
        len(section["text"])
        for record in records
        for section in record["sections"]
    )
    print(
        f"Wrote {len(records)} articles / {section_count} sections / "
        f"{text_chars:,} text characters to {args.output}"
    )


if __name__ == "__main__":
    main()
