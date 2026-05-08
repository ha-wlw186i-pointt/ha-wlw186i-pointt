"""Constants for the WLW186i Pointt integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    PERCENTAGE,
)

# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------
DOMAIN: Final = "wlw186i_pointt"
MANUFACTURER: Final = "Bosch Thermotechnology"

# ---------------------------------------------------------------------------
# OAuth2 / OpenID Connect — SingleKey-ID (Bosch SSO)
# ---------------------------------------------------------------------------
OIDC_AUTHORIZE_URL: Final = "https://singlekey-id.com/auth/connect/authorize"
OIDC_TOKEN_URL: Final = "https://singlekey-id.com/auth/connect/token"
CLIENT_ID: Final = "762162C0-FA2D-4540-AE66-6489F189FADC"
REDIRECT_URI: Final = "com.buderus.tt.dashtt://app/login"
STYLE_ID: Final = "tt_bud"
SCOPES: Final[list[str]] = [
    "openid",
    "email",
    "profile",
    "offline_access",
    "pointt.gateway.claiming",
    "pointt.gateway.removal",
    "pointt.gateway.list",
    "pointt.gateway.users",
    "pointt.gateway.resource.dashapp",
    "pointt.castt.flow.token-exchange",
    "bacon",
    "hcc.tariff.read",
]

# ---------------------------------------------------------------------------
# Pointt API
# ---------------------------------------------------------------------------
POINTT_BASE_URL: Final = (
    "https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1/"
)

# Bulk API tuning for K40RF wireless gateway
# Conservative timing: the K40RF is a wireless gateway with limited bandwidth.
# Only paths for enabled entities are fetched, keeping batch count low.
BULK_BATCH_SIZE: Final = 4
BULK_INTER_BATCH_DELAY: Final = 10  # seconds between batches
BULK_RETRY_DELAY: Final = 60  # seconds before retrying 504 paths

# Gateway type preferences (in order)
PREFERRED_GATEWAY_TYPES: Final = ("k40", "connectkey", "icom")

# ---------------------------------------------------------------------------
# Config / options keys
# ---------------------------------------------------------------------------
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_EXPIRES_AT: Final = "expires_at"
CONF_TOKEN_TYPE: Final = "token_type"
CONF_GATEWAY_ID: Final = "gateway_id"
CONF_GATEWAY_TYPE: Final = "gateway_type"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 600  # 10 minutes
MIN_SCAN_INTERVAL: Final = 300  # 5 minutes
MAX_SCAN_INTERVAL: Final = 3600  # 60 minutes


# ---------------------------------------------------------------------------
# Resource paths — grouped by logical section
# ---------------------------------------------------------------------------
RESOURCE_PATHS_SYSTEM: Final[list[str]] = [
    "/system/sensors/temperatures/outdoor_t1",
    "/system/awayMode/enabled",
    "/system/healthStatus",
    "/system/brand",
    "/system/bus",
    "/system/appliance/model",
]

RESOURCE_PATHS_HEAT_SOURCE: Final[list[str]] = [
    "/heatSources/hs1/type",
    "/heatSources/hs1/heatPumpType",
    "/heatSources/compressor/status",
    "/heatSources/actualModulation",
    "/heatSources/actualSupplyTemperature",
    "/heatSources/returnTemperature",
    "/heatSources/systemPressure",
    "/heatSources/actualHeatDemand",
    "/heatSources/numberOfStarts",
    "/heatSources/workingTime/totalSystem",
    "/heatSources/Source/eHeater/status",
    "/heatSources/additionalHeater/operationMode",
    "/heatSources/hs1/defrostActive",
    "/heatSources/emStatus",
    "/heatSources/pvContactState",
]

RESOURCE_PATHS_HC1: Final[list[str]] = [
    "/heatingCircuits/hc1/operationMode",
    "/heatingCircuits/hc1/currentRoomSetpoint",
    "/heatingCircuits/hc1/roomtemperature",
    "/heatingCircuits/hc1/actualSupplyTemperature",
    "/heatingCircuits/hc1/currentSuWiMode",
    "/heatingCircuits/hc1/overallStatus",
    "/heatingCircuits/hc1/controlType",
    "/heatingCircuits/hc1/heatingType",
    "/heatingCircuits/hc1/temperatureLevels",
]

RESOURCE_PATHS_DHW1: Final[list[str]] = [
    "/dhwCircuits/dhw1/actualTemp",
    "/dhwCircuits/dhw1/currentSetpoint",
    "/dhwCircuits/dhw1/operationMode",
    "/dhwCircuits/dhw1/overallStatus",
    "/dhwCircuits/dhw1/dhwType",
    "/dhwCircuits/dhw1/charge",
]

RESOURCE_PATHS_GATEWAY: Final[list[str]] = [
    "/gateway/uuid",
    "/gateway/versionFirmware",
    "/gateway/versionHardware",
    "/gateway/DateTime",
]

ALL_RESOURCE_PATHS: Final[list[str]] = (
    RESOURCE_PATHS_SYSTEM
    + RESOURCE_PATHS_HEAT_SOURCE
    + RESOURCE_PATHS_HC1
    + RESOURCE_PATHS_DHW1
    + RESOURCE_PATHS_GATEWAY
)

# Paths fetched once at startup and then cached for the lifetime of the
# integration (until the next HA restart).  Used by the DeviceInfo property.
DEVICE_INFO_PATHS: Final[list[str]] = [
    "/system/appliance/model",
    "/system/brand",
    "/gateway/versionFirmware",
    "/gateway/versionHardware",
]


# ---------------------------------------------------------------------------
# Sensor entity descriptions
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class WLW186iSensorEntityDescription(SensorEntityDescription):
    """Describe a WLW186i sensor entity."""

    resource_path: str
    value_type: str = "auto"  # auto, float, string, json


SENSOR_DESCRIPTIONS: Final[tuple[WLW186iSensorEntityDescription, ...]] = (
    # ── System ──────────────────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="outdoor_temperature",
        name="Outdoor Temperature",
        resource_path="/system/sensors/temperatures/outdoor_t1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="away_mode",
        name="Away Mode",
        resource_path="/system/awayMode/enabled",
        icon="mdi:home-export-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="health_status",
        name="Health Status",
        resource_path="/system/healthStatus",
        icon="mdi:heart-pulse",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="brand",
        name="Brand",
        resource_path="/system/brand",
        icon="mdi:tag",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="bus_type",
        name="Bus Type",
        resource_path="/system/bus",
        icon="mdi:bus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="appliance_model",
        name="Appliance Model",
        resource_path="/system/appliance/model",
        icon="mdi:information-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # ── Heat Source ─────────────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="heat_source_type",
        name="Heat Source Type",
        resource_path="/heatSources/hs1/type",
        icon="mdi:fire",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="heat_pump_type",
        name="Heat Pump Type",
        resource_path="/heatSources/hs1/heatPumpType",
        icon="mdi:heat-pump-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="compressor_status",
        name="Compressor",
        resource_path="/heatSources/compressor/status",
        icon="mdi:engine",
        entity_registry_enabled_default=False,
    ),
    # ── Enabled by default ─────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="modulation",
        name="Modulation",
        resource_path="/heatSources/actualModulation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent",
    ),
    WLW186iSensorEntityDescription(
        key="hs_supply_temperature",
        name="Supply Temperature",
        resource_path="/heatSources/actualSupplyTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WLW186iSensorEntityDescription(
        key="return_temperature",
        name="Return Temperature",
        resource_path="/heatSources/returnTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── Heat Source (continued, disabled by default) ────────────────────
    WLW186iSensorEntityDescription(
        key="system_pressure",
        name="System Pressure",
        resource_path="/heatSources/systemPressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="heat_demand",
        name="Heat Demand",
        resource_path="/heatSources/actualHeatDemand",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fire",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="compressor_starts",
        name="Compressor Starts",
        resource_path="/heatSources/numberOfStarts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="total_working_time",
        name="Total Working Time",
        resource_path="/heatSources/workingTime/totalSystem",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="eheater_status",
        name="E-Heater",
        resource_path="/heatSources/Source/eHeater/status",
        icon="mdi:radiator",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="additional_heater_mode",
        name="Additional Heater Mode",
        resource_path="/heatSources/additionalHeater/operationMode",
        icon="mdi:radiator",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="defrost_active",
        name="Defrost Active",
        resource_path="/heatSources/hs1/defrostActive",
        icon="mdi:snowflake-melt",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="em_status",
        name="EM Status",
        resource_path="/heatSources/emStatus",
        icon="mdi:flash",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="pv_contact",
        name="PV Contact",
        resource_path="/heatSources/pvContactState",
        icon="mdi:solar-power",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # ── Heating Circuit 1 ──────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="hc1_operation_mode",
        name="HC1 Operation Mode",
        resource_path="/heatingCircuits/hc1/operationMode",
        icon="mdi:thermostat",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_room_setpoint",
        name="HC1 Room Setpoint",
        resource_path="/heatingCircuits/hc1/currentRoomSetpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermostat",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_room_temperature",
        name="HC1 Room Temperature",
        resource_path="/heatingCircuits/hc1/roomtemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_supply_temperature",
        name="HC1 Supply Temperature",
        resource_path="/heatingCircuits/hc1/actualSupplyTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_summer_winter_mode",
        name="HC1 Summer/Winter Mode",
        resource_path="/heatingCircuits/hc1/currentSuWiMode",
        icon="mdi:sun-snowflake-variant",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_overall_status",
        name="HC1 Overall Status",
        resource_path="/heatingCircuits/hc1/overallStatus",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_control_type",
        name="HC1 Control Type",
        resource_path="/heatingCircuits/hc1/controlType",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_heating_type",
        name="HC1 Heating Type",
        resource_path="/heatingCircuits/hc1/heatingType",
        icon="mdi:radiator",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="hc1_temperature_levels",
        name="HC1 Temperature Levels",
        resource_path="/heatingCircuits/hc1/temperatureLevels",
        icon="mdi:thermometer-lines",
        value_type="json",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # ── DHW (Domestic Hot Water) ───────────────────────────────────────
    # ── Enabled by default ─────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="dhw_temperature",
        name="DHW Temperature",
        resource_path="/dhwCircuits/dhw1/actualTemp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── DHW (continued, disabled by default) ───────────────────────────
    WLW186iSensorEntityDescription(
        key="dhw_setpoint",
        name="DHW Setpoint",
        resource_path="/dhwCircuits/dhw1/currentSetpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:thermostat",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="dhw_operation_mode",
        name="DHW Operation Mode",
        resource_path="/dhwCircuits/dhw1/operationMode",
        icon="mdi:water-boiler",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="dhw_overall_status",
        name="DHW Overall Status",
        resource_path="/dhwCircuits/dhw1/overallStatus",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="dhw_type",
        name="DHW Type",
        resource_path="/dhwCircuits/dhw1/dhwType",
        icon="mdi:water-boiler",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="dhw_charge",
        name="DHW Charging",
        resource_path="/dhwCircuits/dhw1/charge",
        icon="mdi:water-boiler-alert",
        entity_registry_enabled_default=False,
    ),
    # ── Gateway ────────────────────────────────────────────────────────
    WLW186iSensorEntityDescription(
        key="gateway_uuid",
        name="Gateway UUID",
        resource_path="/gateway/uuid",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="gateway_firmware",
        name="Gateway Firmware",
        resource_path="/gateway/versionFirmware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="gateway_hardware",
        name="Gateway Hardware",
        resource_path="/gateway/versionHardware",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WLW186iSensorEntityDescription(
        key="gateway_datetime",
        name="Gateway Date/Time",
        resource_path="/gateway/DateTime",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Build a lookup from resource_path -> description for quick access
SENSOR_DESCRIPTION_BY_PATH: Final[dict[str, WLW186iSensorEntityDescription]] = {
    desc.resource_path: desc for desc in SENSOR_DESCRIPTIONS
}
