<div align="center">

# SonoffLANonly

### LAN-only Sonoff and eWeLink devices in Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-CUSTOM-FD7E14?style=for-the-badge&logo=home-assistant&logoColor=white&labelColor=555555)](https://github.com/hacs/integration)
[![Home Assistant 2023.2+](https://img.shields.io/badge/HOME%20ASSISTANT-2023.2%2B-41BDF5?style=for-the-badge&logo=home-assistant&logoColor=white&labelColor=555555)](https://www.home-assistant.io/)
[![Latest release](https://img.shields.io/github/v/release/Wheemer/SonoffLANonly?style=for-the-badge&logo=github&logoColor=white&label=RELEASE&labelColor=555555&color=22C55E)](https://github.com/Wheemer/SonoffLANonly/releases/latest)
[![License](https://img.shields.io/badge/LICENSE-MIT-64748B?style=for-the-badge&labelColor=555555)](LICENSE.md)

[Install](#install) | [Configure](#configure) | [Polling](#per-device-update-interval) | [Diagnostics](#diagnostics) | [Devices](DEVICES.md)

</div>

SonoffLANonly is a Home Assistant custom integration for Sonoff and other eWeLink devices running their original firmware. It uses the local eWeLink protocol for device commands, state, availability, and realtime telemetry. There is no cloud command or state fallback.

This project is a LAN-only fork of [AlexxIT/SonoffLAN](https://github.com/AlexxIT/SonoffLAN). It keeps the broad device support from that project while adding stricter local operation, local telemetry recovery, and per-device callback watchdog intervals.

## What It Does

- Controls supported switches, lights, sensors, covers, fans, climate devices, RF bridges, cameras, and related entities over LAN.
- Treats local mDNS callbacks as the primary source of state and telemetry.
- Prompts supported power-monitoring devices for fresh local telemetry when callbacks become stale.
- Confirms ack-only switch commands through a fresh local mDNS state response.
- Retries unreachable devices and restores entity availability when a device returns.
- Supports a `1` to `300` second device-specific telemetry watchdog interval, with a `30` second default.
- Exposes optional connection diagnostics for local receive age, telemetry acknowledgements, missing telemetry, and connection failures.
- Refreshes the eWeLink device inventory and local encryption keys during integration setup without starting cloud control or cloud state updates.

## LAN-Only Boundary

All runtime device commands, entity state, telemetry, and availability are local. Unsupported cloud modes are rejected instead of silently falling back.

An eWeLink login is still required for normal encrypted devices because the integration needs account inventory, model metadata, and each device's local encryption key. The login is used for metadata retrieval; it is not a cloud control path. DIY devices can be configured without an eWeLink password when their metadata and key are supplied locally.

Home Assistant and the devices must share a network where mDNS and direct TCP traffic can reach the devices. VLANs require working multicast forwarding and routing between Home Assistant and the Sonoff devices.

## Install

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Wheemer&repository=SonoffLANonly&category=integration)

If the button does not work:

1. Open HACS.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/Wheemer/SonoffLANonly` as an **Integration** repository.
4. Install **SonoffLANonly**.
5. Restart Home Assistant so the new Python module is loaded.
6. Open **Settings > Devices & services > Add integration** and select **SonoffLANonly**.

For a manual install, copy `custom_components/sonoff` into the Home Assistant `/config/custom_components/` directory and restart Home Assistant.

After any integration update, restart Home Assistant. Reloading the config entry unloads and reloads the already-imported module but does not replace Python code held by the running Home Assistant process.

## Configure

Enter the eWeLink account email or phone number and password. The integration retrieves the device inventory, metadata, and local encryption keys, then operates the devices locally.

Use the integration options to select eWeLink homes or enable the debug page. New devices paired in the eWeLink app are reconciled into the local cache the next time the integration is set up or reloaded with working credentials.

### Per-Device Update Interval

Local callbacks remain authoritative. `update_interval` is the maximum age allowed for supported realtime telemetry before the integration prompts the device for a fresh local publication. It is not a blind poll when callbacks are already arriving.

The default is `30` seconds. Every top-level Sonoff device exposes one **Update interval** Number entity in the device page's **Configuration** section. It controls freshness for all entities belonging to that physical device. Set it from `1` through `300` seconds; the value is stored in the SonoffLANonly config entry and survives reloads, updates, and restarts.

You can also provide initial or fallback values in `configuration.yaml` by eWeLink device ID:

```yaml
sonoff:
  devices:
    1000123456:
      update_interval: 15
    1000654321:
      update_interval: 1
```

Allowed values are `1` through `300` seconds. Restart Home Assistant after changing YAML.

A value saved through the device's **Update interval** control overrides YAML for that device. This keeps existing YAML defaults intact while allowing normal adjustments from the Home Assistant UI.

LAN callbacks reset the device timer. The integration sends a direct local refresh only after the device has been silent for the configured interval, so normal callbacks remain authoritative instead of being duplicated by blind polling. Power-monitoring devices use their firmware-specific telemetry refresh command. A shorter interval cannot make firmware publish data more quickly than it permits, and one-second intervals increase local network traffic.

### Local Device Overrides

The existing SonoffLAN YAML device overrides remain available:

```yaml
sonoff:
  devices:
    1000123456:
      name: Workshop Plug
      device_class: outlet
      devicekey: 0123456789abcdef
      update_interval: 15
```

`devicekey` is sensitive. Do not include it in issues, logs, screenshots, or diagnostics shared publicly.

## Telemetry And Recovery

Supported power devices use local callbacks for power, current, voltage, and energy data. When telemetry becomes older than the configured interval, SonoffLANonly sends the device-specific LAN request and waits for the asynchronous mDNS response. An HTTP acknowledgement alone is not treated as fresh sensor data.

Repeated connection failures mark a device unavailable. The integration continues local recovery attempts and clears the failure latch before notifying Home Assistant when the device answers again. This prevents a recovered switch from remaining unavailable because Home Assistant evaluated the old failure state during the recovery callback.

## Diagnostics

From **Settings > Devices & services > SonoffLANonly**, open the integration menu and download diagnostics. Connection diagnostic entities are disabled by default; enable one from the device entity list when troubleshooting.

Connection attributes include:

- `localrecv_age_s`: age of the last local callback.
- `localsensor_ack_at`: last successful LAN telemetry-request acknowledgement.
- `localsensor_ok_at`: last callback containing recognised telemetry.
- `localsensornodata`: consecutive acknowledged requests that produced no telemetry.
- `localsensorfail`: failed telemetry requests.
- `localconnectfail`: consecutive local transport failures.

Before opening an issue, confirm the device is reachable from the Home Assistant host and include the Home Assistant version, SonoffLANonly version, model, UIID, relevant logs, and sanitized diagnostics. Never publish account credentials or device keys.

## Device Support

See [DEVICES.md](DEVICES.md) for the inherited compatibility table. A verified **Local Type** indicates known local protocol support. Devices known to be cloud-only are intentionally unsupported by this fork. Blank local-support entries are unverified and may require testing.

## Updating From SonoffLAN

SonoffLANonly uses the same `sonoff` integration domain to preserve existing entities and automations. Do not install it alongside AlexxIT/SonoffLAN. Remove the old HACS repository, add this repository, install the fork, and restart Home Assistant once.

Back up Home Assistant before changing custom integration sources. Existing entity IDs should remain stable, but unsupported cloud-only devices will not be available.

## Development

Run the test suite from the repository root:

```bash
pytest -q
```

The GitHub workflow also runs HACS validation and Home Assistant hassfest checks.

## Credits

SonoffLANonly is derived from [AlexxIT/SonoffLAN](https://github.com/AlexxIT/SonoffLAN), including its protocol implementation, device definitions, and community contributions. Original local-protocol research credits remain with the upstream project and its contributors.

This repository preserves the upstream MIT license. See [LICENSE.md](LICENSE.md).
