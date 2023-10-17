import logging
from typing import Any, Callable
import asyncio
import datetime
import aiohttp
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class SolarModule:
    def __init__(self, id: str, power: int, dcvoltage: int, gridvoltage: int):
        self._id = id
        self._power = power
        self._dcvoltage = dcvoltage
        self._gridvoltage = gridvoltage


class InverterData:
    def __init__(self, id: str, freq: float, temp: float, reportingtime: datetime):
        self._id = id
        self._freq = freq
        self._temperature = temp
        self._reportingtime = reportingtime
        self._solarmodules: list[SolarModule] = []

    def add_solar_module(self, sm: SolarModule) -> None:
        self._solarmodules.append(sm)

    def get_solarmodule_by_id(self, id: str) -> SolarModule:
        return next((x for x in self._solarmodules if x._id == id), None)


class EcuData:
    def __init__(
        self,
        id: str,
        address: str,
        alias: str,
        lifetimeGeneration: float,
        power: int,
        dailyEnergy: float,
        numberOfInverters: int = 0,
        numberOfInvertersOnline=0,
        softwareVersion: str = "",
    ) -> None:
        self._id = id
        self._alias = alias
        self._address = address
        self._power = power
        self._lifetimeGeneration = lifetimeGeneration
        self._dailyEnergy = dailyEnergy
        self._inverters: list[InverterData] = []
        self._numberOfInverters = numberOfInverters
        self._numberOfInvertersOnline = numberOfInvertersOnline
        self._softwareVersion = softwareVersion

    def add_inverter(self, inverter: InverterData) -> None:
        self._inverters.append(inverter)

    def get_inverter_by_id(self, id: str) -> InverterData:
        return next((x for x in self._inverters if x._id == id), None)


class EcuClient:
    def __init__(self, address: str, alias: str) -> None:
        _LOGGER.info("Init ApSystems ECU Client integration")
        self._address = address
        self._alias = alias

    async def get_ecu_data(self) -> [EcuData]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://" + self._address) as resp:
                    data = await resp.read()
                    soup = BeautifulSoup(data, features="html.parser")

                    id = (
                        soup.body.table.find("th", text="ECU ID")
                        .find_next_sibling("td")
                        .text
                    )

                    try:
                        lifetimegen = float(
                            soup.body.table.find("th", text="Lifetime generation")
                            .find_next_sibling("td")
                            .text.replace(" kWh", "")
                        )
                    except Exception as e:
                        lifetimegen = 0
                        _LOGGER.warning(str(e))

                    try:
                        power = int(
                            soup.body.table.find("th", text="Last System Power")
                            .find_next_sibling("td")
                            .text.replace(" W", "")
                        )
                    except Exception as e:
                        power = 0
                        _LOGGER.warning(str(e))

                    try:
                        energy = float(
                            soup.body.table.find("th", text="Generation of Current Day")
                            .find_next_sibling("td")
                            .text.replace(" kWh", "")
                        )
                    except Exception as e:
                        energy = 0.0
                        _LOGGER.warning(str(e))

                    try:
                        numberOfInverters = int(
                            soup.body.table.find("th", text="Number of Inverters")
                            .find_next_sibling("td")
                            .text
                        )
                    except Exception as e:
                        numberOfInverters = 0
                        _LOGGER.warning(str(e))

                    try:
                        numberOfInvertersOnline = int(
                            soup.body.table.find(
                                "th", text="Last Number of Inverters Online"
                            )
                            .find_next_sibling("td")
                            .text
                        )
                    except Exception as e:
                        numberOfInvertersOnline = 0
                        _LOGGER.warning(str(e))

                    try:
                        softwareVersion = str(
                            soup.body.table.find("th", text="Current Software Version")
                            .find_next_sibling("td")
                            .text
                        )
                    except Exception as e:
                        softwareVersion = ""
                        _LOGGER.warning(str(e))

                    ecuData = EcuData(
                        id,
                        self._address,
                        self._alias,
                        lifetimegen,
                        power,
                        energy,
                        numberOfInverters,
                        numberOfInvertersOnline,
                        softwareVersion,
                    )

                    async with session.get(
                        "http://" + self._address + "/index.php/realtimedata"
                    ) as resp_rt:
                        realtimedata = await resp_rt.read()
                        soup_realtimedata = BeautifulSoup(
                            realtimedata, features="html.parser"
                        )
                        currInverter = None
                        for row in soup_realtimedata.body.table.findChildren("tr"):
                            cells = row.find_all("td")
                            if not cells is None and len(cells) > 0:
                                id = cells[0].text.strip()

                                if len(cells) == 7:
                                    try:
                                        power = int(
                                            cells[1].text.replace("W", "").strip()
                                        )
                                    except Exception as e:
                                        power = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        dc = int(cells[2].text.replace("V", "").strip())
                                    except Exception as e:
                                        dc = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        hz = float(
                                            cells[3].text.replace("Hz", "").strip()
                                        )
                                    except Exception as e:
                                        hz = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        ac = int(cells[4].text.replace("V", "").strip())
                                    except Exception as e:
                                        ac = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        temp = int(
                                            cells[5].text.replace("°C", "").strip()
                                        )
                                    except Exception as e:
                                        temp = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        f = datetime.datetime.strptime(
                                            cells[6].text.strip(), "%Y-%m-%d %H:%M:%S"
                                        )
                                    except Exception as e:
                                        f = 0
                                        _LOGGER.warning(str(e))

                                    if not currInverter is None:
                                        try:
                                            ecuData.add_inverter(currInverter)
                                        except Exception as e:
                                            _LOGGER.error(str(e))

                                    id_parts = id.split("-")
                                    currInverter = InverterData(
                                        id_parts[0], hz, temp, f
                                    )

                                    try:
                                        currInverter.add_solar_module(
                                            SolarModule(id_parts[1], power, dc, ac)
                                        )
                                    except Exception as e:
                                        _LOGGER.error(str(e))

                                elif not currInverter is None:
                                    try:
                                        power = int(
                                            cells[1].text.replace("W", "").strip()
                                        )
                                    except Exception as e:
                                        power = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        dc = int(cells[2].text.replace("V", "").strip())
                                    except Exception as e:
                                        dc = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        ac = int(cells[3].text.replace("V", "").strip())
                                    except Exception as e:
                                        ac = 0
                                        _LOGGER.warning(str(e))

                                    try:
                                        id_parts = id.split("-")
                                        currInverter.add_solar_module(
                                            SolarModule(id_parts[1], power, dc, ac)
                                        )
                                    except Exception as e:
                                        _LOGGER.error(str(e))

                        if not currInverter is None:
                            try:
                                ecuData.add_inverter(currInverter)
                            except Exception as e:
                                _LOGGER.error(str(e))

                    return ecuData

        except:
            return None
