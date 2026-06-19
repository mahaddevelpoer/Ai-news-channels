from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path

from state_manager import ROOT_DIR, ensure_dirs


VIDEO_PATH = ROOT_DIR / "output" / "render.mp4"
FRAMES_DIR = ROOT_DIR / "output" / "frames"
VOICE_PATH = ROOT_DIR / "output" / "voiceover.wav"
MUSIC_PATH = ROOT_DIR / "assets" / "music" / "background.mp3"
GENERATED_MUSIC = ROOT_DIR / "output" / "generated_music.wav"
FINAL_AUDIO = ROOT_DIR / "output" / "final_audio.wav"
TEMP_VIDEO = ROOT_DIR / "output" / "render_from_frames.mp4"
FINAL_PATH = ROOT_DIR / "output" / "final_video.mp4"
SAMPLE_RATE = 44100
VIDEO_FPS = "12"


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())


def generate_music(path: Path, duration_seconds: float) -> None:
    total = int(SAMPLE_RATE * duration_seconds)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(total):
            t = i / SAMPLE_RATE
            pulse = 0.58 + 0.42 * (math.sin(2 * math.pi * 2.0 * t) > 0)
            bass = math.sin(2 * math.pi * 92 * t)
            pad = 0.38 * math.sin(2 * math.pi * 184 * t) + 0.22 * math.sin(2 * math.pi * 276 * t)
            value = int(32767 * 0.075 * pulse * (bass + pad))
            frames.extend(value.to_bytes(2, "little", signed=True))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(frames)


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    winget_ffmpeg = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    matches = list(winget_ffmpeg.glob("Gyan.FFmpeg*_x64__*/*/bin/ffmpeg.exe"))
    return str(matches[0]) if matches else "ffmpeg"


def run(command: list[str]) -> bool:
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"FFmpeg attempt failed with exit code {exc.returncode}")
        return False


def main() -> None:
    ensure_dirs()
    ffmpeg = ffmpeg_path()
    duration_seconds = wav_duration_seconds(VOICE_PATH)

    music_input = MUSIC_PATH if MUSIC_PATH.exists() else GENERATED_MUSIC
    if not MUSIC_PATH.exists():
        print("No background music asset found. Generating newsroom music bed.")
        generate_music(GENERATED_MUSIC, duration_seconds)

    audio_mixed = run(
        [
            ffmpeg,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(music_input),
            "-i",
            str(VOICE_PATH),
            "-t",
            f"{duration_seconds:.3f}",
            "-filter_complex",
            "[0:a]volume=0.22[music];[1:a]volume=1.35[voice];[music][voice]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map",
            "[aout]",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(FINAL_AUDIO),
        ]
    )
    if not audio_mixed:
        print("Music mix failed. Falling back to voice-only final audio.")
        if not run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(VOICE_PATH),
                "-filter:a",
                "volume=1.35",
                "-ar",
                "44100",
                "-ac",
                "2",
                str(FINAL_AUDIO),
            ]
        ):
            raise RuntimeError("Could not prepare final audio.")

    frames = []
    if FRAMES_DIR.exists():
        frames = sorted([p for p in FRAMES_DIR.iterdir() if p.is_file() and p.name.startswith("frame_")])
    print(f"Render video exists: {VIDEO_PATH.exists()}")
    print(f"Rendered frame count: {len(frames)}")
    if frames:
        print(f"First rendered frame: {frames[0]}")

    commands: list[list[str]] = []
    if VIDEO_PATH.exists():
        commands.append(
            [
                ffmpeg,
                "-y",
                "-i",
                str(VIDEO_PATH),
                "-i",
                str(FINAL_AUDIO),
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
        normalized_dir = ROOT_DIR / "output" / "normalized_frames"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        for old in normalized_dir.glob("frame_*.png"):
            old.unlink()
        for idx, frame in enumerate(frames, start=1):
            target = normalized_dir / f"frame_{idx:04d}.png"
            shutil.copyfile(frame, target)

        encoded = run(
            [
                ffmpeg,
                "-y",
                "-framerate",
                VIDEO_FPS,
                "-start_number",
                "1",
                "-i",
                str(normalized_dir / "frame_%04d.png"),
                "-vf",
                "fps=24,scale=1280:720,format=yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "23",
                "-preset",
                "medium",
                str(TEMP_VIDEO),
            ]
        )
        if not encoded:
            print("Sequential frame pattern failed. Trying glob pattern.")
            encoded = run(
                [
                    ffmpeg,
                    "-y",
                    "-framerate",
                    VIDEO_FPS,
                    "-pattern_type",
                    "glob",
                    "-i",
                    str(normalized_dir / "frame_*.png"),
                    "-vf",
                    "fps=24,scale=1280:720,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "23",
                    "-preset",
                    "medium",
                    str(TEMP_VIDEO),
                ]
            )
        if not encoded:
            print("Frame sequence encode failed. Creating a moving hold from the first studio frame.")
            encoded = run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(normalized_dir / "frame_0001.png"),
                    "-t",
                    f"{duration_seconds:.3f}",
                    "-vf",
                    "scale=1280:720,zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1280x720:fps=24,format=yuv420p",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "23",
                    "-preset",
                    "medium",
                    str(TEMP_VIDEO),
                ]
            )
        if not encoded:
            raise RuntimeError("Could not encode rendered studio frames.")

        commands.append(
            [
                ffmpeg,
                "-y",
                "-i",
                str(TEMP_VIDEO),
                "-i",
                str(FINAL_AUDIO),
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

    for command in commands:
        if run(command):
            print(f"Final video saved to {FINAL_PATH}")
            return

    raise RuntimeError("Could not create final video. Studio render frames are required; animation.mp4 is not used as a final-video fallback.")


if __name__ == "__main__":
    main()
