import datetime
import json
import logging
import pathlib
import time

from renderer.apps.dashboard.app import DashboardApp, DashboardScreenConfig
from renderer.apps.dashboard.influx import InfluxDBCurrentValue, InfluxDBTrend
from renderer.apps.dashboard.sun import SunriseSunsetWidget
from renderer.apps.dashboard.weather import WeatherWidget
from renderer.apps.hiking_quiz.app import HikingQuizApp

HERE = pathlib.Path(__file__).parent


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s", level=logging.INFO
    )

    logger = logging.getLogger(__name__.split(".")[0])
    logger.info("starting")

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
                            position=(70, 480 // 4 - 90),
                            size=(250, 2 * 90),
                            url="http://192.168.178.222:8086",
                            data_fields=[
                                {
                                    "sensor_id": 1,
                                    "field": "temperature",
                                    "label": "Temperatur",
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
                        InfluxDBTrend(
                            position=(405, 10),
                            size=(385 + 10, 230),
                            url="http://192.168.178.222:8086",
                            data_field="temperature",
                            sensor_id="1",
                        ),
                        InfluxDBTrend(
                            position=(10, 240),
                            size=(385 + 10, 230),
                            url="http://192.168.178.222:8086",
                            data_field="humidity",
                            sensor_id="1",
                        ),
                        InfluxDBTrend(
                            position=(405, 240),
                            size=(385 + 10, 230),
                            url="http://192.168.178.222:8086",
                            data_field="co2",
                            sensor_id="1",
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
