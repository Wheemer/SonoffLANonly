from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from custom_components.sonoff import energy_history
from custom_components.sonoff.energy_history import build_daily_statistics
from custom_components.sonoff.sensor import XCloudEnergy

from . import DEVICEID, init


def test_manager_uses_background_tasks():
    calls = []

    class Hass:
        def async_create_background_task(self, coro, name):
            coro.close()
            calls.append(name)
            return SimpleNamespace(cancel=lambda: None)

    manager = energy_history.XEnergyHistoryManager(Hass())
    manager.add_entities(
        [
            SimpleNamespace(
                param="hundredDaysKwhData", device={"deviceid": DEVICEID}
            )
        ]
    )

    assert calls == [f"sonoff energy history {DEVICEID}"]


def test_build_daily_statistics_orders_oldest_first():
    statistics = build_daily_statistics(
        [3.0, 2.0, 1.0], date(2026, 9, 2), ZoneInfo("UTC"), 10.0
    )

    assert [item["start"].date() for item in statistics] == [
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 2),
    ]
    assert [item["state"] for item in statistics] == [1.0, 2.0, 3.0]
    assert [item["sum"] for item in statistics] == [11.0, 13.0, 16.0]


def test_build_daily_statistics_uses_local_midnight():
    statistics = build_daily_statistics(
        [1.25],
        date(2026, 9, 2),
        ZoneInfo("America/St_Johns"),
        0.0,
    )

    start = statistics[0]["start"]
    assert start.hour == 0
    assert start.minute == 0
    assert start.utcoffset().total_seconds() == -(2 * 3600 + 30 * 60)


def test_build_daily_statistics_preserves_overlap_baseline():
    statistics = build_daily_statistics(
        [0.25, 0.5], date(2026, 9, 2), ZoneInfo("UTC"), 42.0
    )

    assert [item["sum"] for item in statistics] == [42.5, 42.75]


def test_hundred_day_entity_hands_complete_history_to_manager():
    registry, entities = init({"extra": {"uiid": 182}})
    registry.dispatcher_send(
        DEVICEID, {"config": {"hundredDaysKwhData": "000001" * 100}}
    )

    energy: XCloudEnergy = next(entity for entity in entities if entity.uid == "energy")
    assert energy.should_poll is False
    assert energy.daily_history == [0.01] * 100

    registry.dispatcher_send(DEVICEID, {"config": {"hundredDaysKwhData": "000002"}})
    assert energy.daily_history is None


def test_baseline_uses_last_statistic_before_long_gap(monkeypatch):
    manager = energy_history.XEnergyHistoryManager(None)
    monkeypatch.setattr(
        energy_history,
        "get_last_statistics",
        lambda *args: {"sonoff:test": [{"start": 1.0, "sum": 42.5}]},
    )
    monkeypatch.setattr(
        energy_history,
        "statistics_during_period",
        lambda *args: (_ for _ in ()).throw(AssertionError("unexpected overlap query")),
    )

    baseline = manager._get_baseline(
        datetime(2026, 9, 2, tzinfo=timezone.utc), "sonoff:test"
    )

    assert baseline == 42.5


def test_baseline_uses_row_immediately_before_overlap(monkeypatch):
    manager = energy_history.XEnergyHistoryManager(None)
    monkeypatch.setattr(
        energy_history,
        "get_last_statistics",
        lambda *args: {"sonoff:test": [{"start": 2_000_000_000.0, "sum": 99.0}]},
    )
    monkeypatch.setattr(
        energy_history,
        "statistics_during_period",
        lambda *args: {"sonoff:test": [{"sum": 18.75}]},
    )

    baseline = manager._get_baseline(
        datetime(2026, 9, 2, tzinfo=timezone.utc), "sonoff:test"
    )

    assert baseline == 18.75
