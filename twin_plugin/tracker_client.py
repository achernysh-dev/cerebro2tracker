# coding: utf-8
"""TrackerClient factory for the Cerebro plugin (no SystemExit)."""
import os
import sys


def _ensure_tracker_importable():
    try:
        import yandex_tracker_client  # noqa: F401
        return
    except ImportError:
        pass
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.join(repo_root, "vendor", "site-packages"),
        os.path.join(repo_root, ".venv", "Lib", "site-packages"),
        os.path.join(repo_root, ".venv", "lib", "site-packages"),
    ]
    for path in candidates:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
    try:
        import yandex_tracker_client  # noqa: F401
    except ImportError:
        pass


def make_client(token=None, cloud_org_id=None, org_id=None):
    """
    Returns (client, error_message).
    error_message is None on success.
    """
    _ensure_tracker_importable()
    try:
        from yandex_tracker_client import TrackerClient
    except ImportError:
        return None, (
            "yandex_tracker_client is not installed. "
            "Run scripts\\vendor_deps.bat or install yandex-tracker-client into the project vendor folder."
        )

    token = (token or "").strip() or None
    cloud_org_id = (cloud_org_id or "").strip() or None
    org_id = (org_id or "").strip() or None

    if not token:
        return None, "TRACKER_TOKEN is not set."
    if cloud_org_id and org_id:
        return None, "Use either TRACKER_CLOUD_ORG_ID or TRACKER_ORG_ID, not both."
    if cloud_org_id:
        return TrackerClient(token=token, cloud_org_id=cloud_org_id), None
    if org_id:
        return TrackerClient(token=token, org_id=org_id), None
    return None, "Set TRACKER_CLOUD_ORG_ID (or TRACKER_ORG_ID)."


def make_client_from_settings(settings):
    org_type = (settings.get("tracker_org_id_type") or "cloud").strip()
    if org_type == "org":
        return make_client(
            token=settings.get("tracker_token"),
            org_id=settings.get("tracker_org_id"),
        )
    return make_client(
        token=settings.get("tracker_token"),
        cloud_org_id=settings.get("tracker_cloud_org_id"),
    )
