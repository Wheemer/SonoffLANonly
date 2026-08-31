import pytest
import voluptuous as vol

from custom_components.sonoff.config_flow import merge_options, options_schema


def test_options_schema_is_lan_only():
    schema = options_schema({"home-id": "My Home"})

    assert schema({}) == {"debug": False}
    assert schema({"debug": True, "homes": ["home-id"]}) == {
        "debug": True,
        "homes": ["home-id"],
    }
    with pytest.raises(vol.MultipleInvalid):
        schema({"mode": "cloud"})


def test_visible_options_preserve_device_update_intervals():
    assert merge_options(
        {
            "debug": False,
            "device_update_intervals": {"1000123abc": 1},
        },
        {"debug": True, "homes": ["home-id"]},
    ) == {
        "debug": True,
        "homes": ["home-id"],
        "device_update_intervals": {"1000123abc": 1},
    }
