# AGENTS.md

## What this is

Home Assistant custom integration (HACS-compatible) for Buderus/Bosch heat pumps (Logatherm WLW186i and similar) via the Bosch Pointt cloud API. Read-only sensor entities only. API was reverse-engineered from the MyBuderus 3.7.0 mobile app.

## Project layout

All integration code lives in `custom_components/wlw186i_pointt/`. There is no packaging, no build step, no tests, no CI.

| File | Role |
|------|------|
| `__init__.py` | Entry setup/teardown; creates API client + coordinator, forwards to `sensor` platform |
| `api.py` | `PointtApiClient` — aiohttp-based, handles OAuth2 token refresh and bulk API with batching/retry |
| `config_flow.py` | Two-step OAuth2 PKCE flow (user pastes redirect URL); also options flow for scan interval |
| `const.py` | All constants, OAuth2 config, resource paths, and all 40 `WLW186iSensorEntityDescription` definitions |
| `coordinator.py` | `DataUpdateCoordinator` — only fetches paths for enabled entities; caches device-info once |
| `sensor.py` | Creates one `WLW186iSensor` per description; extracts values from polymorphic API payloads |
| `diagnostics.py` | HA diagnostics dump with token redaction |

## Key architecture details

- **No external PyPI deps.** Only uses `aiohttp` and HA helper libraries provided by Home Assistant core.
- **OAuth2 PKCE auth** against `singlekey-id.com`. Redirect URI is a mobile app scheme (`com.buderus.tt.dashtt://app/login`), so the config flow asks the user to paste the redirect URL. Constants in `const.py`.
- **Bulk API batching** is critical: 4 paths per batch, 10s inter-batch delay, 60s retry delay for 504s. These conservative timings exist because the K40RF is a wireless gateway with limited bandwidth. Tuning constants are in `const.py` (`BULK_BATCH_SIZE`, `BULK_INTER_BATCH_DELAY`, `BULK_RETRY_DELAY`).
- **Selective fetching:** The coordinator only polls resource paths for entities the user has enabled, keeping batch count low.
- **Token persistence:** When the API client refreshes tokens, it calls back into the coordinator which persists them to the HA config entry. Losing a refresh token means the user must re-authenticate.
- **Sensor descriptions** are defined as a tuple in `const.py` (`SENSOR_DESCRIPTIONS`). Adding a sensor means adding its resource path to the appropriate `RESOURCE_PATHS_*` list and a corresponding `WLW186iSensorEntityDescription`.

## Development

- **Min HA version:** 2024.11.0
- **No tests, no linter config, no CI.** Validation is manual against a live HA instance.
- **Installation for dev:** Copy or symlink `custom_components/wlw186i_pointt/` into your HA `config/custom_components/` directory and restart HA.
- **Version** is in `custom_components/wlw186i_pointt/manifest.json`.

## Conventions

- All modules use `from __future__ import annotations`.
- Constants use `typing.Final` annotations.
- Sensor entity descriptions use a frozen dataclass (`WLW186iSensorEntityDescription`) extending HA's `SensorEntityDescription` with `resource_path` and `value_type` fields.
- 4 sensors enabled by default (modulation, supply temp, return temp, DHW temp); all others default to disabled (`entity_registry_enabled_default=False`).
- Four custom exceptions in `api.py`: `PointtApiError`, `PointtAuthError`, `PointtTokenExpiredError`, `PointtGatewayTimeoutError`. Only `PointtTokenExpiredError` triggers the HA reauth flow; other `PointtAuthError`s are treated as transient and retried.

## Gotchas

- The `value_type` field on sensor descriptions controls how `sensor.py` extracts the value from the API payload. Most are `"auto"` but `hc1_temperature_levels` uses `"json"` to serialize a nested dict.
- `DEVICE_INFO_PATHS` in `const.py` are fetched once at startup and cached. They overlap with some sensor resource paths but are fetched separately by the coordinator for device registry info.
- `strings.json` and `translations/en.json` must stay in sync (they are currently identical).
