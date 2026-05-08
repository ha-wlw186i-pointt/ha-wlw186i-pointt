# ha-wlw186i-pointt

A Home Assistant custom integration for monitoring Buderus/Bosch heat pumps
(Logatherm WLW186i and similar models) via the Bosch Pointt cloud API.

This integration communicates with heat pump gateways (ConnectKey K40RF, etc.)
through the same cloud API used by the official MyBuderus mobile app. It
provides read-only sensor entities for temperatures, pressures, operating
states, and diagnostic information.

## Requirements

- Home Assistant **2024.11** or newer
- A Bosch/Buderus heat pump with a **ConnectKey K40RF** (or compatible) gateway
- An active **MyBuderus / SingleKey-ID** account with the gateway paired

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** and select the three-dot menu in the top right.
3. Choose **Custom repositories**.
4. Add the URL of this repository and select **Integration** as the category.
5. Search for "WLW186i Pointt" in HACS and install it.
6. Restart Home Assistant.

### Manual

1. Copy the `custom_components/wlw186i_pointt/` directory into your Home
   Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **WLW186i Pointt**.
3. A link to the Bosch SingleKey-ID login page will be shown. Click it and
   log in with your MyBuderus credentials.
4. After login the browser will show a "can't reach this site" error — **this
   is expected**. The redirect goes to the app's custom URL scheme which
   doesn't work on a desktop browser.
5. Copy the **full URL** from the browser address bar (it starts with
   `com.buderus.tt.dashtt://...`) and paste it into the text field in Home
   Assistant.
6. The integration will automatically discover your gateway and create the
   sensor entities.

## Sensors

The integration exposes **40 sensor entities**. To minimise load on the
wireless K40RF gateway, only 4 are **enabled by default**. All others are
available in the entity registry and can be enabled individually via the
Home Assistant UI.

### Enabled by default

| Sensor | Unit | Description |
|--------|------|-------------|
| Modulation | % | Current heat pump modulation level |
| Supply Temperature | C | Heat source supply temperature |
| Return Temperature | C | Heat source return temperature |
| DHW Temperature | C | Domestic hot water actual temperature |

### Available (disabled by default)

#### System

| Sensor | Unit | Description |
|--------|------|-------------|
| Outdoor Temperature | C | Outdoor sensor T1 |
| Away Mode | | Away mode enabled/disabled |
| Health Status | | System health status |
| Brand | | Configured brand (diagnostic) |
| Bus Type | | Communication bus type (diagnostic) |
| Appliance Model | | Indoor unit model designation (diagnostic) |

#### Heat Source

| Sensor | Unit | Description |
|--------|------|-------------|
| Heat Source Type | | Type of heat source (diagnostic) |
| Heat Pump Type | | Heat pump variant (diagnostic) |
| Compressor | | Compressor on/off status |
| System Pressure | bar | Heating circuit system pressure |
| Heat Demand | % | Current heat demand |
| Compressor Starts | | Total compressor start count |
| Total Working Time | s | Total compressor running time |
| E-Heater | | Electric backup heater status |
| Additional Heater Mode | | Additional heater operation mode |
| Defrost Active | | Defrost cycle active |
| EM Status | | Energy manager status (diagnostic) |
| PV Contact | | Photovoltaic contact state (diagnostic) |

#### Heating Circuit 1

| Sensor | Unit | Description |
|--------|------|-------------|
| HC1 Operation Mode | | Heating circuit operation mode |
| HC1 Room Setpoint | C | Target room temperature |
| HC1 Room Temperature | C | Measured room temperature |
| HC1 Supply Temperature | C | Heating circuit supply temperature |
| HC1 Summer/Winter Mode | | Current summer/winter mode |
| HC1 Overall Status | | Heating circuit overall status |
| HC1 Control Type | | Control type (diagnostic) |
| HC1 Heating Type | | Heating type (diagnostic) |
| HC1 Temperature Levels | | Temperature level configuration (diagnostic) |

#### Domestic Hot Water

| Sensor | Unit | Description |
|--------|------|-------------|
| DHW Setpoint | C | Target hot water temperature |
| DHW Operation Mode | | Hot water operation mode |
| DHW Overall Status | | Hot water circuit status |
| DHW Type | | Hot water circuit type (diagnostic) |
| DHW Charging | | Hot water charging active |

#### Gateway

| Sensor | Unit | Description |
|--------|------|-------------|
| Gateway UUID | | Gateway unique identifier (diagnostic) |
| Gateway Firmware | | Current firmware version (diagnostic) |
| Gateway Hardware | | Hardware version (diagnostic) |
| Gateway Date/Time | | Gateway clock (diagnostic) |

## Configuration

After setup, the polling interval can be adjusted via the integration's
**Options** dialog:

- **Update interval**: 300 -- 3600 seconds (default: 600 / 10 minutes)

Device-info values (model, brand, firmware, hardware version) are fetched
once at startup and cached until the next Home Assistant restart.

## How it works

The integration uses the Bosch Pointt REST API — the same cloud backend the
MyBuderus mobile app connects to. Authentication is handled via OAuth2
Authorization Code + PKCE against Bosch's SingleKey-ID identity provider.

Data is retrieved using the Pointt **bulk API**, which fetches multiple
resource paths in a single request. To avoid overloading the wireless K40RF
gateway, requests are sent in small batches (4 paths per request) with a
10-second delay between batches.

All communication is **read-only**. The integration never writes to the heat
pump or changes any settings.

## Disclaimer

This is an **unofficial**, community-driven project. It is **not affiliated
with, endorsed by, or supported by** Bosch Thermotechnology, Buderus, or any
of their subsidiaries.

The integration was developed by reverse-engineering the MyBuderus mobile
application's network protocol. It relies on undocumented cloud APIs that may
change or become unavailable without notice.

**This software is provided "as is", without warranty of any kind, express or
implied.** Use it at your own risk. The authors accept no liability for any
damage, data loss, or other issues arising from the use of this software. See
the [LICENSE](LICENSE) file for details.

## License

This project is licensed under the [MIT License](LICENSE).
