#!/usr/bin/env python3
"""Generate pre-recorded MP3 narration files from locale JSON.

Engines
-------
edge   — Microsoft Neural TTS (free, high quality, recommended).
         Requires: pip install edge-tts
gtts   — Google Text-to-Speech (simpler, less expressive).
         Requires: pip install gTTS

The shipped clips
-----------------
The files in www/audio/ were made with edge-tts and the defaults below:

    fr  fr-FR-RemyMultilingualNeural   rate -12%  pitch -4Hz
    en  en-US-AndrewMultilingualNeural rate -10%  pitch -4Hz

The "Multilingual" voices are Microsoft's newest generation and sound far
less synthetic than the older ones (Denise, Sonia); slowing them down and
lowering the pitch a little gives the storyteller tone. They were picked by
ear against Denise, Henri, Vivienne and Chatterbox (an open voice-cloning
model, which needs minutes per clip on a CPU).

To regenerate them all, e.g. after changing a narrated line:

    pip install edge-tts
    python scripts/generate_audio.py

then update STATIC_AUDIO_SECONDS in const.py: tests/unit/test_static_audio.py
prints the clip lengths it expects.

Quick start
-----------
    # List available voices for a language
    python scripts/generate_audio.py --list-voices --lang fr

    # Generate comparison samples (writes to screenshots/audio-samples/)
    python scripts/generate_audio.py --samples --lang fr

    # Try other settings for one language
    python scripts/generate_audio.py --lang fr \\
        --voice fr-FR-HenriNeural --rate -15% --pitch -6Hz

Output
------
    custom_components/loup_garou/www/audio/{lang}/{stem}.mp3

Only keys present in STATIC_AUDIO_MAP are generated.  Re-run whenever
the corresponding locale strings change.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "custom_components" / "loup_garou" / "locales"
AUDIO_DIR  = ROOT / "custom_components" / "loup_garou" / "www" / "audio"
SAMPLES_DIR_DEFAULT = ROOT / "screenshots" / "audio-samples"  # git-ignored

sys.path.insert(0, str(ROOT / "custom_components"))
from loup_garou.const import STATIC_AUDIO_MAP  # noqa: E402

# ── Default voices per language ───────────────────────────────────────────────

# Language → (voice, rate, pitch) used for the shipped clips.
DEFAULT_EDGE_VOICE: dict[str, tuple[str, str, str]] = {
    "fr": ("fr-FR-RemyMultilingualNeural", "-12%", "-4Hz"),
    "en": ("en-US-AndrewMultilingualNeural", "-10%", "-4Hz"),
}

DEFAULT_GTTS_LANG: dict[str, str] = {
    "fr": "fr",
    "en": "en",
}

# ── edge-tts parameter validation ─────────────────────────────────────────────

_RATE_RE   = re.compile(r"^[+-]\d+%$")
_PITCH_RE  = re.compile(r"^[+-]\d+Hz$")
_VOLUME_RE = re.compile(r"^[+-]\d+%$")


def _validate(value: str, pattern: re.Pattern, name: str) -> str:
    if not pattern.match(value):
        print(f"Invalid {name} {value!r}. Must match {pattern.pattern}  e.g. -15%  +5Hz",
              file=sys.stderr)
        sys.exit(1)
    return value


# ── Comparison samples ────────────────────────────────────────────────────────

SAMPLE_TEXTS = {
    "fr": {
        "night":  "La nuit tombe sur le village. Tout le monde ferme les yeux.",
        "wolves": "Les loups-garous ouvrent les yeux.",
        "win":    "Les loups-garous ont dévoré tout le village. Les loups ont gagné !",
    },
    "en": {
        "night":  "Night falls over the village. Everyone closes their eyes.",
        "wolves": "The werewolves open their eyes.",
        "win":    "The werewolves have devoured the whole village. The wolves have won!",
    },
}

# Preset combinations to compare:  (label_suffix, rate, pitch)
SAMPLE_PRESETS: list[tuple[str, str, str]] = [
    ("default",       "+0%",  "+0Hz"),
    ("slow",          "-15%", "+0Hz"),
    ("slow_deep",     "-15%", "-10Hz"),
    ("very_slow_deep","-22%", "-15Hz"),
]

SAMPLE_VOICES: dict[str, list[str]] = {
    "fr": [
        "fr-FR-RemyMultilingualNeural",
        "fr-FR-DeniseNeural",
        "fr-FR-HenriNeural",
        "fr-FR-VivienneMultilingualNeural",
        "fr-BE-CharlineNeural",
        "fr-BE-GerardNeural",
    ],
    "en": [
        "en-US-AndrewMultilingualNeural",
        "en-US-BrianMultilingualNeural",
        "en-GB-SoniaNeural",
        "en-GB-RyanNeural",
    ],
}


async def _generate_edge(text: str, voice: str, rate: str, pitch: str,
                          volume: str, out_path: Path) -> None:
    try:
        import edge_tts
    except ImportError:
        print("edge-tts not installed — run: pip install edge-tts", file=sys.stderr)
        sys.exit(1)
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate,
                                pitch=pitch, volume=volume)
    await comm.save(str(out_path))


def _generate_gtts(text: str, lang: str, slow: bool, tld: str,
                   out_path: Path) -> None:
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS not installed — run: pip install gTTS", file=sys.stderr)
        sys.exit(1)
    gTTS(text=text, lang=DEFAULT_GTTS_LANG[lang], slow=slow, tld=tld).save(str(out_path))


# ── Core generation ───────────────────────────────────────────────────────────

async def generate_for_lang(
    lang: str,
    engine: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
    gtts_slow: bool,
    gtts_tld: str,
) -> None:
    locale_path = LOCALE_DIR / f"{lang}.json"
    if not locale_path.exists():
        print(f"Locale file not found: {locale_path}", file=sys.stderr)
        sys.exit(1)

    locale: dict = json.loads(locale_path.read_text(encoding="utf-8"))
    out_dir = AUDIO_DIR / lang
    out_dir.mkdir(parents=True, exist_ok=True)

    params = (f"voice={voice} rate={rate} pitch={pitch} volume={volume}"
              if engine == "edge" else
              f"lang={DEFAULT_GTTS_LANG[lang]} slow={gtts_slow} tld={gtts_tld}")
    print(f"\nGenerating [{lang}] via {engine} — {params}")
    print(f"Output: {out_dir}\n")

    for locale_key, stem in STATIC_AUDIO_MAP.items():
        text = locale.get(locale_key, "")
        if not text:
            print(f"  SKIP  {locale_key!r} — key missing in {lang}.json")
            continue
        out_path = out_dir / f"{stem}.mp3"
        print(f"  {stem}.mp3")
        if engine == "edge":
            await _generate_edge(text, voice, rate, pitch, volume, out_path)
        else:
            _generate_gtts(text, lang, gtts_slow, gtts_tld, out_path)

    print(f"\n  {len(STATIC_AUDIO_MAP)} files written.")


async def generate_samples(lang: str, out_dir: Path) -> None:
    try:
        import edge_tts
    except ImportError:
        print("edge-tts not installed — run: pip install edge-tts", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    texts = SAMPLE_TEXTS.get(lang, SAMPLE_TEXTS["fr"])
    voices = SAMPLE_VOICES.get(lang, SAMPLE_VOICES["fr"])

    tasks = []
    labels = []

    for voice in voices:
        short = voice.split("-")[-1].replace("Neural", "").replace("Multilingual", "ML")
        for phrase_key, text in texts.items():
            for rate, pitch_val in [s[1:] for s in SAMPLE_PRESETS]:
                label = f"{lang}_{short}_{phrase_key}_{rate.replace('%','pct')}_{pitch_val.replace('Hz','hz')}"
                out_path = out_dir / f"{label}.mp3"
                tasks.append(_generate_edge(text, voice, rate, pitch_val, "+0%", out_path))
                labels.append(label)

    # Also generate the named presets under a cleaner naming scheme
    tasks_preset = []
    labels_preset = []
    for voice in voices:
        short = voice.split("-")[-1].replace("Neural", "").replace("Multilingual", "ML")
        for preset_name, rate, pitch_val in SAMPLE_PRESETS:
            for phrase_key, text in texts.items():
                label = f"{lang}_{short}_{preset_name}_{phrase_key}"
                out_path = out_dir / f"{label}.mp3"
                tasks_preset.append(_generate_edge(text, voice, rate, pitch_val, "+0%", out_path))
                labels_preset.append(label)

    all_tasks = list(zip(tasks_preset, labels_preset))
    print(f"\nGenerating {len(all_tasks)} sample files → {out_dir}\n")
    for coro, label in all_tasks:
        print(f"  {label}.mp3 …", end=" ", flush=True)
        await coro
        print("✓")
    print(f"\nDone — {len(all_tasks)} files in {out_dir}")


async def list_voices(lang: str) -> None:
    try:
        import edge_tts
    except ImportError:
        print("edge-tts not installed — run: pip install edge-tts", file=sys.stderr)
        sys.exit(1)
    voices = await edge_tts.list_voices()
    prefix = lang + "-"
    matches = [v for v in voices if v["Locale"].startswith(prefix)]
    if not matches:
        print(f"No voices found for language prefix {lang!r}")
        return
    print(f"\nAvailable voices for '{lang}':\n")
    print(f"  {'ShortName':<40} {'Gender':<8} Locale")
    print(f"  {'-'*40} {'-'*8} ------")
    for v in sorted(matches, key=lambda x: x["ShortName"]):
        print(f"  {v['ShortName']:<40} {v['Gender']:<8} {v['Locale']}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Generate static MP3 narration files for Loup Garou.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target
    p.add_argument("--lang", action="append", choices=["fr", "en"], metavar="LANG",
                   help="Language to generate (fr/en). May be repeated. Default: fr en")

    # Mode
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--samples", nargs="?", const=str(SAMPLES_DIR_DEFAULT), metavar="DIR",
                      help="Generate voice comparison samples instead of production files. "
                           f"Default dir: {SAMPLES_DIR_DEFAULT}")
    mode.add_argument("--list-voices", action="store_true",
                      help="List available edge-tts voices for --lang and exit.")

    # Engine
    p.add_argument("--engine", choices=["edge", "gtts"], default="edge",
                   help="TTS engine to use (default: edge)")

    # edge-tts parameters
    edge_group = p.add_argument_group("edge-tts options")
    edge_group.add_argument("--voice", metavar="VOICE",
                            help="Voice name, e.g. fr-FR-HenriNeural. "
                                 "Defaults: see 'The shipped clips' below")
    edge_group.add_argument("--voice-fr", metavar="VOICE",
                            help="French voice (overrides --voice for fr)")
    edge_group.add_argument("--voice-en", metavar="VOICE",
                            help="English voice (overrides --voice for en)")
    edge_group.add_argument("--rate", metavar="RATE",
                            help="Speed adjustment, e.g. -15%% (default: per language)")
    edge_group.add_argument("--pitch", metavar="PITCH",
                            help="Pitch adjustment, e.g. -10Hz (default: per language)")
    edge_group.add_argument("--volume", default="+0%", metavar="VOLUME",
                            help="Volume adjustment, e.g. +10%% (default: +0%%)")

    # gTTS parameters
    gtts_group = p.add_argument_group("gTTS options (--engine gtts)")
    gtts_group.add_argument("--gtts-slow", action="store_true",
                            help="Use gTTS slow mode")
    gtts_group.add_argument("--gtts-tld", default="com", metavar="TLD",
                            help="gTTS accent TLD, e.g. ca for Canadian French (default: com)")

    args = p.parse_args()
    langs = args.lang or ["fr", "en"]

    if args.list_voices:
        for lang in langs:
            asyncio.run(list_voices(lang))
        return

    if args.samples is not None:
        out_dir = Path(args.samples)
        for lang in langs:
            asyncio.run(generate_samples(lang, out_dir))
        return

    for lang in langs:
        default_voice, default_rate, default_pitch = DEFAULT_EDGE_VOICE[lang]
        voice = getattr(args, f"voice_{lang}", None) or args.voice or default_voice
        rate = args.rate or default_rate
        pitch = args.pitch or default_pitch
        # Validate edge-tts params only when actually using edge
        if args.engine == "edge":
            _validate(rate,        _RATE_RE,   "--rate")
            _validate(pitch,       _PITCH_RE,  "--pitch")
            _validate(args.volume, _VOLUME_RE, "--volume")
        asyncio.run(generate_for_lang(
            lang=lang,
            engine=args.engine,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=args.volume,
            gtts_slow=args.gtts_slow,
            gtts_tld=args.gtts_tld,
        ))


if __name__ == "__main__":
    main()
