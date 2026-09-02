import asyncio
from contextlib import suppress
from datetime import date, datetime, time, timedelta, tzinfo
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .core.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HISTORY_PARAM = "hundredDaysKwhData"
HISTORY_DAYS = 100
HISTORY_OVERLAP_DAYS = 30
HISTORY_RETRY_SECONDS = 300


def build_daily_statistics(
    history: list[float], today: date, timezone: tzinfo, baseline: float
) -> list[StatisticData]:
    """Build chronological daily statistics from newest-first device history."""
    total = baseline
    statistics = []
    for days_ago in range(len(history) - 1, -1, -1):
        value = history[days_ago]
        total = round(total + value, 6)
        statistics.append(
            StatisticData(
                start=datetime.combine(
                    today - timedelta(days=days_ago), time.min, timezone
                ),
                state=value,
                sum=total,
            )
        )
    return statistics


class XEnergyHistoryManager:
    """Import device-stored daily energy into Home Assistant statistics."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._tasks: dict[str, asyncio.Task] = {}

    def add_entities(self, entities: list) -> None:
        for entity in entities:
            if getattr(entity, "param", None) != HISTORY_PARAM:
                continue
            deviceid = entity.device["deviceid"]
            if deviceid in self._tasks:
                continue
            self._tasks[deviceid] = self.hass.async_create_background_task(
                self._run(entity), f"{DOMAIN} energy history {deviceid}"
            )

    async def async_stop(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def _run(self, entity) -> None:
        first_import = True
        while True:
            try:
                success = False
                if entity.can_update() and await entity.get_update():
                    history = getattr(entity, "daily_history", None)
                    if history and len(history) == HISTORY_DAYS:
                        days = HISTORY_DAYS if first_import else HISTORY_OVERLAP_DAYS
                        await self._async_import(entity, history[:days])
                        _LOGGER.debug(
                            "Imported %s days of historical energy for %s",
                            days,
                            entity.device.get("deviceid"),
                        )
                        first_import = False
                        success = True

                if not success:
                    _LOGGER.debug(
                        "Historical energy unavailable for %s; retrying",
                        entity.device.get("deviceid"),
                    )

                delay = entity.report_dt if success else HISTORY_RETRY_SECONDS
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception(
                    "Historical energy update failed for %s; retrying",
                    entity.device.get("deviceid"),
                )
                await asyncio.sleep(HISTORY_RETRY_SECONDS)

    async def _async_import(self, entity, history: list[float]) -> None:
        deviceid = entity.device["deviceid"]
        statistic_id = f"{DOMAIN}:{deviceid}_energy_consumption"
        today = dt_util.now().date()
        timezone = dt_util.get_default_time_zone()
        earliest = datetime.combine(
            today - timedelta(days=len(history) - 1), time.min, timezone
        )
        baseline = await get_instance(self.hass).async_add_executor_job(
            self._get_baseline, earliest, statistic_id
        )
        statistics = build_daily_statistics(history, today, timezone, baseline)
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{entity.device['name']} energy consumption",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )
        async_add_external_statistics(self.hass, metadata, statistics)

    def _get_baseline(self, earliest: datetime, statistic_id: str) -> float:
        last = get_last_statistics(self.hass, 1, statistic_id, True, {"sum"}).get(
            statistic_id
        )
        if last and last[0]["start"] < earliest.timestamp():
            return float(last[0]["sum"])

        existing = statistics_during_period(
            self.hass,
            earliest - timedelta(days=HISTORY_DAYS + 1),
            earliest,
            {statistic_id},
            "hour",
            None,
            {"sum"},
        )
        rows = existing.get(statistic_id)
        return float(rows[-1]["sum"]) if rows else 0.0
