import datetime
import json
import logging
import pathlib
import time

from renderer.apps.dashboard.app import DashboardApp, DashboardScreenConfig
from renderer.apps.dashboard.influx import (
    InfluxDBCurrentValue,
    InfluxDBTrend,
    InfluxDBTrendCompareToYesterday,
    TrendAggregation,
)
from renderer.apps.dashboard.sun import SunriseSunsetWidget
from renderer.apps.dashboard.weather import WeatherWidget
from renderer.apps.hiking_quiz.app import HikingQuizApp
from renderer.config import INFLUXDB_URL

HERE = pathlib.Path(__file__).parent


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s", level=logging.INFO
    )

    logger = logging.getLogger(__name__.split(".")[0])
    logger.info("starting")

    air_quality_long_term_history_h = 56 * 24  # 56 days
    air_quality_long_term_aggregations = [
        TrendAggregation(
            interval_min=24 * 60,
            function="min",
            linewidth=1,
            linestyle="dotted",
        ),
        TrendAggregation(interval_min=24 * 60, function="median", linewidth=2),
        TrendAggregation(
            interval_min=24 * 60,
            function="max",
            linewidth=1,
            linestyle="dotted",
        ),
    ]

    apps = [
        HikingQuizApp(),
        DashboardApp(
            [
                DashboardScreenConfig(
                    [
                        SunriseSunsetWidget(
                            position=(10, 10),
                            size=(780, 210),
                            latitude=48.74,
                            longitude=9.31,
                        ),
                        WeatherWidget(
                            position=(10, 210),
                            size=(780, 480 - 10 - 210),
                            latitude=48.74,
                            longitude=9.31,
                            days=7,
                            infos=[
                                "weather_symbol",
                                "weather_summary",
                                "spacer",
                                "temperature_min_max",
                                "spacer",
                                "uv_index",
                                "spacer",
                                "precipitation_total",
                                "precipitation_hourly",
                            ],
                        ),
                    ]
                ),
            ]
        ),
        DashboardApp(
            [
                DashboardScreenConfig(
                    [
                        InfluxDBCurrentValue(
                            position=(800 // 4 - 150, 480 // 4 - 2 * 50),
                            size=(2 * 150, 4 * 50),
                            url=INFLUXDB_URL,
                            data_fields=[
                                {
                                    "sensor_id": 1,
                                    "field": "temperature",
                                    "label": "Temperatur",
                                },
                                {
                                    "sensor_id": 3,
                                    "field": "temperature",
                                    "label": "Temperatur (Balkon)",
                                },
                                {
                                    "sensor_id": 1,
                                    "field": "humidity",
                                    "label": "Luftfeuchtigkeit",
                                },
                                {
                                    "sensor_id": 1,
                                    "field": "co2",
                                    "label": "CO₂ Gehalt",
                                },
                            ],
                            alignment="vertical",
                        ),
                        InfluxDBTrendCompareToYesterday(
                            position=(405, 10),
                            size=(385 + 10, 230),
                            url=INFLUXDB_URL,
                            data_field="temperature",
                            sensor_id="1",
                        ),
                        InfluxDBTrendCompareToYesterday(
                            position=(10, 240),
                            size=(385 + 10, 230),
                            url=INFLUXDB_URL,
                            data_field="humidity",
                            sensor_id="1",
                        ),
                        InfluxDBTrendCompareToYesterday(
                            position=(405, 240),
                            size=(385 + 10, 230),
                            url=INFLUXDB_URL,
                            data_field="co2",
                            sensor_id="1",
                        ),
                    ]
                ),
                DashboardScreenConfig(
                    [
                        InfluxDBTrend(
                            position=(10, 10),
                            size=(800 - 10 - 10, 230),
                            url=INFLUXDB_URL,
                            data_field="temperature",
                            sensor_id="1",
                            aggregations=air_quality_long_term_aggregations,
                            history_h=air_quality_long_term_history_h,
                        ),
                        InfluxDBTrend(
                            position=(10, 10 + 230),
                            size=(800 - 10 - 10, 230),
                            url=INFLUXDB_URL,
                            data_field="temperature",
                            sensor_id="3",
                            aggregations=air_quality_long_term_aggregations,
                            history_h=air_quality_long_term_history_h,
                        ),
                    ]
                ),
            ]
        ),
    ]

    static = pathlib.Path(HERE / "../static")
    now = datetime.datetime.now().astimezone()
    with open(static / "info.json", "w") as f:
        json.dump(
            {
                "last_updated": now.isoformat(),
                "apps": [
                    {"name": app.name, "nb_screens": app.get_nb_screens()}
                    for app in apps
                ],
            },
            f,
        )
    for nb, app in enumerate(apps):
        folder = static / "app" / str(nb)
        start = time.time()
        app.render(now, folder)
        end = time.time()
        logger.info(f"Rendered app {app.name} in {end - start:.2f}s")

    logger.info("finished")


if __name__ == "__main__":
    main()
