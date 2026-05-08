"""The WLW186i Pointt integration.

Monitors Buderus/Bosch heat pumps via the Pointt cloud API using data
reverse-engineered from the MyBuderus 3.7.0 mobile app.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PointtApiClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import WLW186iPointtCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLW186i Pointt from a config entry."""
    session = async_get_clientsession(hass)

    client = PointtApiClient(
        session=session,
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        expires_at=entry.data.get(CONF_EXPIRES_AT, 0),
    )

    coordinator = WLW186iPointtCoordinator(hass, entry, client)

    # First refresh — raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options changes (scan interval)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — adjust the polling interval."""
    coordinator: WLW186iPointtCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_interval_from_options()
