from __future__ import annotations

import json
from datetime import datetime

from state_manager import ROOT_DIR, ensure_dirs


NEWS_PATH = ROOT_DIR / "output" / "news_items.json"
SCRIPT_PATH = ROOT_DIR / "output" / "script.json"


def roman_urdu_line(story: dict, index: int) -> str:
    title = story["title"].rstrip(".")
    source = story.get("source", "source")
    summary = story.get("summary") or "Is khabar ki tafseel source link par mojood hai."
    clean_summary = summary.replace("\n", " ").strip()
    return (
        f"Khabar number {index}. {title}. "
        f"{source} ke mutabiq, {clean_summary[:260]}. "
        "Yeh artificial intelligence ki duniya mein aik ahem update hai."
    )


def main() -> None:
    ensure_dirs()
    with NEWS_PATH.open("r", encoding="utf-8") as handle:
        stories = json.load(handle)

    segments = []
    for idx, story in enumerate(stories, start=1):
        reporter = "A" if idx % 2 else "B"
        segments.append(
            {
                "index": idx,
                "reporter": reporter,
                "headline": story["title"],
                "source": story["source"],
                "published_at": story["published_at"],
                "story_id": story["id"],
                "link": story["link"],
                "text": roman_urdu_line(story, idx),
            }
        )

    script = {
        "title": f"AI News Update | Latest Artificial Intelligence News | {datetime.utcnow():%Y-%m-%d}",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "language": "Roman Urdu",
        "segments": segments,
    }

    with SCRIPT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(script, handle, indent=2, ensure_ascii=False)

    print(f"Saved script with {len(segments)} segments to {SCRIPT_PATH}")


if __name__ == "__main__":
    main()
