# Changelog

## 3.12.2.3

- Publish the integration as SonoffLANonly with LAN-only runtime control, state, and availability.
- Keep eWeLink authentication only for device inventory, metadata, and local encryption keys.
- Add local metadata reconciliation so newly paired devices enter the local cache.
- Add per-device telemetry watchdog intervals from 1 to 300 seconds with a 30-second default.
- Prompt supported S40-class and power-monitoring devices for local telemetry when callbacks become stale.
- Require asynchronous local telemetry after acknowledgement instead of treating ack-only responses as sensor updates.
- Confirm supported switch commands through fresh local mDNS state.
- Add bounded local polling, failure backoff, and connection diagnostics.
- Restore recovered entities only after local transport failure latches are cleared.
- Remove cloud mode choices and cloud runtime health reporting from the config flow.
- Add regression coverage for config flow, energy transport, telemetry, availability, and switch recovery behavior.
