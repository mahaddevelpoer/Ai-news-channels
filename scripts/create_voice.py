from __future__ import annotations

import json
import math
import wave
from pathlib import Path

from gtts import gTTS

from state_manager import ROOT_DIR, ensure_dirs

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None


SCRIPT_PATH = ROOT_DIR / "output" / "script.json"
VOICE_DIR = ROOT_DIR / "output" / "voice"
TIMINGS_PATH = ROOT_DIR / "output" / "timings.json"
SAMPLE_RATE = 44100


def tone_samples(duration_ms: int, freq: float) -> list[int]:
    total = int(SAMPLE_RATE * duration_ms / 1000)
    samples = []
    for i in range(total):
        t = i / SAMPLE_RATE
        envelope = 0.35 + 0.12 * math.sin(t * 2 * math.pi * 3)
        syllable = 1.0 if math.sin(t * 2 * math.pi * 5.5) > -0.35 else 0.2
        value = int(32767 * 0.18 * envelope * syllable * math.sin(2 * math.pi * freq * t))
        samples.append(value)
    return samples


def write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for value in samples:
            frames.extend(value.to_bytes(2, "little", signed=True))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(frames)


def silence(duration_ms: int) -> list[int]:
    return [0] * int(SAMPLE_RATE * duration_ms / 1000)


def create_segment_voice(text: str, output_path: Path, reporter: str) -> list[int]:
    if AudioSegment is not None:
        try:
            tts = gTTS(text=text, lang="ur", slow=False)
            temp_mp3 = output_path.with_suffix(".mp3")
            tts.save(str(temp_mp3))
            audio = AudioSegment.from_file(temp_mp3)
            temp_mp3.unlink(missing_ok=True)
            if reporter == "B":
                audio = audio._spawn(audio.raw_data, overrides={"frame_rate": int(audio.frame_rate * 1.04)})
            else:
                audio = audio._spawn(audio.raw_data, overrides={"frame_rate": int(audio.frame_rate * 0.98)})
            audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(2).apply_gain(4)
            audio.export(output_path, format="wav")
            with wave.open(str(output_path), "rb") as wav:
                raw = wav.readframes(wav.getnframes())
            samples = []
            for i in range(0, len(raw), 4):
                samples.append(int.from_bytes(raw[i : i + 2], "little", signed=True))
            return samples
        except Exception as exc:
            print(f"TTS failed, using generated placeholder voice: {exc}")

    duration = max(6500, min(16000, len(text.split()) * 430))
    samples = tone_samples(duration, 180 if reporter == "A" else 215)
    write_wav(output_path, samples)
    return samples


def main() -> None:
    ensure_dirs()
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    with SCRIPT_PATH.open("r", encoding="utf-8") as handle:
        script = json.load(handle)

    current_ms = 2500
    full_samples = silence(current_ms)
    timings = []

    for segment in script["segments"]:
        output = VOICE_DIR / f"segment_{segment['index']:02d}.wav"
        samples = create_segment_voice(segment["text"], output, segment["reporter"])
        duration_ms = int(len(samples) / SAMPLE_RATE * 1000)

        timings.append(
            {
                **segment,
                "start_ms": current_ms,
                "duration_ms": duration_ms,
                "end_ms": current_ms + duration_ms,
            }
        )
        full_samples.extend(samples)
        full_samples.extend(silence(900))
        current_ms += duration_ms + 900

    full_samples.extend(silence(2500))
    write_wav(ROOT_DIR / "output" / "voiceover.wav", full_samples)

    with TIMINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"segments": timings, "total_duration_ms": int(len(full_samples) / SAMPLE_RATE * 1000)}, handle, indent=2, ensure_ascii=False)

    print(f"Voiceover duration: {len(full_samples) / SAMPLE_RATE:.1f}s")


if __name__ == "__main__":
    main()
