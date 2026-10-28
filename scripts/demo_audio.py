"""Add music and an English/Spanish voice-over to the demo videos. Developer tool.

    python scripts/demo_audio.py                 # music only (no API key needed)
    ELEVENLABS_API_KEY=... python scripts/demo_audio.py   # + ElevenLabs voice (EN and ES) and music
    (or save the key in ~/.config/elevenlabs/api_key)

Reads docs/media/<scene>.mp4 (silent, from record_demo.py) and writes:
    docs/media/<scene>.music.mp4      music only, used when a narrated version is missing
    docs/media/<scene>.en.mp4         English narration + music
    docs/media/<scene>.es.mp4         Spanish narration + music

Optional: ELEVENLABS_VOICE_EN / ELEVENLABS_VOICE_ES (voice ids), MOON_MUSIC=synth to skip
ElevenLabs Music and use the built-in synthesized track instead.
Generated audio is cached in build/demo-audio so re-running doesn't spend credits twice.
"""

import array
import json
import math
import os
import random
import subprocess
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
CACHE = ROOT / "build" / "demo-audio"

API = "https://api.elevenlabs.io/v1"
# The key can also live in this file (outside the repo) instead of the environment.
KEY_FILE = Path.home() / ".config" / "elevenlabs" / "api_key"
MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"  # "Sarah", a premade multilingual voice
VOICE_DELAY = 0.6  # seconds of music before the narrator starts
TAIL = 1.2  # seconds of music after the narrator ends

NARRATION = {
    "getting-started": {
        "en": "This is Moon Code, the code editor that lives in your terminal. "
              "Press P to create a project, pick a template, and you're ready to code.",
        "es": "Esto es Moon Code, el editor de código que vive en tu terminal. "
              "Pulsa P para crear un proyecto, elige una plantilla y listo para programar.",
    },
    "code-and-run": {
        "en": "Write code the way you're used to. Moon Code indents for you, closes brackets, "
              "and suggests names as you type. Press Tab to accept, then F5 to run it in the integrated terminal.",
        "es": "Escribe código como siempre. Moon Code indenta por ti, cierra los paréntesis "
              "y te sugiere nombres mientras escribes. Pulsa Tab para aceptar y F5 para ejecutarlo en la terminal integrada.",
    },
    "power-tools": {
        "en": "Jump to any file with Control P. Open the command palette with F1 to run any command, "
              "like changing the color theme. Search across your whole project, "
              "and turn extensions on or off with a single click.",
        "es": "Salta a cualquier archivo con Control P. Abre la paleta de comandos con F1 para ejecutar "
              "cualquier comando, como cambiar el tema de colores. Busca en todo tu proyecto "
              "y activa o desactiva extensiones con un solo clic.",
    },
    "moon-ai": {
        "en": "Need help? Press Control L to open Moon AI. Ask a question about the file you're working on, "
              "and a model running locally with Ollama answers right inside the editor. "
              "Your code never leaves your computer. Moon Code: install it with one command and start coding.",
        "es": "¿Necesitas ayuda? Pulsa Control L para abrir Moon AI. Haz una pregunta sobre el archivo en el que trabajas "
              "y un modelo que corre en tu equipo con Ollama responde dentro del editor. "
              "Tu código nunca sale de tu computadora. Moon Code: instálalo con un solo comando y empieza a programar.",
    },
}

MUSIC_PROMPT = ("Calm, modern lo-fi electronic background music for a software product demo. "
                "Soft synth pads, gentle plucked arpeggios, light kick, warm and optimistic, "
                "no vocals, steady tempo around 80 BPM, seamless loop.")


# --- ElevenLabs ---------------------------------------------------------------


def _post(path: str, body: dict, key: str, accept: str = "audio/mpeg") -> bytes:
    request = urllib.request.Request(
        f"{API}{path}", data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": accept},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def voice_over(scene: str, lang: str, key: str) -> Path:
    target = CACHE / f"{scene}.{lang}.mp3"
    if target.exists():
        return target
    voice = os.environ.get(f"ELEVENLABS_VOICE_{lang.upper()}", DEFAULT_VOICE)
    body = {
        "text": NARRATION[scene][lang],
        "model_id": MODEL,
        "language_code": lang,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True},
    }
    print(f"  ElevenLabs voice: {scene} ({lang})")
    target.write_bytes(_post(f"/text-to-speech/{voice}?output_format=mp3_44100_128", body, key))
    return target


def eleven_music(key: str, seconds: int) -> Path | None:
    target = CACHE / "music-eleven.mp3"
    if target.exists():
        return target
    print("  ElevenLabs music…")
    try:
        audio = _post("/music?output_format=mp3_44100_128",
                      {"prompt": MUSIC_PROMPT, "music_length_ms": seconds * 1000}, key)
    except urllib.error.HTTPError as error:
        print(f"  ElevenLabs music unavailable ({error.code}); using the synthesized track.")
        return None
    target.write_bytes(audio)
    return target


# --- Synthesized fallback track ---------------------------------------------------

RATE = 32_000
BEAT = 0.75  # 80 BPM
CHORDS = [  # Am9, Fmaj7, Cmaj7, G6 — two bars each
    [45, 52, 55, 59, 60],
    [41, 48, 52, 55, 57],
    [48, 55, 59, 62, 64],
    [43, 50, 55, 59, 64],
]


def _freq(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def synth_music(seconds: int) -> Path:
    """A soft lo-fi loop (pads, plucked arpeggio, light kick), generated here so it's royalty-free."""
    target = CACHE / "music-synth.wav"
    if target.exists():
        return target
    print("  Synthesizing music…")
    total = int(seconds * RATE)
    samples = array.array("f", [0.0]) * total
    chord_length = 8 * BEAT
    rng = random.Random(7)

    def add_tone(start: float, length: float, freq: float, gain: float, attack: float, decay: float | None) -> None:
        first, count = int(start * RATE), int(length * RATE)
        step = 2 * math.pi * freq / RATE
        for i in range(count):
            index = first + i
            if index >= total:
                break
            t = i / RATE
            envelope = min(1.0, t / attack) * (math.exp(-t / decay) if decay else min(1.0, (length - t) / 0.8))
            phase = step * i
            samples[index] += gain * envelope * (math.sin(phase) + 0.25 * math.sin(2 * phase))

    time = 0.0
    bar = 0
    while time < seconds:
        chord = CHORDS[bar % len(CHORDS)]
        for note in chord:  # pad
            add_tone(time, chord_length + 0.6, _freq(note), 0.045, 1.2, None)
        arpeggio = [n + 12 for n in chord[1:]] + [chord[2] + 24]
        for step in range(16):  # eighth-note pluck
            note = arpeggio[(step * 3 + bar) % len(arpeggio)]
            add_tone(time + step * BEAT / 2, 0.9, _freq(note), 0.05 + rng.random() * 0.015, 0.005, 0.28)
        for beat in (0, 2, 4, 6):  # soft kick
            start = int((time + beat * BEAT) * RATE)
            for i in range(int(0.25 * RATE)):
                if start + i >= total:
                    break
                t = i / RATE
                samples[start + i] += 0.22 * math.exp(-t / 0.07) * math.sin(2 * math.pi * (55 + 90 * math.exp(-t / 0.03)) * t)
        time += chord_length
        bar += 1

    peak = max(abs(s) for s in samples) or 1.0
    pcm = array.array("h", (int(max(-1.0, min(1.0, s / peak * 0.8)) * 32767) for s in samples))
    raw = CACHE / "music-raw.wav"
    with wave.open(str(raw), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(pcm.tobytes())
    # A little space and warmth, then a consistent loudness.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                    "aecho=0.8:0.6:90|170:0.25|0.15,lowpass=f=7000,highpass=f=40,loudnorm=I=-20:TP=-2",
                    "-ar", "44100", "-ac", "2", str(target)], check=True)
    raw.unlink()
    return target


# --- Mixing -------------------------------------------------------------------


def duration(path: Path) -> float:
    output = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                            capture_output=True, text=True, check=True).stdout
    return float(output.strip())


def mix(video: Path, music: Path, voice: Path | None, output: Path) -> None:
    video_length = duration(video)
    total = video_length
    if voice is not None:
        total = max(video_length, VOICE_DELAY + duration(voice) + TAIL)
    extra = total - video_length
    fade_start = max(total - 1.5, 0)
    inputs = ["-i", str(video), "-stream_loop", "-1", "-i", str(music)]
    if voice is None:
        graph = (f"[1:a]aresample=44100,afade=t=in:d=1.2,afade=t=out:st={fade_start:.2f}:d=1.5,"
                 f"loudnorm=I=-19:TP=-1.5[a]")
    else:
        delay = int(VOICE_DELAY * 1000)
        inputs += ["-i", str(voice)]
        graph = (
            f"[2:a]aresample=44100,adelay={delay}|{delay},apad,asplit=2[voice][key];"
            f"[1:a]aresample=44100,volume=0.5,afade=t=in:d=1.2[music];"
            f"[music][key]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[ducked];"
            f"[ducked][voice]amix=inputs=2:normalize=0,afade=t=out:st={fade_start:.2f}:d=1.5,"
            f"loudnorm=I=-16:TP=-1.5[a]"
        )
    graph += f";[0:v]tpad=stop_mode=clone:stop_duration={extra:.2f}[v]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph,
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output)], check=True)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
    longest = int(max(duration(MEDIA / f"{scene}.mp4") for scene in NARRATION)) + 30

    music = None
    if key and os.environ.get("MOON_MUSIC") != "synth":
        music = eleven_music(key, min(longest, 120))
    music = music or synth_music(longest)

    for scene in NARRATION:
        video = MEDIA / f"{scene}.mp4"
        print(f"{scene}:")
        mix(video, music, None, MEDIA / f"{scene}.music.mp4")
        if not key:
            continue
        for lang in ("en", "es"):
            mix(video, music, voice_over(scene, lang, key), MEDIA / f"{scene}.{lang}.mp4")
            print(f"  → {scene}.{lang}.mp4")

    # The website reads this to pick the narrated video for the visitor's language.
    manifest = {scene: [lang for lang in ("en", "es") if (MEDIA / f"{scene}.{lang}.mp4").exists()] for scene in NARRATION}
    (MEDIA / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if not key:
        print("\nNo ELEVENLABS_API_KEY: made music-only videos. Set the key to add the EN/ES narration.")


if __name__ == "__main__":
    sys.exit(main())
