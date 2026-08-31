import asyncio

import pytest

from custom_components.sonoff.core.ewelink import XRegistry
from tests import _REAL_CREATE_TASK, _REAL_GET_RUNNING_LOOP


@pytest.fixture(autouse=True)
def restore_create_task(monkeypatch):
    monkeypatch.setattr(asyncio, "create_task", _REAL_CREATE_TASK)
    monkeypatch.setattr(asyncio, "get_running_loop", _REAL_GET_RUNNING_LOOP)
    registry_globals = XRegistry._verify_sensor_telemetry.__globals__
    monkeypatch.setitem(registry_globals, "LOCAL_TELEMETRY_WAIT_SECONDS", 0)
    monkeypatch.setitem(registry_globals, "LOCAL_SWITCH_WAIT_SECONDS", 0)
    monkeypatch.setitem(registry_globals, "LOCAL_TELEMETRY_MDNS_POLL_SECONDS", 0)
    yield
    monkeypatch.setattr(asyncio, "create_task", _REAL_CREATE_TASK)
    monkeypatch.setattr(asyncio, "get_running_loop", _REAL_GET_RUNNING_LOOP)
