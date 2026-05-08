"""Diagnostics support for the WLW186i Pointt integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .coordinator import WLW186iPointtCoordinator

REDACT_KEYS = {CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: WLW186iPointtCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Redact tokens from config entry data
    redacted_data = {
        k: ("**REDACTED**" if k in REDACT_KEYS else v)
        for k, v in entry.data.items()
    }

    return {
        "config_entry_data": redacted_data,
        "config_entry_options": dict(entry.options),
        "coordinator_data": coordinator.data,
    }
