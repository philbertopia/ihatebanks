import logging
import logging.handlers
import os


def setup_logging(level: str = "INFO", log_file: str = "logs/ovtlyr.log",
                  max_bytes: int = 5_242_880, backup_count: int = 3) -> None:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not root.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        root.addHandler(ch)

        # Rotating file handler
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
