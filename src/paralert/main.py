import logging

import uvicorn

from paralert.adapters.storage.sqlite import init_db
from paralert.config import get_app_config
from paralert.entrypoints.api import app  # noqa: F401 — registers routes
from paralert.entrypoints.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


def main() -> None:
    cfg = get_app_config()
    init_db(cfg.db_path)
    scheduler = start_scheduler(cfg.db_path)
    scheduler.start()
    uvicorn.run(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
