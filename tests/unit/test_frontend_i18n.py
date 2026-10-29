"""The browser UI must not ship hard-coded copy: every visible string comes
from the locale bundles, and every key the UI asks for exists in both."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

COMPONENT = Path(__file__).parent.parent.parent / "custom_components" / "loup_garou"
WWW = COMPONENT / "www" / "game"
HTML_FILES = sorted(WWW.glob("*.html"))
JS_FILES = sorted(WWW.glob("js/**/*.js"))
LANGUAGES = ["fr", "en"]

# Literal keys in JS: any quoted string in a translated namespace.
KEY_RE = re.compile(r"""['"]((?:ui|launcher|role|phase|demo|article|team)\.[a-z0-9_.:]+)['"]""")
# Namespaces passed whole to setConnection(); dynamic_keys() covers their keys.
PREFIXES = {"ui.ws", "launcher.connection"}
# Attributes that are read aloud or shown and so need data-i18n-* instead.
TEXT_ATTRS = {"placeholder", "aria-label", "title", "alt"}


def load(lang: str) -> dict:
    return json.loads((COMPONENT / "locales" / f"{lang}.json").read_text())


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text: list[str] = []
        self.literal_attrs: list[str] = []
        self.keys: set[str] = set()
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        for name, value in attrs:
            if name.startswith("data-i18n") and not name.endswith("-vars"):
                self.keys.add(value)
            elif name in TEXT_ATTRS and value:
                self.literal_attrs.append(f"<{tag} {name}={value!r}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.text.append(data.strip())


def parse(path: Path) -> _Collector:
    collector = _Collector()
    collector.feed(re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S))
    return collector


def role_ids() -> list[str]:
    source = (WWW / "js" / "roles.js").read_text()
    block = re.search(r"ROLE_ORDER = \[(.*?)\]", source, re.S).group(1)
    return re.findall(r"'(\w+)'", block)


def dynamic_keys() -> set[str]:
    """Keys the UI builds from templates (`ui.phase.${phase}` and friends)."""
    keys = {f"ui.phase.{p}" for p in ("setup", "role_reveal", "night", "day", "vote", "game_over")}
    for status in ("connecting", "connected", "reconnecting", "open_from_ha"):
        keys |= {f"ui.ws.{status}", f"launcher.connection.{status}"}
    keys |= {"ui.error.bad_request", "ui.error.internal_error"}
    keys |= {f"launcher.lang.{lang}" for lang in LANGUAGES}
    for role in role_ids():
        keys |= {f"role.{role}.{field}" for field in ("name", "description", "team")}
    for role in ("werewolf", "seer", "witch", "cupid", "alpha_wolf"):
        keys.add(f"role.{role}.action_prompt")
    return keys


def ui_keys() -> set[str]:
    keys = set(dynamic_keys())
    for path in HTML_FILES:
        keys |= parse(path).keys
    for path in JS_FILES:
        keys |= set(KEY_RE.findall(path.read_text()))
    return keys - PREFIXES


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda p: p.name)
def test_html_has_no_literal_text(path):
    page = parse(path)
    assert page.text == [], f"Text outside data-i18n in {path.name}: {page.text}"
    assert page.literal_attrs == [], f"Untranslated attributes in {path.name}: {page.literal_attrs}"


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_js_never_assigns_literal_text(path):
    source = path.read_text()
    assert "innerHTML" not in source, f"{path.name} uses innerHTML; build nodes with dom.js"
    literal = re.findall(r"""(?:textContent\s*=|\btext:)\s*(['"`][^'"`]*[A-Za-zÀ-ÿ][^'"`]*['"`])""", source)
    assert literal == [], f"Hard-coded copy in {path.name}: {literal}"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_ui_key_exists(lang):
    locale = load(lang)
    missing = sorted(k for k in ui_keys() if not isinstance(locale.get(k), str))
    assert missing == [], f"Missing in {lang}.json: {missing}"
