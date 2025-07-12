import datetime
import io
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List

import matplotlib
import matplotlib.font_manager as fm
from influxdb_client import InfluxDBClient
from matplotlib import pyplot as plt
from matplotlib import ticker
from mpl_toolkits.axisartist.axislines import AxesZero
from PIL import Image, ImageDraw, ImageFont

from .widget import Widget

HERE = pathlib.Path(__file__).parent


class InfluxDBWidget(Widget):
    def __init__(self, url: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_folder = HERE / "data"

        token = (self.data_folder / "influxdb_token.txt").read_text().strip()
        client = InfluxDBClient(
            url=url,
            token=token,
            org="home",
        )
        self.query_api = client.query_api()

    def get_unit(self, field: str) -> str:
        return {
            "temperature": "°C",
            "humidity": "%",
            "co2": "ppm",
        }.get(field, field)

    def format_measurement(
        self,
        field: str,
        measurement: float,
        precision: int | None = None,
        sep: str | None = None,
        unit: str | None = None,
    ) -> str:
        if precision is None:
            precision = {
                "temperature": 1,
                "humidity": 0,
                "co2": -1,
            }.get(field, 0)
        if sep is None:
            sep = {
                "temperature": " ",
                "humidity": " ",
                "co2": " ",
            }.get(field, None)
        if unit is None:
            unit = self.get_unit(field)
        if precision < 0:
            measurement = round(measurement, precision)
            precision = 0
        return f"{measurement:.{precision}f}{sep}{unit}"


class InfluxDBCurrentValue(InfluxDBWidget):
    def __init__(
        self,
        data_fields: List[Dict[str, Any]],
        alignment: str = "vertical",
        font_size_label: int = 16,
        font_size_value: int = 32,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.data_fields = data_fields
        self.alignment = alignment
        self.font_size_label = font_size_label
        self.font_size_value = font_size_value

    def get_current_data(self, data_field: Dict, max_age=datetime.timedelta(minutes=5)):
        query = f"""\
from(bucket: "appartment")
    |> range(start: 0)
    |> filter(fn: (r) => r._field == "{data_field["field"]}" and r.sensorid == "{data_field["sensor_id"]}")
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

    def render(self, timestamp: datetime.datetime) -> Image.Image:
        screen = Image.new("1", self.size, 255)
        draw = ImageDraw.Draw(screen)

        # get all data
        data = []
        for data_field in self.data_fields:
            value = self.get_current_data(data_field)
            if value is None:
                value_str = "offline"
                unit_str = None
            else:
                value_str = self.format_measurement(data_field["field"], value, unit="")
                unit_str = self.get_unit(data_field["field"])
            data.append(
                {
                    "label": data_field["label"],
                    "value_str": value_str,
                    "unit_str": unit_str,
                }
            )

        # draw headings
        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.font_size_label
        )
        for i, d in enumerate(data):
            if self.alignment == "horizontal":
                draw.text(
                    (int(self.width / (2 * len(data)) * (2 * i + 1)), 0),
                    d["label"],
                    font=font,
                    fill=0,
                    anchor="mt",
                )
            else:
                draw.text(
                    (0, int(self.height / (2 * len(data)) * (2 * i + 1))),
                    d["label"],
                    font=font,
                    fill=0,
                    anchor="lm",
                )

        # draw values
        font = ImageFont.truetype(
            self.data_folder / "Font.ttc", size=self.font_size_value
        )
        max_unit_width_pixels = max(
            [font.getlength(d["unit_str"]) for d in data if d["unit_str"] is not None]
            or [0]
        )
        for i, d in enumerate(data):
            if self.alignment == "horizontal":
                draw.text(
                    (
                        int(self.width / (2 * len(data)) * (2 * i + 1)),
                        self.height - int(font.size * 0.35),
                    ),
                    d["value_str"] + (d["unit_str"] or ""),
                    font=font,
                    fill=0,
                    anchor="ms",
                )
            else:
                center_height = int(self.height / (2 * len(data)) * (2 * i + 1))
                baseline_height = center_height + int(font.size * 0.35)
                if d["unit_str"] is not None:
                    # align values by unit
                    draw.text(
                        (self.width - max_unit_width_pixels, baseline_height),
                        d["value_str"],
                        font=font,
                        fill=0,
                        anchor="rs",
                    )
                    draw.text(
                        (self.width - max_unit_width_pixels, baseline_height),
                        d["unit_str"],
                        font=font,
                        fill=0,
                        anchor="ls",
                    )
                else:
                    draw.text(
                        (self.width, baseline_height),
                        d["value_str"],
                        font=font,
                        fill=0,
                        anchor="rs",
                    )

        return screen


@dataclass
class TrendAggregation:
    interval_min: int = 5
    function: str = "mean"
    linewidth: int = 2
    linestyle: str = "solid"


class InfluxDBTrend(InfluxDBWidget):
    """
    Widget to display a trend of a single data field from an InfluxDB sensor.
    It shows the last 24 hours of data by default.
    """

    def __init__(
        self,
        data_field: str,
        sensor_id: int,
        aggregations: List[TrendAggregation] | None = None,
        history_h: int = 24,
        font_size: int = 16,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.data_field = data_field
        self.sensor_id = sensor_id
        if aggregations is not None:
            self.aggregations = aggregations
        else:
            self.aggregations = [TrendAggregation()]
        self.history_h = history_h
        self.font_size = font_size

    def get_min_range(self):
        return {
            "temperature": [18, 24],
            "humidity": [40, 60],
            "co2": [400, 1000],
        }.get(self.data_field, [0, 0])

    def get_trend_data(
        self,
        start: datetime.datetime,
        stop: datetime.datetime,
        aggregation: TrendAggregation | None = None,
    ) -> List[tuple[datetime.datetime, float]]:
        if aggregation is None:
            aggregation = TrendAggregation()
        if aggregation.function not in ["mean", "max", "min", "median"]:
            raise ValueError(
                f"Unsupported aggregation function: {aggregation.function}"
            )
        query = f"""\
from(bucket: "appartment")
    |> range(start: {start.isoformat()}, stop: {stop.isoformat()})
    |> filter(fn: (r) => r._field == "{self.data_field}" and r.sensorid == "{self.sensor_id}")
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

    def _create_plot(
        self,
        start: datetime.datetime,
        stop: datetime.datetime,
        min_data_value: float,
        max_data_value: float,
    ):
        font_path = self.data_folder / "Font.ttc"
        fm.fontManager.addfont(font_path)
        prop = fm.FontProperties(fname=font_path)

        dpi = 100
        px = 1 / dpi
        font_px = (
            72 / dpi
        )  # font sizes are usually in points, if we want to use px we need to convert

        font = {
            "family": [prop.get_name(), "sans-serif"],
            "size": self.font_size * font_px,
        }

        matplotlib.rc("font", **font)

        fig = plt.figure(figsize=(self.width * px, self.height * px), dpi=dpi)

        ax = fig.add_subplot(axes_class=AxesZero)
        ax.set_position(
            (
                3.8 * font["size"] / self.width,  # left
                1.6 * font["size"] / self.height,  # bottom
                1 - (3.8 + 1.6) * font["size"] / self.width,  # width
                1 - (1.6 + 1.6) * font["size"] / self.height,  # height
            ),
        )
        ax.grid(True)

        start_of_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        if stop - start <= datetime.timedelta(hours=24):
            # get xtick positions as multiples of 6 hours and format as hour:minute
            interval = datetime.timedelta(hours=6)
            format_str = "%H:%M"
            start_of_labels = start_of_day
        elif (stop - start) / datetime.timedelta(days=1) < self.width / (
            font["size"] * 4
        ):
            # get xtick positions as multiples of 24 hours and format as day of the week
            interval = datetime.timedelta(days=1)
            format_str = "%a %d."
            start_of_labels = start_of_day
        else:
            # get xtick positions as multiples of 7 days and format as date
            interval = datetime.timedelta(days=7)
            format_str = "%d. %b"
            start_of_labels = start_of_day - datetime.timedelta(
                days=start_of_day.weekday()
            )

        p = start_of_labels
        xticks = []
        while p < stop:
            if p > start:
                xticks.append(p)
            p += interval
        ax.set_xticks(xticks, labels=[x.strftime(format_str) for x in xticks])

        ax.yaxis.set_major_formatter(
            ticker.FuncFormatter(
                lambda x, _: self.format_measurement(
                    self.data_field, x, precision=0, sep="\n" if x > 100 else None
                )
            )
        )
        if self.data_field == "temperature":
            # we don't want to have a 2.5°C tick
            ax.yaxis.set_major_locator(
                ticker.MaxNLocator(nbins="auto", steps=[1, 2, 4, 5, 10])
            )

        ax.set_xlim(start, stop)
        min_value, max_value = self.get_min_range()
        min_value = min(min_value, min_data_value - 0.1 * (max_value - min_value))
        max_value = max(max_value, max_data_value + 0.1 * (max_value - min_value))
        ax.set_ylim(min_value, max_value)

        return fig, ax

    def _fig_to_img(self, fig: matplotlib.figure.Figure) -> Image.Image:
        buf = io.BytesIO()
        fig.savefig(buf)
        fig.clf()

        buf.seek(0)
        img = Image.open(buf)

        # draw = ImageDraw.Draw(img)
        # draw.rectangle(
        #     (0, 0, self.width-1, self.height-1), outline=0
        # )

        return img

    def render(self, timestamp: datetime.datetime) -> Image.Image:
        start = timestamp - datetime.timedelta(hours=self.history_h)
        stop = timestamp

        curves = []

        for aggregation in self.aggregations:
            trend = self.get_trend_data(start=start, stop=stop, aggregation=aggregation)
            times, values = zip(*trend)
            curves.append((times, values))

        min_value = min(min(values) for _, values in curves)
        max_value = max(max(values) for _, values in curves)

        fig, ax = self._create_plot(start, stop, min_value, max_value)

        for (times, values), aggregation in zip(curves, self.aggregations):
            ax.plot(
                times,
                values,
                color="black",
                linewidth=aggregation.linewidth,
                linestyle=aggregation.linestyle,
            )

        return self._fig_to_img(fig)


class InfluxDBTrendCompareToYesterday(InfluxDBTrend):
    """
    Widget to display a trend of a single data field from an InfluxDB sensor,
    comparing today's data to yesterday's data.
    It shows the current day with today's data in solid line and yesterday's data in dotted line.
    """

    def render(self, timestamp: datetime.datetime) -> Image.Image:
        assert self.history_h == 24

        start_of_day = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

        one_day = datetime.timedelta(days=1)

        start = start_of_day
        stop = start_of_day + one_day

        trend_today = self.get_trend_data(start=start, stop=stop)
        trend_yesterday = self.get_trend_data(
            start=start - one_day, stop=stop - one_day
        )

        times_today, values_today = zip(*trend_today)
        times_yesterday, values_yesterday = zip(*trend_yesterday)

        fig, ax = self._create_plot(
            start,
            stop,
            min(values_today + values_yesterday),
            max(values_today + values_yesterday),
        )

        ax.plot(
            [t + one_day for t in times_yesterday],
            values_yesterday,
            color="black",
            linewidth=1,
            linestyle="dotted",
        )
        ax.plot(times_today, values_today, color="black", linewidth=2)

        return self._fig_to_img(fig)
