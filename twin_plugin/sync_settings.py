# coding: utf-8
"""Persist Tracker sync configuration in the plugin package directory."""
import json
import os
import shutil

from .status_map import DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY, normalize_cerebro_status_name

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

ORG_ID_TYPE_CLOUD = "cloud"
ORG_ID_TYPE_LEGACY = "org"

DEFAULT_SETTINGS = {
    "tracker_token": "",
    "tracker_org_id_type": ORG_ID_TYPE_CLOUD,
    "tracker_cloud_org_id": "",
    "tracker_org_id": "",
    "parent_portfolio_id": "",
    "selected_tracker_portfolio_id": "",
    "checked_cerebro_task_ids": [],
    "task_map": {},
    "queue_keys": {},
    "status_map": {},
}


def get_package_dir():
    return _PACKAGE_DIR


def get_legacy_settings_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "cerebro2tracker")
    return os.path.join(os.path.expanduser("~"), ".cerebro2tracker")


def get_settings_dir():
    """User-specific config outside the repo (safe for clone/pull)."""
    return get_legacy_settings_dir()


def get_settings_path():
    return os.path.join(get_settings_dir(), "sync_settings.json")


def _package_settings_path():
    return os.path.join(get_package_dir(), "sync_settings.json")


def get_status_map_path():
    return os.path.join(get_package_dir(), "status_map.json")


def _legacy_status_map_path():
    return os.path.join(get_legacy_settings_dir(), "status_map.json")


def _settings_has_user_data(path):
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return False
        if (data.get("tracker_token") or "").strip():
            return True
        if (data.get("tracker_cloud_org_id") or "").strip():
            return True
        if (data.get("tracker_org_id") or "").strip():
            return True
        if data.get("task_map"):
            return True
        if data.get("checked_cerebro_task_ids"):
            return True
        if data.get("queue_keys"):
            return True
    except Exception:
        pass
    return False


def _copy_file(src, dest):
    try:
        shutil.copy2(src, dest)
        return True
    except Exception:
        return False


def _migrate_package_settings():
    """One-time: copy twin_plugin/sync_settings.json into AppData if it has user data."""
    package = _package_settings_path()
    dest = get_settings_path()
    if not os.path.isfile(package):
        return False
    if _settings_has_user_data(dest):
        return False
    if not _settings_has_user_data(package):
        return False
    os.makedirs(get_settings_dir(), exist_ok=True)
    return _copy_file(package, dest)


def _migrate_legacy_status_map():
    legacy = _legacy_status_map_path()
    package = get_status_map_path()
    if not os.path.isfile(legacy) or os.path.isfile(package):
        return False
    return _copy_file(legacy, package)


def default_status_map():
    return dict(DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY)


def normalize_status_map(raw):
    """Normalize Cerebro status name keys; values are Tracker status API keys."""
    out = {}
    for cerebro_name, tracker_key in (raw or {}).items():
        key = normalize_cerebro_status_name(cerebro_name)
        if not key:
            continue
        tracker = str(tracker_key or "").strip()
        if tracker:
            out[key] = tracker
    return out


def ensure_status_map_file():
    """Create package status_map.json from built-in defaults if it does not exist yet."""
    path = get_status_map_path()
    if not os.path.isfile(path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(default_status_map(), fh, ensure_ascii=False, indent=2, sort_keys=True)
    return path


def ensure_sync_settings_file():
    path = get_settings_path()
    if os.path.isfile(path):
        return path
    os.makedirs(get_settings_dir(), exist_ok=True)
    example = os.path.join(get_package_dir(), "sync_settings.json.example")
    if os.path.isfile(example):
        _copy_file(example, path)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(dict(DEFAULT_SETTINGS), fh, ensure_ascii=False, indent=2)
    return path


def ensure_config_files():
    """
    Ensure package JSON config files exist.
    One-time migration: copy repo-local settings into AppData when needed.
    """
    ensure_sync_settings_file()
    _migrate_package_settings()
    _migrate_legacy_status_map()
    ensure_status_map_file()
    return get_settings_path()


def load_status_map(settings=None):
    """
    Effective Cerebro status name -> Tracker status key map.
    Built-in defaults, overridden by package status_map.json, then sync_settings status_map.
    """
    merged = default_status_map()
    path = get_status_map_path()
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict) and stored:
                merged.update(normalize_status_map(stored))
        except Exception:
            pass
    if settings is None:
        settings = load()
    merged.update(normalize_status_map(settings.get("status_map") or {}))
    return merged


def _repo_env_path():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".env")
    )


def _load_dotenv_fallback():
    """Fill missing keys from repo .env (dev convenience; saved file wins)."""
    path = _repo_env_path()
    if not os.path.isfile(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            mapping = {
                "TRACKER_TOKEN": "tracker_token",
                "TRACKER_CLOUD_ORG_ID": "tracker_cloud_org_id",
                "TRACKER_ORG_ID": "tracker_org_id",
                "PARENT_PORTFOLIO_ID": "parent_portfolio_id",
            }
            if key in mapping:
                out[mapping[key]] = val
    return out


def load():
    ensure_config_files()
    path = get_settings_path()
    data = dict(DEFAULT_SETTINGS)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                data.update(stored)
        except Exception:
            pass
    fallback = _load_dotenv_fallback()
    for key, val in fallback.items():
        if not data.get(key):
            data[key] = val
    data["checked_cerebro_task_ids"] = [
        int(x) for x in (data.get("checked_cerebro_task_ids") or [])
    ]
    data["task_map"] = normalize_task_map(data.get("task_map") or {})
    queue_keys = data.get("queue_keys") or {}
    data["queue_keys"] = {str(k): v for k, v in queue_keys.items()}
    return data


def save(settings):
    ensure_config_files()
    path = get_settings_path()
    out = dict(DEFAULT_SETTINGS)
    out.update(settings or {})
    out["checked_cerebro_task_ids"] = list(out.get("checked_cerebro_task_ids") or [])
    out["task_map"] = normalize_task_map(out.get("task_map") or {})
    out["queue_keys"] = {str(k): v for k, v in (out.get("queue_keys") or {}).items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return path


def tracker_issue_url(issue_key):
    return "https://tracker.yandex.ru/%s" % issue_key


def normalize_task_map(task_map):
    """task_map values: {key, url} (legacy: plain issue key string)."""
    out = {}
    for cerebro_id, value in (task_map or {}).items():
        if isinstance(value, dict):
            key = value.get("key") or value.get("issue_key")
            if not key:
                continue
            out[str(cerebro_id)] = {
                "key": str(key),
                "url": value.get("url") or tracker_issue_url(key),
            }
        elif value:
            key = str(value)
            out[str(cerebro_id)] = {"key": key, "url": tracker_issue_url(key)}
    return out


def task_map_issue_key(entry):
    if isinstance(entry, dict):
        return entry.get("key")
    return entry


def tracker_org_id_type(settings=None):
    s = settings or load()
    org_type = (s.get("tracker_org_id_type") or ORG_ID_TYPE_CLOUD).strip()
    if org_type not in (ORG_ID_TYPE_CLOUD, ORG_ID_TYPE_LEGACY):
        org_type = ORG_ID_TYPE_CLOUD
    return org_type


def active_tracker_org_id(settings=None):
    s = settings or load()
    if tracker_org_id_type(s) == ORG_ID_TYPE_LEGACY:
        return (s.get("tracker_org_id") or "").strip()
    return (s.get("tracker_cloud_org_id") or "").strip()


def has_tracker_credentials(settings=None):
    s = settings or load()
    return bool((s.get("tracker_token") or "").strip()) and bool(active_tracker_org_id(s))
