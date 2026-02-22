# Changelog

## Unreleased

- No unreleased changes yet.

## 2.2.0

- Vendor `aiopvpc` and `pvpc_holidays` directly into the custom component to avoid conflicts with the built-in `pvpc_hourly_pricing` integration that pins a different `aiopvpc` version from PyPI.
- Remove git-based `aiopvpc` requirement from `manifest.json`; only `holidays>=0.89` is needed now.
- Update dependency logger names to match vendored module paths.

## 2.1.0

- Add configurable price mode (`pvpc` or `indexed`) with safe defaults for existing configurations.
- Restrict `indexed` mode selection to private API usage with a valid API token.
- Add optional reference price sensor behavior:
  - `Current Indexed Price` in PVPC mode.
  - `Current PVPC` in indexed mode.
- Add a dedicated diagnostic sensor that reports active price mode.
- Add `mode` attribute on `Current Price` to show whether PVPC or indexed pricing is active.
- Update setup/options flow UX:
  - Two-step mode selection after private API/token.
  - `Show Reference Price` moved to the same step as price mode selection.
- Update localized setup/options descriptions to mention indexed mode availability with private API.
- Extend tests for config flow, mode handling, and reference sensor behavior.

## 2.0.0

- Add `holiday_source` option (`python-holidays` or `csv`) to config flow and options flow.
- Persist `holiday_source` in config entries/options and pass it to `PVPCData(...)`.
- Migrate existing entries to schema v7 with explicit default `csv` (matching aiopvpc `PVPCData` default).
- Bump `aiopvpc` to `4.3.5` and adopt `spanish-pvpc-holidays` handling.
- Update holiday fetching strategy: refresh yearly and keep cached values across restarts.
- Improve debug logging and remove warmup handling in favor of `aiopvpc`.
- Enable dependency debug logs for `aiopvpc` and `pvpc_holidays` when PVPC Next debug logging is enabled.
- Add explicit API fetch debug logs (source, fetched indicator set, series windows, and stats).
- Fix pylint issues and update documentation.

## 1.3.3

- Fix broken `aiopvpc` dependency.

## 1.3.2

- Bump bundled `aiopvpc` version.

## 1.3.1

- Add average price sensors for today/tomorrow and refine the feature set.
- Make update frequency configurable.
- Remove average price for tomorrow sensor.
- Update documentation.
- Internal release/version metadata updates.

## 1.3.0

- Move bundled/modified `aiopvpc` implementation to a dedicated fork.

## 1.2.4

- Compute “better prices ahead” across today+tomorrow and keep it relative to current price.
- Internal release/version metadata updates.

## 1.2.3

- Add sensors for current power period, next power period, and time until next power period.
- Internal release/version metadata updates.

## 1.2.2

- Fix available power logic.
- Improve unique ID handling.
- Add more debug logging.
- Update documentation.

## 1.2.1

- Add proper debug logging.
- Add “time to next price” sensor output in `HH:mm`.
- Change default better price target to `very cheap`.
- Add fallback to next-best target when no direct target is available.
- Rework setup/options for translation support and add missing translations.

## 1.2.0

- Fix blocking `import_module` call in the event loop (`holidays.countries.spain`).

## 1.1.9

- Improve “time to next period” precision (`HH:mm`) with minute-level updates.
- Internal release/version metadata updates.

## 1.1.8

- Update available power every hour.
- Internal release/version metadata updates.

## 1.1.7

- Add diagnostic sensors for fetched indicators and current API source.
- Update naming and documentation.

## 1.1.6

- Show hidden MAG tax and OMIE sensors only when Injection Price is enabled.
- Update translations and README for token-based API access.
- Add new integration logo.

## 1.1.5

- Add missing migrations.

## 1.1.4

- Ensure coordinator always fetches Injection Price so it is available if enabled later.

## 1.1.3

- Fix setup/options flow around API key requirements and Injection Price.
- Fix imports that broke setups without an API key.
- Fix missing translations.
- Internal manifest/version metadata updates.

## 1.1.2

- Make Injection Price sensor optional and disabled by default.
- Update setup dialog and README.

## 1.1.1

- Update README and German translation.

## 1.1.0

- Add “better price target” option.
- Improve translation coverage.
- Improve handling of data unavailability.

## 1.0.0

- Initial release.
- Initial version/manifest release metadata.
