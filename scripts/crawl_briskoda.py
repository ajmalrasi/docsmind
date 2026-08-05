"""Resumably crawl one public BRISKODA forum into post-level JSONL.

The crawler uses a real Chromium browser because BRISKODA returns a Cloudflare
challenge to plain HTTP clients. It never attempts to solve a challenge: if one
appears, the run stops with all completed pages safely checkpointed.

Example:
    python -m scripts.crawl_briskoda \
      --output ~/data/docsmind/briskoda/superb_mk3.briskoda.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

FORUM_URL = (
    "https://www.briskoda.net/forums/forum/"
    "299-skoda-superb-mk3-2015-2023/"
)
TOPIC_RE = re.compile(r"^(https://www\.briskoda\.net/forums/topic/(\d+)-[^/?#]+/)")
PAGE_RE = re.compile(r"/page/(\d+)/")


def normalize_topic_url(url: str) -> tuple[str, str] | None:
    """Return the canonical topic root URL and numeric topic ID."""
    clean = urlunsplit((*urlsplit(url)[:3], "", ""))
    if not clean.endswith("/"):
        clean += "/"
    match = TOPIC_RE.match(clean)
    if not match:
        return None
    return match.group(1), match.group(2)


def max_page_from_urls(urls: list[str]) -> int:
    pages = [int(match.group(1)) for url in urls if (match := PAGE_RE.search(url))]
    return max(pages, default=1)


def page_url(root_url: str, page_number: int) -> str:
    return root_url if page_number == 1 else f"{root_url}page/{page_number}/"


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(path)


def load_existing_posts(path: Path) -> tuple[set[str], dict[str, int]]:
    post_ids: set[str] = set()
    topic_counts: dict[str, int] = {}
    if not path.exists():
        return post_ids, topic_counts
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}") from exc
            post_id = str(record["post_id"])
            topic_id = str(record["topic_id"])
            post_ids.add(post_id)
            topic_counts[topic_id] = max(
                topic_counts.get(topic_id, 0), int(record["post_number"])
            )
    return post_ids, topic_counts


class ChallengeDetected(RuntimeError):
    pass


class BriskodaCrawler:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.output = args.output.expanduser().resolve()
        self.state_path = (
            args.state.expanduser().resolve()
            if args.state
            else self.output.with_suffix(self.output.suffix + ".state.json")
        )
        self.state = load_json(
            self.state_path,
            {
                "forum_url": args.forum_url,
                "forum_pages_done": [],
                "forum_max_page": None,
                "discovery_complete": False,
                "topics": {},
            },
        )
        self.post_ids, self.topic_counts = load_existing_posts(self.output)
        self.page: Any = None

    async def pause(self) -> None:
        await asyncio.sleep(random.uniform(self.args.delay_min, self.args.delay_max))

    async def navigate(self, url: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.args.retries + 1):
            try:
                response = await self.page.goto(
                    url, wait_until="domcontentloaded", timeout=self.args.timeout * 1000
                )
                title = await self.page.title()
                html = await self.page.content()
                status = response.status if response else None
                if (
                    title.strip().lower() == "just a moment..."
                    or "cf-chl-" in html
                    or "challenges.cloudflare.com" in html
                ):
                    # Give Cloudflare's ordinary JavaScript browser check time to
                    # finish. We never click, solve, or otherwise evade a challenge.
                    try:
                        await self.page.wait_for_function(
                            "document.title.trim().toLowerCase() !== 'just a moment...'",
                            timeout=self.args.challenge_wait * 1000,
                        )
                    except Exception as exc:
                        raise ChallengeDetected(
                            f"Cloudflare challenge at {url}; checkpoint saved"
                        ) from exc
                    html = await self.page.content()
                    if "cf-chl-" in html or "challenges.cloudflare.com" in html:
                        raise ChallengeDetected(
                            f"Cloudflare challenge at {url}; checkpoint saved"
                        )
                if status is not None and status >= 400:
                    raise RuntimeError(f"HTTP {status} for {url}")
                return
            except ChallengeDetected:
                raise
            except Exception as exc:  # Playwright exposes several transient types.
                last_error = exc
                print(f"retry {attempt}/{self.args.retries}: {url}: {exc}", flush=True)
                if "Page crashed" in str(exc) or self.page.is_closed():
                    # A very long crawl can eventually exhaust a renderer. The
                    # persistent browser context remains valid, so replace only
                    # the failed tab and continue from the page checkpoint.
                    context = self.page.context
                    try:
                        if not self.page.is_closed():
                            await self.page.close()
                    except Exception:
                        pass
                    self.page = await context.new_page()
                await asyncio.sleep(min(30, 2**attempt))
        raise RuntimeError(f"Failed after retries: {url}: {last_error}")

    async def discover_topics(self) -> None:
        done = {int(value) for value in self.state["forum_pages_done"]}
        if self.state["forum_max_page"] is None:
            await self.navigate(self.args.forum_url)
            links = await self.page.eval_on_selector_all(
                "a[href*='/page/']", "els => els.map(el => el.href)"
            )
            self.state["forum_max_page"] = max_page_from_urls(links)
            save_json(self.state_path, self.state)

        actual_max = int(self.state["forum_max_page"])
        run_max = min(actual_max, self.args.max_forum_pages or actual_max)
        print(f"discovering forum pages 1..{run_max} of {actual_max}", flush=True)

        for number in range(1, run_max + 1):
            if number in done:
                continue
            url = page_url(self.args.forum_url, number)
            await self.navigate(url)
            raw_topics = await self.page.eval_on_selector_all(
                "main h4 a[href*='/forums/topic/']",
                "els => els.map(el => ({url: el.href, title: el.textContent.trim()}))",
            )
            for raw in raw_topics:
                normalized = normalize_topic_url(raw["url"])
                if normalized is None:
                    continue
                topic_url, topic_id = normalized
                self.state["topics"].setdefault(
                    topic_url,
                    {
                        "topic_id": topic_id,
                        "topic_title": raw["title"],
                        "max_page": None,
                        "pages_done": [],
                    },
                )
            done.add(number)
            self.state["forum_pages_done"] = sorted(done)
            self.state["discovery_complete"] = (
                run_max == actual_max and len(done) >= actual_max
            )
            save_json(self.state_path, self.state)
            print(
                f"forum {number}/{run_max}: {len(self.state['topics'])} unique topics",
                flush=True,
            )
            await self.pause()

    async def extract_posts(
        self, topic_url: str, topic_id: str, page_number: int
    ) -> list[dict[str, Any]]:
        return await self.page.evaluate(
            """
            ({topicUrl, topicId, pageNumber}) => {
              const title = (document.querySelector('h1')?.textContent || '').trim();
              return Array.from(document.querySelectorAll("article[id^='elComment_']"))
                .map(article => {
                  const content = article.querySelector('.ipsRichText--user');
                  if (!content) return null;
                  const clean = content.cloneNode(true);
                  clean.querySelectorAll(
                    'blockquote, .ipsQuote, script, style, noscript, .ipsEmbeddedVideo'
                  ).forEach(node => node.remove());
                  const text = clean.textContent
                    .replace(/\\u00a0/g, ' ')
                    .replace(/[ \\t]+/g, ' ')
                    .replace(/\\n\\s*\\n\\s*\\n+/g, '\\n\\n')
                    .trim();
                  const postId = article.id.replace('elComment_', '');
                  const author = (
                    article.querySelector("h3 a[href*='/profile/']")?.textContent || ''
                  ).trim();
                  const postedAt = article.querySelector('time[datetime]')
                    ?.getAttribute('datetime') || '';
                  return {
                    topic_id: topicId,
                    topic_title: title,
                    topic_url: topicUrl,
                    post_id: postId,
                    post_url: `${location.origin}${location.pathname}#elComment_${postId}`,
                    author,
                    posted_at: postedAt,
                    page_number: pageNumber,
                    text,
                  };
                })
                .filter(record => record && record.post_id && record.text);
            }
            """,
            {"topicUrl": topic_url, "topicId": topic_id, "pageNumber": page_number},
        )

    async def crawl_topics(self) -> None:
        topics = list(self.state["topics"].items())
        if self.args.max_topics:
            topics = topics[: self.args.max_topics]
        self.output.parent.mkdir(parents=True, exist_ok=True)

        with self.output.open("a", encoding="utf-8") as handle:
            for topic_index, (topic_url, topic) in enumerate(topics, start=1):
                topic_id = str(topic["topic_id"])
                pages_done = {int(value) for value in topic["pages_done"]}

                if topic["max_page"] is None:
                    await self.navigate(topic_url)
                    links = await self.page.eval_on_selector_all(
                        "a[href*='/page/']", "els => els.map(el => el.href)"
                    )
                    topic["max_page"] = max_page_from_urls(links)
                    save_json(self.state_path, self.state)

                max_page = int(topic["max_page"])
                if len(pages_done) >= max_page:
                    continue

                for number in range(1, max_page + 1):
                    if number in pages_done:
                        continue
                    url = page_url(topic_url, number)
                    await self.navigate(url)
                    records = await self.extract_posts(topic_url, topic_id, number)
                    added = 0
                    for record in records:
                        if record["post_id"] in self.post_ids:
                            continue
                        self.topic_counts[topic_id] = self.topic_counts.get(topic_id, 0) + 1
                        record["post_number"] = self.topic_counts[topic_id]
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                        handle.flush()
                        self.post_ids.add(record["post_id"])
                        added += 1
                    pages_done.add(number)
                    topic["pages_done"] = sorted(pages_done)
                    topic["topic_title"] = (
                        records[0]["topic_title"] if records else topic["topic_title"]
                    )
                    save_json(self.state_path, self.state)
                    print(
                        f"topic {topic_index}/{len(topics)} page {number}/{max_page}: "
                        f"+{added} posts; total={len(self.post_ids)}",
                        flush=True,
                    )
                    await self.pause()

    async def run(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise SystemExit("Install crawler dependencies: pip install -e '.[crawl]'") from exc

        profile = self.args.profile.expanduser().resolve()
        profile.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(profile),
                executable_path=self.args.chrome_path,
                headless=not self.args.headful,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
                viewport={"width": 1440, "height": 1000},
            )
            await context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )
            self.page = context.pages[0] if context.pages else await context.new_page()
            try:
                await self.discover_topics()
                await self.crawl_topics()
            finally:
                await context.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forum-url", default=FORUM_URL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument(
        "--profile", type=Path, default=Path("data/crawl/briskoda_chrome")
    )
    parser.add_argument(
        "--chrome-path", default=shutil.which("google-chrome") or shutil.which("chromium")
    )
    parser.add_argument("--delay-min", type=float, default=2.5)
    parser.add_argument("--delay-max", type=float, default=4.5)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--challenge-wait", type=int, default=20)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-forum-pages", type=int)
    parser.add_argument("--max-topics", type=int)
    parser.add_argument("--headful", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.chrome_path:
        raise SystemExit("Chrome/Chromium not found; pass --chrome-path")
    if args.delay_min < 0 or args.delay_max < args.delay_min:
        raise SystemExit("Require 0 <= --delay-min <= --delay-max")
    crawler = BriskodaCrawler(args)
    try:
        asyncio.run(crawler.run())
    except ChallengeDetected as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
