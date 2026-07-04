import datetime
import logging
from abc import ABC, abstractmethod

import metpy.calc
import metpy.units

from .measurement import Measurement, TrendAggregation


class _CompoundMeasurementFromTemperatureAndHumidity(Measurement, ABC):
    def __init__(
        self,
        temperature_measurement: Measurement,
        humidity_measurement: Measurement,
        label: str,
        unit: str,
        precision: int,
    ):
        self.temperature_measurement = temperature_measurement
        self.humidity_measurement = humidity_measurement

        self._label = label
        self._unit = unit
        self._precision = precision

        self.logger = logging.getLogger(__name__)

    @property
    def label(self) -> str:
        return self._label

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def precision(self) -> int:
        return self._precision

    @abstractmethod
    def _calculate_value(self, temperature: float, humidity: float) -> float:
        pass

    def get_most_recent_value(self, max_age: datetime.timedelta) -> float | None:
        temperature = self.temperature_measurement.get_most_recent_value(max_age)
        humidity = self.humidity_measurement.get_most_recent_value(max_age)
        if temperature is None or humidity is None:
            return None
        return self._calculate_value(temperature, humidity)

    def get_trace(
        self,
        start: datetime.datetime,
        stop: datetime.datetime,
        aggregation: TrendAggregation | None = None,
    ) -> list[tuple[datetime.datetime, float]]:
        temperature_trace = self.temperature_measurement.get_trace(
            start, stop, aggregation
        )
        humidity_trace = self.humidity_measurement.get_trace(start, stop, aggregation)
        if len(temperature_trace) != len(humidity_trace):
            self.logger.warning(
                "Temperature and humidity traces have different lengths: %d vs %d",
                len(temperature_trace),
                len(humidity_trace),
            )
            return []
        trace = []
        for (t_time, t_value), (h_time, h_value) in zip(
            temperature_trace, humidity_trace
        ):
            if t_time != h_time:
                self.logger.warning(
                    "Temperature and humidity traces have different timestamps: %s vs %s",
                    t_time,
                    h_time,
                )
                continue
            value = self._calculate_value(
                t_value,
                h_value,
            )
            trace.append((t_time, value))
        return trace


class DewPoint(_CompoundMeasurementFromTemperatureAndHumidity):
    def __init__(
        self,
        temperature_measurement: Measurement,
        humidity_measurement: Measurement,
        label: str = "Taupunkt",
        unit: str = "°C",
        precision: int = 1,
    ):
        super().__init__(
            temperature_measurement, humidity_measurement, label, unit, precision
        )

    def _calculate_value(self, temperature: float, humidity: float) -> float:
        return (
            metpy.calc.dewpoint_from_relative_humidity(
                temperature * metpy.units.units.degC,
                humidity * metpy.units.units.percent,
            )
            .to(metpy.units.units.degC)
            .magnitude
        )


class WetBulbTemperature(_CompoundMeasurementFromTemperatureAndHumidity):
    def __init__(
        self,
        temperature_measurement: Measurement,
        humidity_measurement: Measurement,
        label: str = "Feuchtkugeltemperatur",
        unit: str = "°C",
        precision: int = 1,
    ):
        super().__init__(
            temperature_measurement, humidity_measurement, label, unit, precision
        )

    def _calculate_value(self, temperature: float, humidity: float) -> float:
        dewpoint_value = metpy.calc.dewpoint_from_relative_humidity(
            temperature * metpy.units.units.degC,
            humidity * metpy.units.units.percent,
        )
        return (
            metpy.calc.wet_bulb_temperature(
                pressure=1013.25 * metpy.units.units.hPa,
                temperature=temperature * metpy.units.units.degC,
                dewpoint=dewpoint_value,
            )
            .to(metpy.units.units.degC)
            .magnitude
        )


class WetBulbGlobalTemperature(_CompoundMeasurementFromTemperatureAndHumidity):
    def __init__(
        self,
        temperature_measurement: Measurement,
        humidity_measurement: Measurement,
        label: str = "WBGT",
        unit: str = "°C",
        precision: int = 1,
    ):
        super().__init__(
            temperature_measurement, humidity_measurement, label, unit, precision
        )

    def _calculate_value(self, temperature: float, humidity: float) -> float:
        dewpoint_value = metpy.calc.dewpoint_from_relative_humidity(
            temperature * metpy.units.units.degC,
            humidity * metpy.units.units.percent,
        )
        wet_bulb_temperature = metpy.calc.wet_bulb_temperature(
            pressure=1013.25 * metpy.units.units.hPa,
            temperature=temperature * metpy.units.units.degC,
            dewpoint=dewpoint_value,
        )
        dry_bulb_temperature = temperature
        return (
            0.7 * wet_bulb_temperature.to(metpy.units.units.degC).magnitude
            + 0.3 * dry_bulb_temperature
        )


class FeelsLikeTemperature(_CompoundMeasurementFromTemperatureAndHumidity):
    """
    Calculate the "feels like" temperature based on the actual temperature and humidity.
    This is the temperature that results in the same wet bulb global temperature (WBGT) as the actual temperature and humidity, but at a reference humidity level.
    """

    def __init__(
        self,
        temperature_measurement: Measurement,
        humidity_measurement: Measurement,
        label: str = "Gefühlte Temperatur",
        unit: str = "°C",
        precision: int = 1,
        reference_humidity: float = 50.0,
        calculation_method="wbgt",  # or "wbt"
    ):
        super().__init__(
            temperature_measurement, humidity_measurement, label, unit, precision
        )
        self.reference_humidity = reference_humidity
        self.calculation_method = calculation_method

    def _calculate_reference_metric(self, temperature: float, humidity: float) -> float:
        dewpoint_value = metpy.calc.dewpoint_from_relative_humidity(
            temperature * metpy.units.units.degC,
            humidity * metpy.units.units.percent,
        )
        wet_bulb_temperature = metpy.calc.wet_bulb_temperature(
            pressure=1013.25 * metpy.units.units.hPa,
            temperature=temperature * metpy.units.units.degC,
            dewpoint=dewpoint_value,
        )

        if self.calculation_method == "wbgt":
            dry_bulb_temperature = temperature
            return (
                0.7 * wet_bulb_temperature.to(metpy.units.units.degC).magnitude
                + 0.3 * dry_bulb_temperature
            )
        elif self.calculation_method == "wbt":
            return wet_bulb_temperature.to(metpy.units.units.degC).magnitude
        else:
            raise ValueError(f"Unknown calculation method: {self.calculation_method}")

    def _calculate_value(self, temperature: float, humidity: float) -> float:
        actual = self._calculate_reference_metric(temperature, humidity)

        # Now find the "feels like" temperature that gives the same WBGT at the reference humidity
        # We can use a simple iterative approach to find this temperature
        feels_like_temp = temperature  # Start with the actual temperature
        for _ in range(100):  # Limit iterations to prevent infinite loops
            reference = self._calculate_reference_metric(
                feels_like_temp, self.reference_humidity
            )

            if abs(reference - actual) < 0.1:  # Close enough
                break

            # Adjust feels_like_temp based on whether we need to increase or decrease it
            if reference < actual:
                feels_like_temp += 0.1  # Increase temp to raise WBGT
            else:
                feels_like_temp -= 0.1  # Decrease temp to lower WBGT

        return feels_like_temp
