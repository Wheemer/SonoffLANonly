from homeassistant.components.select import SelectEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .core.const import DOMAIN
from .core.entity import XEntity
from .core.ewelink import SIGNAL_ADD_ENTITIES, XRegistry

PARALLEL_UPDATES = 0  # fix entity_platform parallel_updates Semaphore


def remove_legacy_inching_entities(registry, entity) -> None:
    """Remove the superseded inching switch and action selector."""
    unique_id = entity.unique_id
    base = f"{entity.device['deviceid']}_inching"
    suffix = unique_id.removeprefix(base)
    legacy_ids = (
        registry.async_get_entity_id("switch", DOMAIN, unique_id),
        registry.async_get_entity_id("select", DOMAIN, f"{base}_action{suffix}"),
    )
    for entity_id in legacy_ids:
        if entity_id:
            registry.async_remove(entity_id)


async def async_setup_entry(hass, config_entry, add_entities):
    ewelink: XRegistry = hass.data[DOMAIN][config_entry.entry_id]

    def add_select_entities(entities):
        entities = [e for e in entities if isinstance(e, SelectEntity)]
        registry = er.async_get(hass)
        for entity in entities:
            if isinstance(entity, XInchingMode):
                remove_legacy_inching_entities(registry, entity)

        add_entities(entities)

    ewelink.dispatcher_connect(
        SIGNAL_ADD_ENTITIES,
        add_select_entities,
    )


class XSelectStartup(XEntity, SelectEntity):
    params = {"configure"}
    channel: int = 0

    get_params = {"configure": "get"}

    _attr_current_option = None
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["off", "on", "stay"]

    def __init__(self, ewelink: XRegistry, device: dict):
        super().__init__(ewelink, device)

        self.set_state(device.get("params", {}))

        try:
            self._attr_name = device["tags"]["ck_channel_name"][str(self.channel)]
        except KeyError:
            pass

        # backward compatibility
        self._attr_unique_id = f"{device['deviceid']}_{self.channel + 1}"

    def set_state(self, params: dict):
        # Update the selected startup option from the reported configure list
        configure_list = params.get("configure")
        if not isinstance(configure_list, list):
            return

        for item in configure_list:
            if item.get("outlet") == self.channel:
                self._attr_current_option = item.get("startup", "stay")
                break

    async def async_update(self):
        # Request the latest startup configuration from the device
        await self.ewelink.send(self.device, self.get_params, timeout_lan=5)

    async def async_select_option(self, option: str):
        # Start from the current device config so other channels are preserved
        configure_list = [
            dict(item)
            for item in self.device.get("params", {}).get("configure", [])
            if isinstance(item, dict)
        ]

        for item in configure_list:
            if item.get("outlet") == self.channel:
                item["startup"] = option
                break
        else:
            configure_list.append(
                {
                    "outlet": self.channel,
                    "startup": option,
                    "enableDelay": 0,  # this should be exposed as a config option in the future, for inching devices
                    "width": 1000,  # i don't know what this is for, but it seems to not have any effect on the device
                }
            )

        # Send the full configure list so other channels are preserved
        await self.ewelink.send(self.device, {"configure": configure_list})


class XInchingMode(XEntity, SelectEntity):
    """Channel-aware inching enable and action mode."""

    params = {"pulses"}
    channel: int = 0

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["disabled", "auto_off", "auto_on"]
    _attr_translation_key = "inching_mode"

    def __init__(self, ewelink: XRegistry, device: dict):
        super().__init__(ewelink, device)

        if self.uid != "inching":
            self._attr_name = f"{device['name']} Inching mode {self.channel + 1}"

        item = next(
            (
                item
                for item in device.get("params", {}).get("pulses", [])
                if item.get("outlet") == self.channel
            ),
            {},
        )
        if "switch" not in item:
            self._attr_options = ["disabled", "enabled"]

    def set_state(self, params: dict):
        for item in params.get("pulses", []):
            if item.get("outlet") == self.channel:
                if item.get("pulse") != "on":
                    self._attr_current_option = "disabled"
                elif "switch" not in item:
                    self._attr_current_option = "enabled"
                elif item["switch"] == "on":
                    self._attr_current_option = "auto_on"
                else:
                    self._attr_current_option = "auto_off"
                return

    async def async_select_option(self, option: str):
        if option == "disabled":
            changes = {"pulse": "off"}
        elif option == "enabled":
            changes = {"pulse": "on"}
        elif option == "auto_off":
            changes = {"pulse": "on", "switch": "off"}
        elif option == "auto_on":
            changes = {"pulse": "on", "switch": "on"}
        else:
            raise ValueError(f"Unsupported inching mode: {option}")
        await self.ewelink.set_inching(self.device, self.channel, **changes)


class XStartup(XEntity, SelectEntity):
    param = "startup"

    _attr_current_option = None
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["off", "on", "stay"]

    def set_state(self, params: dict):
        self._attr_current_option = params[self.param]

    async def async_select_option(self, option: str):
        await self.ewelink.send(self.device, {self.param: option})
