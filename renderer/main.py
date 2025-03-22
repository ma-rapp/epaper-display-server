import datetime
import json
import logging
import pathlib
import time

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
