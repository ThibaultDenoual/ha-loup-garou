#!/usr/bin/env python3
"""Generate pre-recorded MP3 narration files from locale JSON.

Usage:
    python scripts/generate_audio.py --lang fr
    python scripts/generate_audio.py --lang en
    python scripts/generate_audio.py --lang fr --lang en  # both at once

Requires gTTS:
    pip install gTTS

Alternatively, for higher-quality voices, use edge-tts (see comment below).

Output:
    custom_components/loup_garou/www/audio/{lang}/{stem}.mp3

Only keys present in STATIC_AUDIO_MAP are generated.  Re-run this script
whenever the corresponding locale strings change.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "custom_components" / "loup_garou" / "locales"
AUDIO_DIR  = ROOT / "custom_components" / "loup_garou" / "www" / "audio"

sys.path.insert(0, str(ROOT / "custom_components"))
from loup_garou.const import STATIC_AUDIO_MAP  # noqa: E402

GTTS_LANG = {"fr": "fr", "en": "en"}

# edge-tts alternative (higher quality, requires: pip install edge-tts):
#   import asyncio, edge_tts
#   async def _edge(text, lang, out):
#       voice = "fr-FR-DeniseNeural" if lang == "fr" else "en-US-JennyNeural"
#       await edge_tts.Communicate(text, voice).save(str(out))
#   asyncio.run(_edge(text, lang, out_path))


def generate_gtts(text: str, lang: str, out_path: Path) -> None:
    try:
        from gtts import gTTS
    except ImportError:
        print("  gTTS not installed — run: pip install gTTS", file=sys.stderr)
        sys.exit(1)
    tts = gTTS(text=text, lang=GTTS_LANG[lang], slow=False)
    tts.save(str(out_path))


def generate_for_lang(lang: str) -> None:
    locale_path = LOCALE_DIR / f"{lang}.json"
    if not locale_path.exists():
        print(f"Locale file not found: {locale_path}", file=sys.stderr)
        sys.exit(1)

    locale: dict = json.loads(locale_path.read_text(encoding="utf-8"))
    out_dir = AUDIO_DIR / lang
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {lang} audio → {out_dir}")
    for locale_key, stem in STATIC_AUDIO_MAP.items():
        text = locale.get(locale_key, "")
        if not text:
            print(f"  SKIP  {locale_key!r} — key missing in {lang}.json")
            continue
        out_path = out_dir / f"{stem}.mp3"
        print(f"  {stem}.mp3  ← {text!r}")
        generate_gtts(text, lang, out_path)

    print(f"Done — {len(STATIC_AUDIO_MAP)} files written to {out_dir}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static MP3 narration files.")
    parser.add_argument("--lang", action="append", choices=["fr", "en"],
                        help="Language to generate (may be repeated). Default: fr en")
    args = parser.parse_args()
    langs = args.lang or ["fr", "en"]
    for lang in langs:
        generate_for_lang(lang)


if __name__ == "__main__":
    main()
