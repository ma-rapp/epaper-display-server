import datetime
import io
import pathlib

import astral.location
import astral.sun
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from mpl_toolkits.axisartist.axislines import AxesZero
from PIL import Image

from .widget import Widget


class SunriseSunsetWidget(Widget):
    def __init__(
        self,
        latitude: float,
        longitude: float,
        axis_label_font_size: int = 16,
        time_label_font_size: int = 22,
        *args,
        **kwargs,
    ):
        """
        Args:
            latitude: Latitude of the location for which to display sunrise/sunset times.
            longitude: Longitude of the location for which to display sunrise/sunset times.
            axis_label_font_size: Font size for axis labels.
            time_label_font_size: Font size for time labels (annotations of sunrise, sunset and total daylight).
        """
        super().__init__(*args, **kwargs)
        self.latitude = latitude
        self.longitude = longitude
        self.axis_label_font_size = axis_label_font_size
        self.time_label_font_size = time_label_font_size
        self.data_folder = pathlib.Path(__file__).parent / "data"

    def here(self) -> astral.LocationInfo:
        return astral.LocationInfo(latitude=self.latitude, longitude=self.longitude)

    def get_sun_trace(
        self, day: datetime.date
    ) -> tuple[list[datetime.datetime], list[float]]:
        loc = astral.location.Location(self.here())

        # create a list of times at 0:00, 0:01, 0:02, ..., 23:59
        minutes_since_midnight = range(0, 24 * 60, 5)
        times = [
            datetime.datetime.combine(day, datetime.time()).astimezone()
            + datetime.timedelta(minutes=m)
            for m in minutes_since_midnight
        ]
        sun_elevations = []
        for t in times:
            sun_elevations.append(loc.solar_elevation(t))
        return times, sun_elevations

    def get_sunrise_sunset(
        self, day: datetime.date
    ) -> tuple[datetime.datetime, datetime.datetime]:
        sun = astral.sun.sun(self.here().observer, date=day)
        return sun["sunrise"].astimezone(), sun["sunset"].astimezone()

    def get_current_sun_elevation(self, timestamp: datetime.datetime) -> float:
        loc = astral.location.Location(self.here())
        return loc.solar_elevation(timestamp)

    def render(self, timestamp: datetime.datetime) -> Image.Image:
        # round timestamp to closest 15 minutes (round to nearest)
        rounding_interval = datetime.timedelta(minutes=15)
        timestamp = timestamp + rounding_interval / 2
        start_of_day = datetime.datetime.combine(
            timestamp.date(), datetime.time()
        ).astimezone()
        timestamp = timestamp - (timestamp - start_of_day) % rounding_interval

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
            "size": self.axis_label_font_size * font_px,
        }

        matplotlib.rc("font", **font)

        fig = plt.figure(figsize=(self.size[0] * px, self.size[1] * px), dpi=dpi)

        ax = fig.add_subplot(axes_class=AxesZero)
        start_of_day = datetime.datetime.combine(
            timestamp.date(), datetime.time()
        ).astimezone()
        ax.set_xlim(start_of_day, start_of_day + datetime.timedelta(days=1))

        # plot sun height
        ax.plot(*self.get_sun_trace(timestamp.date()), color="black", linewidth=2)

        # annotate sunrise and sunset
        sunrise, sunset = self.get_sunrise_sunset(timestamp.date())
        ax.plot([sunrise, sunrise], [0, -10], color="black", linewidth=2)
        ax.plot([sunset, sunset], [0, -10], color="black", linewidth=2)
        ax.text(
            sunrise,
            -7,
            f"↗ {sunrise.hour:02d}:{sunrise.minute:02d}",
            ha="left",
            va="top",
            fontsize=self.time_label_font_size * font_px,
        )
        ax.text(
            sunset - datetime.timedelta(minutes=10),
            -7,
            f"↘ {sunset.hour:02d}:{sunset.minute:02d}",
            ha="right",
            va="top",
            fontsize=self.time_label_font_size * font_px,
        )

        # annotate total daylight
        daylight = sunset - sunrise
        midsun = sunrise + daylight / 2
        ax.text(
            midsun,
            -7,
            f"☀ {daylight.seconds // 3600:02d}:{(daylight.seconds // 60) % 60:02d}",
            ha="center",
            va="top",
            fontsize=self.time_label_font_size * font_px,
        )

        # plot current sun position
        ax.text(
            timestamp,
            self.get_current_sun_elevation(timestamp) - 6 / self.size[1] * 200,
            "☀",
            ha="center",
            va="center",
            fontsize=30,
        )

        xticks = []
        ax.set_xticks(xticks, labels=[x.strftime("%H:%M") for x in xticks])

        yticks = range(-90, 90 + 1, 30)
        ax.set_yticks(yticks, labels=[f"{y:.0f}°" for y in yticks])

        ax.set_ylim(-91, 91)
        ax.grid(True)
        ax.axis["xzero"].set_visible(True)
        ax.axis["bottom"].set_visible(False)
        ax.axis["top"].set_visible(False)
        ax.axis["right"].set_visible(False)

        fig.tight_layout(pad=0, rect=(0, 0.1, 1, 1))
        buf = io.BytesIO()
        fig.savefig(buf)
        fig.clf()

        buf.seek(0)
        img = Image.open(buf)
        return img
