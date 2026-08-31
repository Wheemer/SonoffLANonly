import asyncio
import logging

import voluptuous as vol
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import (
    CONF_DEVICES,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD_OFF,
    CONF_SENSORS,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import async_get as device_registry
from homeassistant.helpers.storage import Store

from . import system_health
from .core import devices as core_devices
from .core.const import (
    CONF_APPID,
    CONF_APPSECRET,
    CONF_COUNTRY_CODE,
    CONF_DEFAULT_CLASS,
    CONF_DEVICEKEY,
    CONF_RFBRIDGE,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from .core.ewelink import (
    LOCAL_SENSOR_COMMANDS,
    SIGNAL_ADD_ENTITIES,
    XRegistry,
)
from .core.ewelink.camera import XCameras
from .core.ewelink.cloud import APP, AuthError
from .core.xutils import create_clientsession

_LOGGER = logging.getLogger(__name__)

# It is important to have the `sensor` first so that the bridges are initialized before
# the child devices. Fix `device_info["via_device"]` problem.
PLATFORMS = [
    "sensor",
    "alarm_control_panel",
    "binary_sensor",
    "button",
    "climate",
    "cover",
    "fan",
    "light",
    "media_player",
    "remote",
    "switch",
    "number",
    "select"
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_APPID): cv.string,
                vol.Optional(CONF_APPSECRET): cv.string,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_DEFAULT_CLASS): cv.string,
                vol.Optional(CONF_SENSORS): cv.ensure_list,
                vol.Optional(CONF_RFBRIDGE): {
                    cv.string: vol.Schema(
                        {
                            vol.Optional(CONF_NAME): cv.string,
                            vol.Optional(CONF_DEVICE_CLASS): cv.string,
                            vol.Optional(CONF_TIMEOUT): cv.positive_int,
                            vol.Optional(CONF_PAYLOAD_OFF): cv.string,
                        },
                        extra=vol.ALLOW_EXTRA,
                    ),
                },
                vol.Optional(CONF_DEVICES): {
                    cv.string: vol.Schema(
                        {
                            vol.Optional(CONF_NAME): cv.string,
                            vol.Optional(CONF_DEVICE_CLASS): vol.Any(str, list),
                            vol.Optional(CONF_DEVICEKEY): cv.string,
                            vol.Optional(CONF_UPDATE_INTERVAL): vol.All(
                                vol.Coerce(float), vol.Range(min=1, max=300)
                            ),
                        },
                        extra=vol.ALLOW_EXTRA,
                    ),
                },
            },
            extra=vol.ALLOW_EXTRA,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

UNIQUE_DEVICES = {}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if (MAJOR_VERSION, MINOR_VERSION) < (2023, 2):
        raise Exception("unsupported hass version")

    # init storage for registries
    hass.data[DOMAIN] = {}

    # load optional global registry config
    if DOMAIN in config:
        XRegistry.config = conf = config[DOMAIN]
        if CONF_APPID in conf and CONF_APPSECRET in conf:
            APP[0] = conf[CONF_APPID]
            APP.append(conf[CONF_APPSECRET])
        if CONF_DEFAULT_CLASS in conf:
            core_devices.set_default_class(conf.get(CONF_DEFAULT_CLASS))
        if CONF_SENSORS in conf:
            core_devices.get_spec = core_devices.get_spec_wrapper(
                core_devices.get_spec, conf.get(CONF_SENSORS)
            )

    # cameras starts only on first command to it
    cameras = XCameras()

    try:
        # import ewelink account from YAML (first time)
        data = {
            CONF_USERNAME: XRegistry.config[CONF_USERNAME],
            CONF_PASSWORD: XRegistry.config[CONF_PASSWORD],
        }
        if not hass.config_entries.async_entries(DOMAIN):
            coro = hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=data
            )
            hass.async_create_task(coro)
    except Exception:
        pass

    async def send_command(call: ServiceCall):
        """Service for send raw command to device.
        :param call: `device` - required param, all other params - optional
        """
        params = dict(call.data)
        deviceid = params.pop("device", None)

        if not deviceid:
            _LOGGER.error("Missing deviceid")
            return

        deviceid = str(deviceid)

        if len(deviceid) == 10:
            registry: XRegistry | None = next(
                (r for r in hass.data[DOMAIN].values() if deviceid in r.devices),
                None,
            )

            if registry is None:
                _LOGGER.error(f"Device not found: {deviceid}")
                return

            device = registry.devices[deviceid]

            # for debugging purposes
            if v := params.get("set_device"):
                if not isinstance(v, dict):
                    _LOGGER.error(f"Invalid set_device payload for deviceid {deviceid}")
                    return

                device.update(v)
                return

            command = params.pop("command", None)
            mode = params.pop("mode", None)

            if mode not in (None, "local"):
                _LOGGER.error("Only LAN commands are supported in SonoffLANonly")
                return

            if mode == "local":
                if command in LOCAL_SENSOR_COMMANDS:
                    await registry.send_local(device, command, params)
                else:
                    await registry.local.send(device, params, command)
            else:
                await registry.send(device, params, cmd_lan=command)

        elif len(deviceid) == 6:
            cmd = params.get("cmd")
            if not isinstance(cmd, str) or not cmd:
                _LOGGER.error(f"Missing camera command for deviceid {deviceid}")
                return

            await cameras.send(deviceid, cmd)

        else:
            _LOGGER.error(f"Wrong deviceid {deviceid}")

    hass.services.async_register(DOMAIN, "send_command", send_command)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    if config_entry.options.get("debug") and not _LOGGER.handlers:
        await system_health.setup_debug(hass, _LOGGER)

    registry: XRegistry = hass.data[DOMAIN].get(config_entry.entry_id)
    if not registry:
        session = create_clientsession(hass)
        hass.data[DOMAIN][config_entry.entry_id] = registry = XRegistry(session)

    data = config_entry.data

    # Remove the obsolete upstream mode option before registering the update
    # listener. SonoffLANonly always uses LAN for runtime communication.
    if "mode" in config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={k: v for k, v in config_entry.options.items() if k != "mode"},
        )

    config_entry.async_on_unload(config_entry.add_update_listener(async_update_options))

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, registry.stop)
    )

    # important to run before registry.setup_devices (for remote childs)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    devices: list[dict] | None = None
    store = Store(hass, 1, f"{DOMAIN}/{config_entry.data['username']}.json")
    registry.store = store

    if devices := await store.async_load():
        _LOGGER.debug(f"{len(devices)} devices loaded from Cache")

    # LAN-only runtime still needs cloud once to seed encrypted device metadata/keys.
    if not devices and data.get(CONF_PASSWORD):
        try:
            _LOGGER.debug(f"Login to cloud with APPID {APP[0][:4]} for LAN cache...")
            await registry.cloud.login(**data)
            if not data.get(CONF_COUNTRY_CODE):
                hass.config_entries.async_update_entry(
                    config_entry,
                    data={**data, CONF_COUNTRY_CODE: registry.cloud.country_code},
                )

            homes = config_entry.options.get("homes")
            devices = await registry.cloud.get_devices(homes)
            _LOGGER.debug(f"{len(devices)} devices loaded from Cloud for LAN cache")

            # store devices to cache
            await store.async_save(devices)

        except Exception as e:
            _LOGGER.warning("Can't seed LAN cache from cloud", exc_info=e)
            if isinstance(e, AuthError):
                raise ConfigEntryAuthFailed(e)

    if devices:
        # we need to setup_devices before local.start
        devices = internal_unique_devices(config_entry.entry_id, devices)
        entities = registry.setup_devices(devices)
        if data.get(CONF_PASSWORD):
            registry.metadata_task = hass.async_create_task(
                registry.refresh_cache_metadata(data, config_entry.options)
            )
    else:
        entities = None

    registry.local.start(await zeroconf.async_get_instance(hass))
    registry.local_connected()

    _LOGGER.debug("LOCAL mode start")

    # at this moment we hold EVENT_HOMEASSISTANT_START event
    if registry.local.online:
        # we hope that most of local devices will be discovered in 3 seconds
        await asyncio.sleep(3)

    # 1. We need add_entities after cloud or local init, so they won't be
    #    unavailable at init state
    # 2. We need add_entities before Hass start event, so Hass won't push
    #    unavailable state with restored=True attribute to history
    if entities:
        _LOGGER.debug(f"Add {len(entities)} entities")
        registry.dispatcher_send(SIGNAL_ADD_ENTITIES, entities)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not ok:
        return False

    registry: XRegistry | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if registry:
        await registry.stop()

    internal_free_devices(entry.entry_id)

    return True


def internal_unique_devices(uid: str, devices: list) -> list:
    """For support multiple integrations - bind each device to one integraion.
    To avoid duplicates.
    """
    return [
        device
        for device in devices
        if UNIQUE_DEVICES.setdefault(device["deviceid"], uid) == uid
    ]


def internal_free_devices(uid: str):
    for k in [k for k, v in UNIQUE_DEVICES.items() if v == uid]:
        UNIQUE_DEVICES.pop(k)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device
) -> bool:
    device_registry(hass).async_remove_device(device.id)
    return True
