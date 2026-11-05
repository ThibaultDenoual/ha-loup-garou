# localization Specification

## Purpose

Defines the French and English locale bundles shared by the browser UI, console, and
atmosphere: key structure, language selection, placeholder formatting, and the parity
guarantees enforced by tests.

## Requirements

### Requirement: Two shipped languages

The integration SHALL ship `locales/fr.json` and `locales/en.json`, served over HTTP at `/loup_garou/locales/<lang>.json`, each declaring `_meta.language` and `_meta.version`.

#### Scenario: English fetch
- **WHEN** a client requests `/loup_garou/locales/en.json`
- **THEN** the full English bundle SHALL be returned as JSON

### Requirement: Key namespaces

Locale bundles SHALL organize copy under `phase.*` (narration lines), `role.<id>.name|description|team` plus optional `wake`, `sleep`, `action_prompt`, and role-specific lines, `elimination.<cause>`, `article.male|female`, `ui.*` (game screens), `launcher.*` (hub screens), and `team.*` labels.

#### Scenario: Witch prompts
- **WHEN** the witch wakes
- **THEN** `role.witch.wake`, `role.witch.save_prompt`, and `role.witch.no_poison_potion` SHALL exist in both languages

### Requirement: Placeholder formatting

Translatable strings SHALL interpolate named placeholders (`{name}`, `{role}`, `{article}`, `{names}`, `{count}`, `{assigned}`, `{players}`, `{done}`, `{total}`), and lookups with unknown keys SHALL degrade to returning the key (UI) or empty string (atmosphere silence) rather than throwing.

#### Scenario: Day announcement
- **WHEN** narrating `phase.day.start_with_death` with a name and role
- **THEN** both placeholders SHALL be substituted in the spoken line

### Requirement: Cross-language parity

Every static translation key used by the shipped HTML/JS SHALL exist in both locale bundles; a unit test SHALL fail the build when a `data-i18n*` attribute or `t("...")` call references a missing key in either language.

#### Scenario: Orphan key
- **WHEN** a new `data-i18n="ui.foo.bar"` is added to HTML without a matching entry
- **THEN** the locale test SHALL fail listing the missing keys per language

### Requirement: Language selection

Runtime language SHALL come from the integration config (`language`, default `fr`, valid values `fr`/`en`); the browser UI SHALL load the document language and re-apply translations when the configured language arrives, while atmosphere and console SHALL read the locale file for their configured language at startup.

#### Scenario: Unsupported language value
- **WHEN** an unknown language code is requested
- **THEN** the client SHALL fall back to French
