from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from state_manager import ROOT_DIR, ensure_dirs, story_id, used_ids


FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://www.anthropic.com/news/rss.xml",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

OUTPUT_PATH = ROOT_DIR / "output" / "news_items.json"


def clean_text(value: str) -> str:
    value = " ".join((value or "").split())
    try:
        value = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        pass

    replacements = {
        "\u00e2\u20ac\u2122": "'",
        "\u00e2\u20ac\u0153": '"',
        "\u00e2\u20ac\u009d": '"',
        "\u00e2\u20ac\u201d": "-",
        "\u00e2\u20ac\u201c": "-",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return value


def parse_date(entry: dict) -> str:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, AttributeError):
            pass
    return datetime.now(timezone.utc).isoformat()


def normalize_entry(entry: dict, feed_title: str) -> dict:
    link = entry.get("link", "").strip()
    title = clean_text(entry.get("title", "Untitled AI story"))
    summary = clean_text(entry.get("summary", ""))
    sid = story_id(link, title)
    return {
        "id": sid,
        "title": title,
        "summary": summary[:500],
        "link": link,
        "source": clean_text(feed_title or "AI News"),
        "published_at": parse_date(entry),
    }


def main() -> None:
    ensure_dirs()
    seen = set()
    already_used = used_ids()
    stories: list[dict] = []
    fallback_stories: list[dict] = []

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        source = parsed.feed.get("title", feed_url)
        for entry in parsed.entries:
            item = normalize_entry(entry, source)
            if item["id"] not in {story["id"] for story in fallback_stories}:
                fallback_stories.append(item)
            if item["id"] in seen or item["id"] in already_used:
                continue
            seen.add(item["id"])
            stories.append(item)

    stories.sort(key=lambda item: item["published_at"], reverse=True)
    fallback_stories.sort(key=lambda item: item["published_at"], reverse=True)
    selected = stories[:10]

    if not selected:
        print("No fresh AI news items found. Reusing latest feed stories for continuous channel output.")
        selected = fallback_stories[:10]
    if not selected:
        raise RuntimeError("No AI news items found in configured RSS feeds.")

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(selected, handle, indent=2, ensure_ascii=False)

    print(f"Saved {len(selected)} fresh stories to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
