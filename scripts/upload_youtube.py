from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from state_manager import ROOT_DIR, mark_uploaded


VIDEO_PATH = ROOT_DIR / "output" / "final_video.mp4"
NEWS_PATH = ROOT_DIR / "output" / "news_items.json"
SCRIPT_PATH = ROOT_DIR / "output" / "script.json"


def write_secret_file(name: str, content: str | None) -> Path | None:
    if not content:
        return None
    path = ROOT_DIR / "output" / name
    path.write_text(content, encoding="utf-8")
    return path


def build_description(stories: list[dict]) -> str:
    lines = [
        "Latest AI news update in Roman Urdu.",
        "",
        "Sources:",
    ]
    for idx, story in enumerate(stories, start=1):
        lines.append(f"{idx}. {story['title']} - {story['source']} - {story['link']}")
    return "\n".join(lines)


def main() -> None:
    with NEWS_PATH.open("r", encoding="utf-8") as handle:
        stories = json.load(handle)
    with SCRIPT_PATH.open("r", encoding="utf-8") as handle:
        script = json.load(handle)

    client_json = os.getenv("YOUTUBE_CLIENT_SECRETS_JSON")
    token_json = os.getenv("YOUTUBE_TOKEN_JSON")
    if not client_json or not token_json:
        print("YouTube credentials missing. Skipping upload and marking stories as used after MP4 generation.")
        mark_uploaded(stories, video_id=None)
        return

    token_path = write_secret_file("youtube_token.json", token_json)
    credentials = Credentials.from_authorized_user_file(str(token_path), scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": script["title"],
            "description": build_description(stories),
            "tags": [
                "AI News",
                "Artificial Intelligence",
                "OpenAI",
                "Google AI",
                "Tech News",
                "Urdu AI News",
                "Roman Urdu News",
            ],
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(VIDEO_PATH), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    print(f"Uploaded YouTube video ID: {video_id}")
    mark_uploaded(stories, video_id=video_id)


if __name__ == "__main__":
    main()
