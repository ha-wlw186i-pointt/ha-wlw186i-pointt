"""DataUpdateCoordinator for the WLW186i Pointt integration.

Polls the Bosch Pointt bulk API at a configurable interval and provides
the latest resource data to all sensor entities.

Only resource paths for **enabled** entities are fetched.  Device-info
values (model, brand, firmware, hardware version) are fetched once at
startup and cached for the lifetime of the integration — they only
refresh on the next HA restart.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PointtApiClient, PointtAuthError, PointtTokenExpiredError, PointtApiError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_GATEWAY_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_INFO_PATHS,
    DOMAIN,
    SENSOR_DESCRIPTIONS,
)

_LOGGER = logging.getLogger(__name__)

# Paths for sensor descriptions that are enabled by default.
# Used as a fallback when the entity registry has not been populated yet
# (i.e. during the very first refresh, before async_forward_entry_setups).
_DEFAULT_ENABLED_PATHS: list[str] = [
    desc.resource_path
    for desc in SENSOR_DESCRIPTIONS
    if desc.entity_registry_enabled_default is not False
]


class WLW186iPointtCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the Pointt bulk API.

    ``self.data`` is a dict mapping resource path (str) to its API payload
    (dict) or ``None`` (path not available on this device).
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: PointtApiClient,
    ) -> None:
        interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self._gateway_id: str = config_entry.data[CONF_GATEWAY_ID]

        # Cache for device-info values (model, brand, firmware, hw version).
        # Populated on the first successful fetch, then re-used for the
        # lifetime of the integration (refreshed on next HA restart).
        self._device_info_cache: dict[str, Any] = {}

        # Register callback so refreshed tokens are persisted in config entry
        client.on_token_refresh = self._async_on_token_refresh

    # -- Token persistence --------------------------------------------------

    async def _async_on_token_refresh(self, tokens: dict[str, Any]) -> None:
        """Persist refreshed tokens into the config entry."""
        try:
            new_data = {**self.config_entry.data}
            new_data[CONF_ACCESS_TOKEN] = tokens["access_token"]
            new_data[CONF_REFRESH_TOKEN] = (
                tokens.get("refresh_token") or new_data[CONF_REFRESH_TOKEN]
            )
            new_data[CONF_EXPIRES_AT] = tokens.get("expires_at", 0)
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            _LOGGER.debug("Persisted refreshed tokens to config entry")
        except Exception:
            _LOGGER.exception(
                "Failed to persist refreshed tokens — in-memory tokens are "
                "still valid but will be lost on HA restart"
            )

    # -- Path selection -----------------------------------------------------

    def _get_active_resource_paths(self) -> list[str]:
        """Return the list of resource paths that should be fetched.

        Includes paths for all *enabled* sensor entities, plus the
        device-info paths when they haven't been cached yet (first poll).

        Falls back to the default-enabled sensor set when the entity
        registry has no entries yet (first refresh during setup).
        """
        registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        )

        if not entries:
            # Entity registry not yet populated (first refresh)
            sensor_paths = list(_DEFAULT_ENABLED_PATHS)
        else:
            gateway_prefix = f"{self._gateway_id}_"
            key_to_path = {
                desc.key: desc.resource_path for desc in SENSOR_DESCRIPTIONS
            }
            sensor_paths = []
            for entry in entries:
                if entry.disabled:
                    continue
                uid = entry.unique_id or ""
                if uid.startswith(gateway_prefix):
                    key = uid[len(gateway_prefix):]
                    path = key_to_path.get(key)
                    if path:
                        sensor_paths.append(path)

        # Include device-info paths only until they've been cached
        extra_paths: list[str] = []
        if not self._device_info_cache:
            extra_paths = list(DEVICE_INFO_PATHS)

        # De-duplicate while preserving order
        all_paths = list(dict.fromkeys(sensor_paths + extra_paths))
        return all_paths

    # -- Data fetching ------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch resource paths for enabled entities via the bulk API."""
        paths = self._get_active_resource_paths()
        _LOGGER.debug("Fetching %d resource paths", len(paths))

        try:
            data = await self.client.async_bulk_get(
                self._gateway_id, paths,
            )
        except PointtTokenExpiredError as err:
            # Refresh token is permanently expired/revoked — the user must
            # re-authenticate.  Triggers the HA reauth flow.
            raise ConfigEntryAuthFailed(str(err)) from err
        except PointtAuthError as err:
            # Transient auth failure (server error, network issue) — the API
            # client already retried internally.  Raise UpdateFailed so the
            # coordinator retries at the next scan interval instead of
            # immediately forcing a re-login.
            raise UpdateFailed(
                f"Authentication error (will retry next interval): {err}"
            ) from err
        except PointtApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        ok = sum(
            1
            for v in data.values()
            if v is not None and not (isinstance(v, dict) and v.get("_error"))
        )
        _LOGGER.debug("Bulk update complete: %d/%d paths OK", ok, len(paths))

        # Cache device-info values once all paths have been fetched without
        # errors.  A value of None (404) is also accepted — it means the
        # path doesn't exist on this device.
        if not self._device_info_cache:
            got_all = all(p in data for p in DEVICE_INFO_PATHS)
            has_no_errors = all(
                not (isinstance(data.get(p), dict) and data[p].get("_error"))
                for p in DEVICE_INFO_PATHS
                if p in data
            )
            if got_all and has_no_errors:
                self._device_info_cache = {
                    p: data[p] for p in DEVICE_INFO_PATHS
                }
                _LOGGER.debug(
                    "Device info cached (%d paths) — will not re-fetch "
                    "until next HA restart",
                    len(self._device_info_cache),
                )

        # Merge: start from previous data (preserves paths no longer
        # fetched), overlay fresh API results, then inject the device-info
        # cache so those values are always present.
        merged: dict[str, Any] = {}
        if self.data:
            merged.update(self.data)
        merged.update(data)
        merged.update(self._device_info_cache)

        return merged

    # -- Options update -----------------------------------------------------

    def update_interval_from_options(self) -> None:
        """Re-read the scan interval from options (called on options update)."""
        interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        self.update_interval = timedelta(seconds=interval)
        _LOGGER.info("Update interval changed to %ds", interval)
