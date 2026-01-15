# PVPC Next

PVPC Next is a custom Home Assistant integration that retrieves the Spanish PVPC electricity prices by hour and exposes them as sensors for automations, dashboards, and energy views.

---

## What's new vs the integrated version

- New PVPC sensors that expose key attributes as standalone entities (e.g., current period, next period, min/max price, price level, and time to better price).
- Calculated sensors for price levels (current, next and next better price).
- Configurable Better Price Target to pick the next neutral/cheap/very cheap window.
- National holidays handled via the `holidays` library (no more hardcoded yearly tables).
- General bugfixes, hardening, and stability improvements.
- Code quality pass with pylint score **10/10**.

---

## Features

- Hourly PVPC prices for Spain.
- Sensors for current price and detailed price attributes.
- Current Price Level, Better Price Level, and Next Price Level sensors.
- Better Price, Better Price In, and Next Price sensors.
- Configurable Better Price Target for those Better Price sensors.
- Works with automations and energy dashboards.
- Lightweight, async, and HA friendly.

---

## Configuration & behavior

- Price levels are relative to each day's price range (very cheap to very expensive).
- Better Price Target options: neutral, cheap, very cheap. Better Price, Better Price In, and Better Price Level point to the next hour that meets the target or better.
- Change Better Price Target via **Settings -> Devices & Integrations -> PVPC Next -> Configure**.
- If no target is found, Better Price sensors show Unknown; if price data is missing, they show Unavailable.
- The old "PVPC" sensor is now "Current Price" and keeps the remaining attributes that are not exposed as separate sensors.

---

## Languages

- English
- Spanish
- Catalan
- German

---

## Installation (HACS)

1. Open **HACS -> Integrations** in Home Assistant.
2. Click the menu (...) -> **Custom repositories**.
3. Add this repository:
   - **URL:** `https://github.com/privatecoder/ha-pvpc-next`
   - **Category:** `Integration`
4. Search for **PVPC Next** and click **Install**.
5. Restart Home Assistant.
6. Add the integration via **Settings -> Devices & Integrations**.

---

## License

MIT License. See the [LICENSE](LICENSE) file.
