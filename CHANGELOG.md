# Changelog

## 3.12.2.12

- Initialize energy reporting settings before applying cached LAN history, preventing S40 energy entities from raising `AttributeError` during startup.

## 3.12.2.11

- Correct the inching action labels: protocol `switch: on` is **Auto-on**, and `switch: off` is **Auto-off**.
- Keep protocol option values separate from their translated user-facing labels.

## 3.12.2.10

- Rename the inching modes to the concise, behavior-focused **Disabled**, **Auto-off**, and **Auto-on** labels.

## 3.12.2.9

- Replace the separate channel-aware inching switch and action entities with one **Inching mode** dropdown: **Disabled**, **On then off**, or **Off then on**.
- Remove obsolete inching switch and action registry entries automatically when the new mode selector loads.

## 3.12.2.8

- Mirror eWeLink 5.28.1 realtime reporting for proven UIID 32 and 182 devices by opening a 60-second `uiActive` lease and renewing it every 50 seconds.
- Keep each device's configured update interval as its independent telemetry freshness target, using a bounded active mDNS refresh when a `uiActive` publication becomes stale.
- Stop using `sledOnline` writes as telemetry and availability probes for those `uiActive` devices.
- Preserve complete channel-aware inching payloads, reject unreported outlets and fields, and confirm only the selected outlet and changed field after acknowledgement.
- Require historical energy payloads to arrive inline or through a local callback before advancing the entity's hourly request throttle.
- Route UIID 181 automatic-mode changes through the proven local `/zeroconf/autoControlEnabled` endpoint.
- Remove configuration and climate entities whose implementations were known to require cloud commands under the enforced LAN-only policy.
- Stop advertising cloud-only transition support for UIID 277 MINI-DIM while retaining immediate local brightness control.
- Cancel per-device local refresh tasks cleanly during config-entry unload and reload.
- Synchronize the fork with current `upstream/master` and expand protocol, interval, acknowledgement, and lifecycle regression coverage.

## 3.12.2.7

- Always release the realtime telemetry poll latch when an mDNS recovery task fails or is cancelled, preventing one background error from permanently stopping later sensor updates.
- Retry a failed telemetry recovery within five seconds while ensuring an older task cannot clear a newer poll's latch.

## 3.12.2.6

- Keep realtime LAN sensors available while their device remains locally reachable instead of treating missing callback payloads as device failure.
- Restart a stalled eWeLink mDNS browser after repeated missed telemetry callbacks so local readings recover without reloading the integration.
- Log background telemetry recovery failures instead of allowing task exceptions to disappear silently.

## 3.12.2.5

- Expose one **Update interval** control for every top-level Sonoff device, covering all entities attached to that physical device.
- Apply the interval to the general LAN state and availability watchdog as well as supported realtime telemetry.
- Reset the watchdog whenever a local callback arrives, avoiding duplicate polling while the device is actively reporting.
- Keep child entities on their parent device's LAN interval so multiple controls cannot compete for one transport.

## 3.12.2.4

- Add a persisted **Update interval** Number control to the Configuration section of every device that supports active local telemetry refresh.
- Keep the existing 30-second default and YAML values while allowing per-device UI values from 1 to 300 seconds.
- Make a saved UI value override YAML for that device and preserve it when other integration options are changed.

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
