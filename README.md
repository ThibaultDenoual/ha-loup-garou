# 🐺 Loup-Garou pour Home Assistant

<div align="center">

**Turn your smart home into a full Werewolf game master.**  
Lights flicker at nightfall. TTS narrates every elimination. One phone, passed around the table — that's all it takes.

[![Tests](https://github.com/ThibaultDenoual/ha-loup-garou/actions/workflows/tests.yml/badge.svg)](https://github.com/ThibaultDenoual/ha-loup-garou/actions/workflows/tests.yml)
[![Validate](https://github.com/ThibaultDenoual/ha-loup-garou/actions/workflows/validate.yml/badge.svg)](https://github.com/ThibaultDenoual/ha-loup-garou/actions/workflows/validate.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2024.1-blue.svg)](https://www.home-assistant.io)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/ThibaultDenoual/ha-loup-garou?sort=semver)](https://github.com/ThibaultDenoual/ha-loup-garou/releases)

[Installation](#-installation) · [Configuration](#%EF%B8%8F-configuration) · [Roles](#-roles) · [Development](#-development)

</div>

---

## What is this?

**Loup-Garou** (Werewolf) is a social deduction game. Villagers try to uncover hidden werewolves; werewolves try to eliminate the village before being caught.

This Home Assistant integration turns your lights and speakers into an immersive game master:

- 🌑 **Lights dim to deep red** when night falls
- 🔊 **TTS narrates** every death, vote result, and game event
- 📱 **One-phone UI** — a web app you pass between players; no app install required
- 🎭 **12 playable roles** with full night-action logic
- 🌍 **French & English** — language auto-follows your HA locale
- 🏠 **HA-optional** — the game engine runs standalone without Home Assistant

---

## ✨ Features

| Feature | Details |
|---|---|
| **Immersive atmosphere** | Smart lights + TTS narration via your HA speaker |
| **12 roles** | Villager, Werewolf, Seer, Hunter, Elder, Scapegoat, Little Girl, Witch, Cupid, Alpha Wolf, Minion, Sheriff |
| **Role reveal flow** | Tap-to-reveal on each player's turn — no accidental spoilers |
| **Sheriff election** | Double-vote mechanic fully supported |
| **Cupid's lovers** | Linked lovers die together — chain eliminations handled correctly |
| **Witch potions** | Save + poison, once each, with pending-kill preview |
| **Alpha Wolf conversion** | Convert a villager mid-game |
| **Hunter's last shot** | Drag someone along in death |
| **Scapegoat** | Dies on vote ties so the game never stalls |
| **Bilingual** | Full FR and EN locale files |
| **Zero app install** | Game UI is served directly from HA at `/local/loup_garou/game/` |

---

## 📦 Installation

### Via HACS (recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/ThibaultDenoual/ha-loup-garou` as an **Integration**.
4. Search for **Loup Garou** and install it.
5. Restart Home Assistant.

### Manual

1. Download the [latest release](https://github.com/ThibaultDenoual/ha-loup-garou/releases/latest).
2. Copy `custom_components/loup_garou/` into your HA `config/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration

After restarting, add the integration from **Settings → Devices & Services → Add Integration → Loup Garou**.

You will be asked to configure:

| Option | Description |
|---|---|
| **Speaker** | The `media_player` entity used for TTS narration |
| **Lights** | Light entities to control during day/night atmosphere |
| **Language** | `fr` (French) or `en` (English) |

Once configured, open the game UI on any device connected to your local network:

```
http://<your-ha-ip>:8123/local/loup_garou/game/
```

> **Tip:** Bookmark this URL and set your screen to stay on. The phone gets passed between players — no accounts, no QR codes.

---

## 🎭 Roles

All 12 roles are included and fully playable. You pick which roles to include when setting up each game.

| Role | Team | Night action | Ability |
|---|---|---|---|
| 🧑‍🌾 **Villager** | Village | — | Votes during the day to eliminate suspects |
| 🐺 **Werewolf** | Wolves | Vote to kill | Devours one villager per night |
| 🔮 **Seer** | Village | Investigate | Learns the true role of one player each night |
| 🏹 **Hunter** | Village | On death | When eliminated, takes one player with them |
| 🧓 **Elder** | Village | — | Survives the first wolf attack; the second is fatal |
| 🐐 **Scapegoat** | Village | — | Dies instead of no-one when the vote is tied |
| 👧 **Little Girl** | Village | — | Can peek during the wolf phase — risky! |
| 🧙 **Witch** | Village | Save + poison | Two one-use potions: heal tonight's victim or poison anyone |
| 💘 **Cupid** | Village | Night 1 only | Links two lovers; if one dies, so does the other |
| 🐺👑 **Alpha Wolf** | Wolves | Convert | Once per game, converts a villager into a werewolf |
| 🤫 **Minion** | Wolves | — | Knows the wolves' identity; wins if wolves win |
| ⭐ **Sheriff** | Village | — | Elected; their vote counts double |

### Win conditions

- **Wolves win** when they equal or outnumber the remaining villagers.
- **Village wins** when all werewolves are eliminated.
- **Lovers win** when only the two linked lovers survive — regardless of their teams.

---

## 🏗️ Architecture

```
Browser (phone)  ──▶  game_server.py  (WebSocket / aiohttp)
                            │
                       game_engine.py  (pure Python, zero HA imports)
                            │ events
                       loup_garou/
                       ├── __init__.py   — wires engine + server + atmosphere
                       └── atmosphere.py — engine events → lights + TTS
```

The game engine is **completely decoupled from Home Assistant**. You can run it standalone for development or testing:

```bash
# Standalone web UI (no HA required)
python run_devserver.py --port 8099

# Console-only mode
python run_console.py
```

---

## 🛠️ Development

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Run all tests
pytest tests/unit
pytest tests/e2e

# Coverage report
pytest --cov=custom_components/loup_garou --cov-report=term-missing
```

The test suite uses a real `GameEngine` with real role plugins — only external I/O (HA services, WebSocket clients) is mocked.

---

## 🤝 Contributing

Pull requests are welcome! Before adding a new role:

1. Write `tests/unit/roles/test_<role>.py` first (TDD).
2. Implement `roles/impl/<role>.py` as a `BaseRole` subclass.
3. Add locale keys to both `locales/fr.json` and `locales/en.json`.

No changes to `game_engine.py` should be needed for a new role — the engine is role-agnostic.

Please open an issue before starting large changes.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
