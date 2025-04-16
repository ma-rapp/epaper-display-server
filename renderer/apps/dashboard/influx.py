import datetime
import io
import pathlib

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

    def translate_field(self, field: str) -> str:
        return {
            "temperature": "Temperatur",
            "humidity": "Luftfeuchtigkeit",
            "co2": "CO₂ Gehalt",
        }.get(field, field)

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
            }.get(field, None)
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
        self, data_fields, sensor_id, alignment: str = "vertical", *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.data_fields = data_fields
        self.sensor_id = sensor_id
        self.alignment = alignment

    def get_current_data(self, data_field: str, max_age=datetime.timedelta(minutes=5)):
        query = f"""\
from(bucket: "appartment")
    |> range(start: 0)
    |> filter(fn: (r) => r._field == "{data_field}" and r.sensorid == "{self.sensor_id}")
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

    def render(self, timestamp: datetime.datetime) -> Image:
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
                value_str = self.format_measurement(data_field, value, unit="")
                unit_str = self.get_unit(data_field)
            data.append(
                {
                    "label": self.translate_field(data_field),
                    "value_str": value_str,
                    "unit_str": unit_str,
                }
            )

        # draw headings
        font = ImageFont.truetype(self.data_folder / "Font.ttc", size=16)
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
        font = ImageFont.truetype(self.data_folder / "Font.ttc", size=32)
        max_unit_width_pixels = max(
            [font.getlength(d["unit_str"]) for d in data if d["unit_str"] is not None]
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


class InfluxDBTrend(InfluxDBWidget):
    def __init__(self, data_field, sensor_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.data_field = data_field
        self.sensor_id = sensor_id

    def get_min_range(self):
        return {
            "temperature": [18, 24],
            "humidity": [40, 60],
            "co2": [400, 1000],
        }.get(self.data_field, [0, 0])

    def get_trend_data(self, days: int = 1):
        query = f"""\
from(bucket: "appartment")
    |> range(start: -{days}d)
    |> filter(fn: (r) => r._field == "{self.data_field}" and r.sensorid == "{self.sensor_id}")
    |> aggregateWindow(every: 5m, fn: mean)"""
        result = self.query_api.query(query)

        assert len(result) == 1
        table = result[0]
        assert len(table.records) > 0

        return [
            (record.get_time().astimezone(), record.get_value())
            for record in table.records
            if record.get_value() is not None
        ]

    def render(self, timestamp: datetime.datetime) -> Image:
        font_path = self.data_folder / "Font.ttc"
        fm.fontManager.addfont(font_path)
        prop = fm.FontProperties(fname=font_path)

        font = {"family": [prop.get_name(), "sans-serif"], "size": 12}

        matplotlib.rc("font", **font)

        fig = plt.figure(figsize=(self.width / 100, self.height / 100), dpi=100)

        # left axis
        ax = fig.add_subplot(axes_class=AxesZero)
        ax.set_position(
            [
                3.8 * font["size"] / self.width,  # left
                1.6 * font["size"] / self.height,  # bottom
                1 - (3.8 + 1.6) * font["size"] / self.width,  # width
                1 - (1.6 + 1.4) * font["size"] / self.height,  # height
            ],
        )
        ax.grid(True)

        trend = self.get_trend_data()
        times, values = zip(*trend)
        ax.plot(times, values, color="black", linewidth=2)

        # get xtick positions as multiples of 6 hours
        start = min(times)
        end = max(times)
        start_of_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        p = start_of_day
        xticks = []
        while p < end:
            if p > start:
                xticks.append(p)
            p += datetime.timedelta(hours=6)
        ax.set_xticks(xticks, labels=[x.strftime("%H:%M") for x in xticks])

        ax.yaxis.set_major_formatter(
            ticker.FuncFormatter(
                lambda x, _: self.format_measurement(
                    self.data_field, x, precision=0, sep="\n" if x > 100 else None
                )
            )
        )

        ax.set_xlim(start, end)
        min_value, max_value = self.get_min_range()
        min_value = min(min_value, min(values) - 0.1 * (max_value - min_value))
        max_value = max(max_value, max(values) + 0.1 * (max_value - min_value))
        ax.set_ylim(min_value, max_value)

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
