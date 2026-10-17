"""Keep static UI copy available in each shipped language."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GAME_ROOT = ROOT / "custom_components" / "loup_garou" / "www" / "game"
LOCALES = ROOT / "custom_components" / "loup_garou" / "locales"

_HTML_KEY = re.compile(r'data-i18n(?:-placeholder|-aria-label)?="([^"]+)"')
_JS_KEY = re.compile(r"\bt\([\"']([^\"']+)[\"']")


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def test_frontend_static_translation_keys_exist_in_both_locales() -> None:
    used_keys: set[str] = set()
    sources = [*GAME_ROOT.glob("*.html"), *GAME_ROOT.rglob("*.js")]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        used_keys.update(_HTML_KEY.findall(text))
        used_keys.update(_JS_KEY.findall(text))

    for language in ("en", "fr"):
        locale = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        missing = sorted(key for key in used_keys if key not in locale)
        assert not missing, f"{language} locale is missing frontend keys: {missing}"


def test_frontend_pages_have_unique_element_ids() -> None:
    for page in GAME_ROOT.glob("*.html"):
        parser = _IdCollector()
        parser.feed(page.read_text(encoding="utf-8"))
        duplicates = sorted({element_id for element_id in parser.ids if parser.ids.count(element_id) > 1})
        assert not duplicates, f"{page.name} has duplicate element IDs: {duplicates}"
