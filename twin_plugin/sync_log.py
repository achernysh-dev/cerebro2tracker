# coding: utf-8
"""User-visible sync logging (Cerebro print_* is unreliable in twin plugins)."""
import os
import sys
import time

from . import sync_settings

_ui_callback = None
_activity_log_name = "sync_activity.log"


def get_activity_log_path():
    return os.path.join(sync_settings.get_settings_dir(), _activity_log_name)


def set_ui_callback(callback):
    """callback(line: str) — called on UI thread from sync code."""
    global _ui_callback
    _ui_callback = callback


def clear_ui_callback():
    global _ui_callback
    _ui_callback = None


def log(message):
    """Append timestamped line to activity log file and optional UI panel."""
    text = str(message).strip()
    if not text:
        return
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), text)

    try:
        folder = sync_settings.get_settings_dir()
        os.makedirs(folder, exist_ok=True)
        with open(get_activity_log_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass

    cb = _ui_callback
    if cb is not None:
        try:
            cb(line)
        except Exception:
            pass

    try:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
    except Exception:
        pass
