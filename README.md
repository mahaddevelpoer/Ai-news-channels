# Automated AI News Video Channel

This project fetches fresh AI news every hour, creates a Roman Urdu 3D TV-news style video in Blender, mixes voiceover and background music with FFmpeg, and optionally uploads the MP4 to YouTube.

The first version is intentionally simple and reliable for GitHub Actions. If no custom models or music are available, it uses generated low-poly reporters, a simple studio, and generated background music.

## What It Does

- Runs hourly with GitHub Actions and supports manual `workflow_dispatch`.
- Fetches the latest AI stories from RSS feeds.
- Selects up to 10 fresh stories that were not used before.
- Generates Roman Urdu presenter lines.
- Splits stories between Reporter A and Reporter B.
- Renders a 720p Eevee Blender studio video.
- Adds breaking news, headline, source, and date overlays.
- Creates TTS voiceover with a generated fallback if TTS fails.
- Lowers background music while reporters speak.
- Uploads to YouTube when credentials are configured.
- Saves uploaded or generated story IDs in `data/uploaded_news.json`.

## Project Structure

```text
.github/workflows/hourly-news.yml
scripts/fetch_news.py
scripts/generate_script.py
scripts/create_voice.py
scripts/render_blender_video.py
scripts/mix_audio.py
scripts/upload_youtube.py
scripts/state_manager.py
assets/models/
assets/music/
assets/studio/
data/uploaded_news.json
output/
requirements.txt
.env.example
README.md
```

## Local Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install Blender and FFmpeg, then run:

```bash
python scripts/fetch_news.py
python scripts/generate_script.py
python scripts/create_voice.py
blender -b --python scripts/render_blender_video.py
python scripts/mix_audio.py
python scripts/upload_youtube.py
```

The final video will be saved at:

```text
output/final_video.mp4
```

If YouTube credentials are missing, `upload_youtube.py` skips upload and still records the used story IDs so duplicates are avoided.

## GitHub Actions Setup

1. Push this repository to GitHub.
2. Open repository settings.
3. Go to **Secrets and variables > Actions**.
4. Add these secrets if you want automatic upload:

```text
YOUTUBE_CLIENT_SECRETS_JSON
YOUTUBE_TOKEN_JSON
```

5. Optionally add this repository variable:

```text
YOUTUBE_PRIVACY_STATUS=private
```

Supported privacy values are `private`, `unlisted`, or `public`.

## YouTube Credentials

Create OAuth credentials in Google Cloud Console with the YouTube Data API v3 enabled. The required OAuth scope is:

```text
https://www.googleapis.com/auth/youtube.upload
```

Generate a refresh token locally and paste the full token JSON into the `YOUTUBE_TOKEN_JSON` GitHub secret. Paste the client JSON into `YOUTUBE_CLIENT_SECRETS_JSON`.

## Custom Assets

Optional:

- Put music at `assets/music/background.mp3`.
- Put future Blender models under `assets/models/`.
- Put future studio assets under `assets/studio/`.

The current Blender script uses placeholder low-poly humanoid reporters so the workflow does not depend on external model downloads.

## Notes

- GitHub-hosted runners can render Blender scenes, but hourly video rendering may consume minutes quickly.
- The render is 1280x720 and uses Eevee for speed.
- The generated Roman Urdu script is template-based. You can replace `scripts/generate_script.py` with an LLM call later.
- The workflow commits `data/uploaded_news.json` back to the repo so future runs avoid repeated stories.
