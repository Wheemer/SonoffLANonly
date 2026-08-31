from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from multidict import CIMultiDict

from .const import DOMAIN


def source_hash() -> str:
    if source_hash.__doc__:
        return source_hash.__doc__

    try:
        import hashlib
        import os

        m = hashlib.md5()
        path = os.path.dirname(os.path.dirname(__file__))
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for file in sorted(files):
                if not file.endswith(".py"):
                    continue
                path = os.path.join(root, file)
                with open(path, "rb") as f:
                    m.update(f.read())

        source_hash.__doc__ = m.hexdigest()[:7]
        return source_hash.__doc__

    except Exception as e:
        return repr(e)


def system_log_records(hass: HomeAssistant, domain: str) -> list | str:
    try:
        return [
            entry.to_dict()
            for key, entry in hass.data["system_log"].records.items()
            if domain in str(key)
        ]
    except Exception as e:
        return str(e)


def create_clientsession(hass: HomeAssistant) -> ClientSession:
    session = async_create_clientsession(hass)

    integration = hass.data["integrations"][DOMAIN]
    session._default_headers = CIMultiDict(
        {"User-Agent": "SonoffLAN/" + integration.version}
    )
    return session
