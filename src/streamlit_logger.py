import logging
import os

_ORANGE = "\033[38;5;208m"
_RESET = "\033[0m"

LEVEL_EMOJI = {
    logging.DEBUG: "🔍",
    logging.INFO: "📦",
    logging.WARNING: "⚠️",
    logging.ERROR: "❌",
    logging.CRITICAL: "💥",
}


class EmojiFormatter(logging.Formatter):
    def __init__(self, session):
        self.session = session

    def format(self, record):
        emoji = LEVEL_EMOJI.get(record.levelno, "•")
        ts = self.formatTime(record, "%H:%M:%S")
        name = record.name
        msg = record.getMessage()
        line = f"[{_ORANGE}{ts}{_RESET}] {emoji} [{name}] {msg} [session: {self.session}]"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(session) -> logging.Logger:
    log_level_str = os.getenv("STREAMLIT_LOGGER_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)

    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.WARNING:
        root.setLevel(logging.WARNING)

    handler = logging.StreamHandler()
    handler.setFormatter(EmojiFormatter(session))

    for name in ("zhp_autokiw", "src"):
        lg = logging.getLogger(name)
        lg.setLevel(numeric_level)
        lg.propagate = False
        if not lg.handlers:
            lg.addHandler(handler)

    return logging.getLogger("zhp_autokiw")
