from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path

from pydub import AudioSegment

from state_manager import ROOT_DIR, ensure_dirs


VIDEO_PATH = ROOT_DIR / "output" / "render.mp4"
FRAMES_DIR = ROOT_DIR / "output" / "frames"
VOICE_PATH = ROOT_DIR / "output" / "voiceover.wav"
MUSIC_PATH = ROOT_DIR / "assets" / "music" / "background.mp3"
GENERATED_MUSIC = ROOT_DIR / "output" / "generated_music.wav"
FINAL_PATH = ROOT_DIR / "output" / "final_video.mp4"
BREAKING_ANIMATION = ROOT_DIR / "assets" / "animation.mp4"


def generate_music(path: Path, duration_ms: int) -> None:
    sample_rate = 44100
    total = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total):
            t = i / sample_rate
            beat = 0.65 + 0.35 * (math.sin(2 * math.pi * 2 * t) > 0)
            tone = math.sin(2 * math.pi * 110 * t) + 0.35 * math.sin(2 * math.pi * 220 * t)
            value = int(32767 * 0.08 * beat * tone)
            frames.extend(value.to_bytes(2, "little", signed=True))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(frames)


def main() -> None:
    ensure_dirs()
    voice = AudioSegment.from_file(VOICE_PATH).set_channels(2).set_frame_rate(44100).apply_gain(4)
    duration_ms = len(voice)

    if MUSIC_PATH.exists():
        music = AudioSegment.from_file(MUSIC_PATH)
    else:
        generate_music(GENERATED_MUSIC, duration_ms)
        music = AudioSegment.from_file(GENERATED_MUSIC)

    music = music.set_channels(2).set_frame_rate(44100)
    while len(music) < duration_ms:
        music += music
    music = music[:duration_ms]

    intro = music[:2500].apply_gain(-6)
    bed = music[2500:].apply_gain(-19)
    mixed = intro + bed
    mixed = mixed.overlay(voice)
    audio_path = ROOT_DIR / "output" / "final_audio.wav"
    mixed.export(audio_path, format="wav")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        winget_ffmpeg = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        matches = list(winget_ffmpeg.glob("Gyan.FFmpeg*_x64__*/*/bin/ffmpeg.exe"))
        ffmpeg = str(matches[0]) if matches else "ffmpeg"

    frames = sorted(FRAMES_DIR.glob("frame_*.png")) if FRAMES_DIR.exists() else []
    print(f"Render video exists: {VIDEO_PATH.exists()}")
    print(f"Rendered frame count: {len(frames)}")

    commands: list[list[str]] = []
    if VIDEO_PATH.exists():
        commands.append(
            [
                ffmpeg,
                "-y",
                "-i",
                str(VIDEO_PATH),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(FINAL_PATH),
            ]
        )
    if frames:
        commands.append(
            [
                ffmpeg,
                "-y",
                "-framerate",
                "24",
                "-pattern_type",
                "glob",
                "-i",
                str(FRAMES_DIR / "frame_*.png"),
                "-i",
                str(audio_path),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "23",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(FINAL_PATH),
            ]
        )
    if BREAKING_ANIMATION.exists():
        commands.append(
            [
                ffmpeg,
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(BREAKING_ANIMATION),
                "-i",
                str(audio_path),
                "-t",
                f"{duration_ms / 1000:.3f}",
                "-vf",
                "scale=1280:720,format=yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "23",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(FINAL_PATH),
            ]
        )

    last_error: subprocess.CalledProcessError | None = None
    for command in commands:
        try:
            subprocess.run(command, check=True)
            last_error = None
            break
        except subprocess.CalledProcessError as exc:
            last_error = exc
            print(f"FFmpeg attempt failed with exit code {exc.returncode}. Trying fallback if available.")

    if last_error is not None:
        raise last_error
    print(f"Final video saved to {FINAL_PATH}")


if __name__ == "__main__":
    main()
