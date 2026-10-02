"""Unit tests for the get_entities light payload (entity picker backend)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from loup_garou.loup_garou import describe_light


def _hass_with_state(entity_id: str, friendly_name: str | None, state: str = "on"):
    hass = MagicMock()
    attrs = {} if friendly_name is None else {"friendly_name": friendly_name}
    hass.states.get.return_value = SimpleNamespace(
        entity_id=entity_id, attributes=attrs, state=state
    )
    return hass


def test_describe_light_uses_friendly_name():
    hass = _hass_with_state("light.salon", "Salon")
    with patch(
        "homeassistant.helpers.entity_registry.async_get", side_effect=Exception("no reg")
    ), patch(
        "homeassistant.helpers.area_registry.async_get", side_effect=Exception("no reg")
    ):
        info = describe_light(hass, "light.salon")
    assert info == {
        "entity_id": "light.salon",
        "name": "Salon",
        "area": None,
        "state": "on",
    }


def test_describe_light_falls_back_to_entity_id():
    hass = _hass_with_state("light.cave", None)
    with patch(
        "homeassistant.helpers.entity_registry.async_get", side_effect=Exception("no reg")
    ), patch(
        "homeassistant.helpers.area_registry.async_get", side_effect=Exception("no reg")
    ):
        info = describe_light(hass, "light.cave")
    assert info["name"] == "light.cave"
    assert info["area"] is None


def test_describe_light_missing_state_never_raises():
    hass = MagicMock()
    hass.states.get.return_value = None
    with patch(
        "homeassistant.helpers.entity_registry.async_get", side_effect=Exception("no reg")
    ), patch(
        "homeassistant.helpers.area_registry.async_get", side_effect=Exception("no reg")
    ):
        info = describe_light(hass, "light.ghost")
    assert info == {
        "entity_id": "light.ghost",
        "name": "light.ghost",
        "area": None,
        "state": None,
    }


def test_describe_light_resolves_area_name():
    hass = _hass_with_state("light.salon", "Salon")
    ent_reg = MagicMock()
    ent_reg.async_get.return_value = SimpleNamespace(area_id="area-1")
    ar = MagicMock()
    ar.async_get.return_value = SimpleNamespace(name="Salon")
    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=ent_reg
    ), patch("homeassistant.helpers.area_registry.async_get", return_value=ar):
        info = describe_light(hass, "light.salon")
    assert info["area"] == "Salon"


def test_describe_light_marks_unavailable_state():
    hass = _hass_with_state("light.hs", "HS", state="unavailable")
    with patch(
        "homeassistant.helpers.entity_registry.async_get", side_effect=Exception("no reg")
    ), patch(
        "homeassistant.helpers.area_registry.async_get", side_effect=Exception("no reg")
    ):
        info = describe_light(hass, "light.hs")
    assert info["state"] == "unavailable"
