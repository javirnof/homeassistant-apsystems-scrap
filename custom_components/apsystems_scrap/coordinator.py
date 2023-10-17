from datetime import timedelta
from typing import Any, Awaitable, Callable, Coroutine
from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import logging
import datetime
from .apsystems_ecu import EcuClient, EcuData

_LOGGER = logging.getLogger(__name__)


@dataclass
class EcuCoordinatorData:
    EcuData: EcuData


class EcuUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Ecu Apsystems coordinator",
            update_interval=timedelta(minutes=5),
            update_method=self._async_update_data,
        )

        self._entry = entry
        self._ecuClient = EcuClient(
            self._entry.data["address"], self._entry.data["alias"]
        )

    async def _async_update_data(self) -> EcuCoordinatorData:
        ecuData: EcuData = await self._ecuClient.get_ecu_data()
        return ecuData
