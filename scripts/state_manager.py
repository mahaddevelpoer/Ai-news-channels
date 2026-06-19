from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
STATE_PATH = DATA_DIR / "uploaded_news.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT_DIR / "output").mkdir(parents=True, exist_ok=True)


def story_id(url: str, title: str = "") -> str:
    key = (url or title).strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def load_state() -> dict:
    ensure_dirs()
    if not STATE_PATH.exists():
        return {"used_story_ids": [], "videos": []}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"used_story_ids": [], "videos": []}

    state.setdefault("used_story_ids", [])
    state.setdefault("videos", [])
    return state


def save_state(state: dict) -> None:
    ensure_dirs()
    with STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)


def used_ids() -> set[str]:
    return set(load_state().get("used_story_ids", []))


def mark_uploaded(stories: Iterable[dict], video_id: str | None = None) -> None:
    state = load_state()
    existing = set(state.get("used_story_ids", []))
    story_ids = []
    for story in stories:
        sid = story.get("id") or story_id(story.get("link", ""), story.get("title", ""))
        story_ids.append(sid)
        existing.add(sid)

    state["used_story_ids"] = sorted(existing)
    state.setdefault("videos", []).append(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "video_id": video_id,
            "story_ids": story_ids,
        }
    )
    save_state(state)
