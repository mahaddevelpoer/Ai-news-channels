from __future__ import annotations

import asyncio
import json
import math
import subprocess
import wave
from pathlib import Path

import edge_tts

from state_manager import ROOT_DIR, ensure_dirs


SCRIPT_PATH = ROOT_DIR / "output" / "script.json"
VOICE_DIR = ROOT_DIR / "output" / "voice"
TIMINGS_PATH = ROOT_DIR / "output" / "timings.json"
VOICEOVER_PATH = ROOT_DIR / "output" / "voiceover.wav"
SAMPLE_RATE = 44100

REPORTER_VOICES = {
    "A": "en-IN-PrabhatNeural",
    "B": "en-IN-NeerjaNeural",
}


def ffmpeg() -> str:
    return "ffmpeg"


def write_placeholder_voice(path: Path, duration_ms: int, freq: float) -> None:
    total = int(SAMPLE_RATE * duration_ms / 1000)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(total):
            t = i / SAMPLE_RATE
            envelope = 0.45 + 0.2 * math.sin(t * 2 * math.pi * 4.2)
            value = int(32767 * 0.16 * envelope * math.sin(2 * math.pi * freq * t))
            frames.extend(value.to_bytes(2, "little", signed=True))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(frames)


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        return int(wav.getnframes() / wav.getframerate() * 1000)


async def synthesize_edge_tts(text: str, voice: str, mp3_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+4%", pitch="-2Hz")
    await communicate.save(str(mp3_path))


def convert_to_wav(input_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-i",
            str(input_path),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(output_path),
        ],
        check=True,
    )


def concat_wavs(files: list[Path], output: Path) -> None:
    concat_file = output.with_suffix(".txt")
    concat_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in files), encoding="utf-8")
    subprocess.run(
        [
            ffmpeg(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output),
        ],
        check=True,
    )


def create_silence(path: Path, duration_ms: int) -> None:
    total = int(SAMPLE_RATE * duration_ms / 1000)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"\x00\x00\x00\x00" * total)


async def main_async() -> None:
    ensure_dirs()
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    with SCRIPT_PATH.open("r", encoding="utf-8") as handle:
        script = json.load(handle)

    timings = []
    audio_parts: list[Path] = []
    current_ms = 1800
    intro = VOICE_DIR / "intro_silence.wav"
    create_silence(intro, current_ms)
    audio_parts.append(intro)

    for segment in script["segments"]:
        reporter = segment["reporter"]
        wav_path = VOICE_DIR / f"segment_{segment['index']:02d}.wav"
        mp3_path = wav_path.with_suffix(".mp3")
        text = segment.get("tts_text") or segment["text"]
        try:
            await synthesize_edge_tts(text, REPORTER_VOICES[reporter], mp3_path)
            convert_to_wav(mp3_path, wav_path)
            mp3_path.unlink(missing_ok=True)
        except Exception as exc:
            print(f"Neural TTS failed for segment {segment['index']}: {exc}")
            duration = max(5500, min(13000, len(text.split()) * 330))
            write_placeholder_voice(wav_path, duration, 168 if reporter == "A" else 212)

        duration_ms = wav_duration_ms(wav_path)
        timings.append({**segment, "start_ms": current_ms, "duration_ms": duration_ms, "end_ms": current_ms + duration_ms})
        audio_parts.append(wav_path)

        pause = VOICE_DIR / f"pause_{segment['index']:02d}.wav"
        create_silence(pause, 550)
        audio_parts.append(pause)
        current_ms += duration_ms + 550

    outro = VOICE_DIR / "outro_silence.wav"
    create_silence(outro, 1800)
    audio_parts.append(outro)
    current_ms += 1800

    concat_wavs(audio_parts, VOICEOVER_PATH)
    with TIMINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"segments": timings, "total_duration_ms": current_ms}, handle, indent=2, ensure_ascii=False)

    print(f"Voiceover duration: {current_ms / 1000:.1f}s")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
