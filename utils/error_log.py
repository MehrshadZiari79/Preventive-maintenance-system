# utils/error_log.py
"""
Small error log for problems that the program handles silently (for example
a page that fails while the main window closes).  The packaged EXE has no
console, so these would otherwise be invisible.

File: %LOCALAPPDATA%\\GelaDairy\\PMSystem\\error.log  (kept below ~512 KB)
"""

import datetime
import os
import tempfile
import traceback
from pathlib import Path

_MAX_BYTES = 512 * 1024


def log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "GelaDairy" / "PMSystem" / "error.log"


def log_error(context, exc=None):
    """Append one entry (with traceback when `exc` is given). Never raises."""
    print(context, exc if exc is not None else "")
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _MAX_BYTES:
            path.replace(path.with_name("error.old.log"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {context}")
            if exc is not None:
                fh.write(f": {exc!r}\n")
                fh.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            fh.write("\n")
    except Exception:
        pass
