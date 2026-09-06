from __future__ import annotations

import logging
import re
import sys

_SENSITIVE = re.compile(
    r"(initData|init_data|hash=|auth_token|access_token|api[_-]?key|secret|token)=[^\s&\"']+",
    re.IGNORECASE,
)


class SanitizingFilter(logging.Filter):
    """Strips credentials/initData out of anything that reaches the logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        redacted = _SENSITIVE.sub(lambda m: m.group(0).split("=")[0] + "=[REDACTED]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SanitizingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    return logging.getLogger("remarka")


logger = configure_logging()
