import logging
from pathlib import Path


LOGGER_NAME = "MediaDownloader"
APP_DATA_DIR = Path.home() / ".media_downloader"
LOG_DIR = APP_DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logger(enable_console=False):
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    has_file_handler = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")) == LOG_FILE
        for handler in logger.handlers
    )
    if not has_file_handler:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if enable_console:
        has_console_handler = any(
            isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, logging.FileHandler)
            for handler in logger.handlers
        )
        if not has_console_handler:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger


logger = logging.getLogger(LOGGER_NAME)
