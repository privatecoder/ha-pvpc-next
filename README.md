# PVPC Next

PVPC Next is a custom Home Assistant integration that retrieves the Spanish PVPC electricity prices by hour and exposes them as sensors for automations, dashboards, and energy views.

---

## What's new vs the integrated version

- New PVPC sensors that expose key attributes as standalone entities (e.g., current period, next period, min/max price, price level, and time to better price).
- Calculated sensors for price levels (current, next and next better price).
- National holidays handled via the `holidays` library (no more hardcoded yearly tables).
- General bugfixes, hardening, and stability improvements.
- Code quality pass with pylint score **10/10**.

---

## Features

- Hourly PVPC prices for Spain.
- Sensors for current price and detailed price attributes.
- Current Price Level: a relative label based on how the current price compares to the daily range (very cheap to very expensive).
- Better Price Level: the same relative label applied to the next cheaper price ahead, if available.
- Next Price: the next hourly price after the current hour, plus a matching Next Price Level.
- Works with automations and energy dashboards.
- Lightweight, async, and HA friendly.

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
