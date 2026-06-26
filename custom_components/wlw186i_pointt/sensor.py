"""Sensor platform for the WLW186i Pointt integration.

Creates one sensor entity per resource path defined in ``const.py``.
All entities are backed by the shared ``WLW186iPointtCoordinator``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TYPE,
    DOMAIN,
    MANUFACTURER,
    SENSOR_DESCRIPTIONS,
    WLW186iSensorEntityDescription,
)
from .coordinator import WLW186iPointtCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLW186i Pointt sensors from a config entry."""
    coordinator: WLW186iPointtCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[WLW186iSensor] = [
        WLW186iSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class WLW186iSensor(CoordinatorEntity[WLW186iPointtCoordinator], SensorEntity):
    """Representation of a single WLW186i heat pump sensor."""

    entity_description: WLW186iSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WLW186iPointtCoordinator,
        description: WLW186iSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description

        gateway_id = coordinator.config_entry.data[CONF_GATEWAY_ID]
        self._attr_unique_id = f"{gateway_id}_{description.key}"

    # -- Device info --------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so all sensors are grouped under one device."""
        entry_data = self.coordinator.config_entry.data
        gateway_id = entry_data[CONF_GATEWAY_ID]
        gateway_type = entry_data.get(CONF_GATEWAY_TYPE, "unknown")

        # Try to extract model and firmware from coordinator data
        data = self.coordinator.data or {}
        model = _extract_string(data.get("/system/appliance/model"))
        firmware = _extract_string(data.get("/gateway/versionFirmware"))
        hw_version = _extract_string(data.get("/gateway/versionHardware"))

        return DeviceInfo(
            identifiers={(DOMAIN, gateway_id)},
            name=f"WLW186i ({gateway_id})",
            manufacturer=MANUFACTURER,
            model=model or f"ConnectKey {gateway_type.upper()}",
            sw_version=firmware,
            hw_version=hw_version,
        )

    # -- State --------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True if the coordinator has data and this path didn't error."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        payload = self.coordinator.data.get(self.entity_description.resource_path)
        # None means 404 (path not on device) — still "available" but unknown
        if payload is not None and isinstance(payload, dict) and payload.get("_error"):
            return False
        return True

    @property
    def native_value(self) -> Any | None:
        """Return the current value extracted from the API payload."""
        if self.coordinator.data is None:
            return None

        payload = self.coordinator.data.get(self.entity_description.resource_path)
        if payload is None:
            return None
        if isinstance(payload, dict) and payload.get("_error"):
            return None

        return _extract_value(payload, self.entity_description.value_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw API payload type and writeable flag as attributes."""
        if self.coordinator.data is None:
            return None

        payload = self.coordinator.data.get(self.entity_description.resource_path)
        if not isinstance(payload, dict) or payload.get("_error"):
            return None

        attrs: dict[str, Any] = {}
        if "type" in payload:
            attrs["api_type"] = payload["type"]
        if "writeable" in payload:
            attrs["writeable"] = payload["writeable"]
        if "unitOfMeasure" in payload:
            attrs["api_unit"] = payload["unitOfMeasure"]
        if "allowedValues" in payload:
            attrs["allowed_values"] = payload["allowedValues"]
        if "minValue" in payload:
            attrs["min_value"] = payload["minValue"]
        if "maxValue" in payload:
            attrs["max_value"] = payload["maxValue"]

        return attrs if attrs else None


# ---------------------------------------------------------------------------
# Value extraction helpers
# ---------------------------------------------------------------------------

def _extract_value(payload: dict[str, Any], value_type: str) -> Any | None:
    """Extract a display value from a Pointt API resource payload.

    The API returns polymorphic types (floatValue, stringValue, refEnum, etc.).
    """
    if not isinstance(payload, dict):
        return str(payload) if payload is not None else None

    rtype = payload.get("type", "")

    # Explicit JSON serialisation requested
    if value_type == "json":
        # Return a compact JSON representation
        filtered = {k: v for k, v in payload.items() if k not in ("type", "id")}
        return json.dumps(filtered, separators=(",", ":"))

    # Auto-detect from API type
    if rtype in ("floatValue", "emonValue"):
        return payload.get("value")

    if rtype == "stringValue":
        return payload.get("value")

    if rtype == "refEnum":
        refs = payload.get("references", [])
        return ", ".join(r.get("id", "?") for r in refs) if refs else None

    if rtype == "arrayData":
        vals = payload.get("values", [])
        return ", ".join(str(v) for v in vals) if vals else None

    if rtype == "systeminfo":
        # Return a meaningful sub-field or compact JSON
        return json.dumps(payload, separators=(",", ":"))

    # Fallback: if there's a "value" key, use it
    if "value" in payload:
        return payload["value"]

    # Last resort: compact JSON
    return json.dumps(payload, separators=(",", ":"))


def _extract_string(payload: Any) -> str | None:
    """Extract a plain string value from a payload (for device info etc.)."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        if payload.get("_error"):
            return None
        return payload.get("value")
    return str(payload)
