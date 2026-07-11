from __future__ import annotations

import time

# Set when the process imports this module (i.e. at startup).
START_TIME = time.monotonic()


def uptime_seconds() -> int:
    return int(time.monotonic() - START_TIME)
