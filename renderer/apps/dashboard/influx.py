import datetime
import pathlib

from influxdb_client import InfluxDBClient

from .measurement import Measurement, TrendAggregation

HERE = pathlib.Path(__file__).parent


class InfluxDBMeasurement(Measurement):
    def __init__(
        self,
        url: str,
        sensor_id: int,
        field: str,
        label: str = "",
        unit: str = "",
        precision: int = 1,
    ):
        self._url = url
        self._sensor_id = sensor_id
        self._field = field
        self._label = label
        self._unit = unit
        self._precision = precision

        self.data_folder = HERE / "data"

        token = (self.data_folder / "influxdb_token.txt").read_text().strip()
        client = InfluxDBClient(
            url=url,
            token=token,
            org="home",
        )
        self.query_api = client.query_api()

    @property
    def label(self) -> str:
        return self._label

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def precision(self) -> int:
        return self._precision

    def get_most_recent_value(self, max_age: datetime.timedelta) -> float | None:
        query = f"""\
from(bucket: "appartment")
    |> range(start: 0)
    |> filter(fn: (r) => r._field == "{self._field}" and r.sensorid == "{self._sensor_id}")
    |> last()"""
        result = self.query_api.query(query)

        assert len(result) == 1
        table = result[0]
        assert len(table.records) == 1
        record = table.records[0]

        if record.get_time() < datetime.datetime.now(datetime.timezone.utc) - max_age:
            return None
        else:
            return record.get_value()

    def get_trace(
        self,
        start: datetime.datetime,
        stop: datetime.datetime,
        aggregation: TrendAggregation | None = None,
    ) -> list[tuple[datetime.datetime, float]]:
        if aggregation is None:
            aggregation = TrendAggregation()
        if aggregation.function not in ["mean", "max", "min", "median"]:
            raise ValueError(
                f"Unsupported aggregation function: {aggregation.function}"
            )
        query = f"""\
from(bucket: "appartment")
    |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
    |> filter(fn: (r) => r._field == "{self._field}" and r.sensorid == "{self._sensor_id}")
    |> aggregateWindow(every: {aggregation.interval_min}m, fn: {aggregation.function})"""
        result = self.query_api.query(query)

        assert len(result) == 1
        table = result[0]
        assert len(table.records) > 0

        return [
            (record.get_time().astimezone(), record.get_value())
            for record in table.records
            if record.get_value() is not None
        ]
