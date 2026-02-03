# PVPC Next

PVPC Next is a custom Home Assistant integration that retrieves the Spanish PVPC electricity prices by hour and exposes them as sensors for automations, dashboards, and energy views.

Official PVPC prices: https://www.esios.ree.es/en/pvpc

---

## What's new vs the integrated version

- New PVPC sensors that expose key attributes as standalone entities (e.g., tariff, current/next period, hours to next period, min/max price, price levels, better prices ahead, and time to better price).
- Calculated sensors for price levels (current, next and next best price).
- Configurable Better Price Target (default: very cheap) to pick the next neutral/cheap/very cheap window; if none match, it falls back to the lowest available future price.
- National holidays handled via a forked `aiopvpc` library that integrates the `holidays` dataset (no more hardcoded yearly tables).
- Configurable holiday source for tariff-period holiday handling (`python-holidays` or `csv`).
- General bugfixes, hardening, and stability improvements.

---

## Features

- Hourly PVPC prices for Spain.
- Sensors for current price and detailed price attributes.
- Current Price Level, Next Best Level, and Next Price Level sensors.
- Next Best Price, Next Best In, Next Price, and Next Price In sensors.
- Configurable Better Price Target for the Next Best sensors (default: very cheap, with a fallback to the lowest available future price if no target match).
- Tariff selection by geographic zone and contracted power (P1 and P3).
- Diagnostic sensors for API source and data IDs (PVPC, and optional private API data IDs).
- Works with automations and energy dashboards.
- Lightweight, async, and HA friendly.

---

## Sensors

- Price sensors: Current Price; private API adds Injection Price, MAG tax, and OMIE Price (MAG tax and OMIE Price are disabled by default).
- Attribute sensors: Tariff, Current Period, Current Power Period, Next Power Period, Next Power Period In, Next Period, Next Period In, Available Power, Min Price, Max Price, Avg. Price Today, Next Best Price, Next Price, Next Price In, Next Best In, Better Prices Ahead, Current Price Level, Next Price Level, Next Best Level.
- Diagnostic sensors: PVPC Data ID, API Source; private API adds Injection Price Data ID, MAG Tax Data ID, and OMIE Price Data ID (MAG/OMIE data IDs are disabled by default).

---

## Configuration & behavior

- Price levels are relative to each day's price range (very cheap to very expensive).
- Better Price Target thresholds use `price_ratio` buckets: neutral <= 0.60, cheap <= 0.40, very cheap <= 0.20 (ratios are relative to each day's min/max range).
- Better Price Target options: neutral, cheap, very cheap (default: very cheap). Next Best Price, Next Best In, and Next Best Level point to the next hour that meets the target or better, and fall back to the lowest available future price if none match.
- Price periods (P1/P2/P3) and power periods (P1/P3) follow different rules; see the Endesa overview [here](https://www.endesa.com/es/blog/blog-de-endesa/horarios-luz-valle-punta-llano) and EnergiaXXI notes [here](https://www.energiaxxi.com/es/facturas/cambios-factura-luz).
- Price periods for "2.0TD Península / Baleares / Canarias": weekdays P1 10:00-14:00 and 18:00-22:00; P2 08:00-10:00, 14:00-18:00, 22:00-00:00; P3 00:00-08:00; weekends and national holidays are P3 all day.
- Price periods for "2.0TD Ceuta / Melilla": weekdays P1 11:00-15:00 and 19:00-23:00; P2 08:00-11:00, 15:00-19:00, 23:00-00:00; P3 00:00-08:00; weekends and national holidays are P3 all day.
- Power periods (both regions): weekdays P1 08:00-00:00 and P3 00:00-08:00; weekends and national holidays are P3 all day (no P2 for power).
- Tariff selection controls the geographic zone (Península/Baleares/Canarias vs Ceuta/Melilla).
- Contracted power (P1 and P3) is used to compute the Available Power sensor (in W).
- Change Better Price Target via **Settings -> Devices & Integrations -> PVPC Next -> Configure**.
- Update frequency for Next Price In, Next Best In, Next Period In, and Next Power Period In can be set to disabled/hourly/every minute in **Configure**; disabled will turn the entity off in the registry.
- Holiday source can be set in **Configure**:
  - `csv` (default in aiopvpc `PVPCData` and CLI).
  - `python-holidays` (uses the Holidays python library).
- If no target is found, Next Best sensors show Unknown; if price data is missing, they show Unavailable.
- The old "PVPC" sensor is now "Current Price" and keeps the remaining attributes that are not exposed as separate sensors.
- Private API usage is optional and disabled by default; it requires an ESIOS API token and can be enabled in **Configure** (enables Injection Price, MAG tax and OMIE Price sensors).
- Recorder exclusions are configured in `configuration.yaml` (not from the integration), for example:

```yaml
recorder:
  exclude:
    entities:
      - sensor.esios_next_price_in
      - sensor.esios_next_best_in
      - sensor.esios_next_period_in
      - sensor.esios_next_power_period_in
```

---

## Notes

- The popular `danimart1991/pvpc-hourly-pricing-card` does not work with this integration, but there is a compatible fork available [here](https://github.com/privatecoder/pvpc-hourly-pricing-card).
- There is also an open issue requesting the original maintainer to merge these compatibility changes upstream.

---

## API endpoints

- Public (no token, PVPC only): `https://api.esios.ree.es/archives/70/download_json?locale=es&date=YYYY-MM-DD`
- Token-based: `https://api.esios.ree.es/indicators/{indicator_id}?start_date=YYYY-MM-DDT00:00&end_date=YYYY-MM-DDT23:59`
  - Indicators fetched with a token:
    - `1001` (PVPC)
    - `1739` (Injection)
    - `1900` (MAG tax)
    - `10211` (OMIE Price)
  - The API token is sent via headers (`x-api-key` and `Authorization`).

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
