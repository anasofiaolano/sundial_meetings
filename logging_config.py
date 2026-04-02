# Logging configuration for Sundial CRM
#
# Best practice:
# - Rotating file logs in logs/ folder (gitignored, survives process restarts)
# - Structured format: timestamp | level | component | message
# - RotatingFileHandler: 10MB per file, 10 backups = 100MB max on disk
# - Log levels:
#     INFO    — normal operations (API calls, file writes, git ops, state transitions)
#     WARNING — unexpected but recoverable (edit failed, retrying)
#     ERROR   — failures that need attention (always with full stack trace)
# - Do NOT log full transcript content (large + potentially sensitive)
# - Do NOT log API keys or credentials

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

FMT = "%(asctime)s %(levelname)-8s %(name)-22s — %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Call once at server startup. Adds file + stderr handlers to the root logger."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. uvicorn called this twice)

    root.setLevel(level)
    formatter = logging.Formatter(FMT, datefmt=DATE_FMT)

    # ── File handler — rotating, survives restarts ────────────────────────
    file_handler = RotatingFileHandler(
        LOG_DIR / "sundial.log",
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # ── stderr — so uvicorn/pm2 stdout logs still show something ─────────
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
