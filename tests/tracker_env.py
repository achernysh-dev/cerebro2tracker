# coding: utf-8
"""Shared TrackerClient factory for sample scripts (env-based credentials)."""

import os

from yandex_tracker_client import TrackerClient


def _load_dotenv():
    """Load repo-root .env into os.environ (only keys not already set)."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def make_client():
    _load_dotenv()
    """
    OAuth + org (typical Tracker Cloud / Yandex 360):

        TRACKER_TOKEN       OAuth token
        TRACKER_ORG_ID      X-Org-Id (numeric org id), or
        TRACKER_CLOUD_ORG_ID  X-Cloud-Org-Id (cloud org id like bpf...)

    IAM (Yandex Cloud org only):

        TRACKER_IAM_TOKEN   short-lived IAM bearer
        TRACKER_CLOUD_ORG_ID  required with IAM
    """
    token = os.environ.get("TRACKER_TOKEN")
    iam_token = os.environ.get("TRACKER_IAM_TOKEN")
    org_id = os.environ.get("TRACKER_ORG_ID")
    cloud_org_id = os.environ.get("TRACKER_CLOUD_ORG_ID")

    if iam_token:
        if not cloud_org_id:
            raise SystemExit(
                "TRACKER_IAM_TOKEN requires TRACKER_CLOUD_ORG_ID "
                "(see yandex_tracker_client.Connection)."
            )
        return TrackerClient(iam_token=iam_token, cloud_org_id=cloud_org_id)

    if not token:
        raise SystemExit("Set TRACKER_TOKEN or TRACKER_IAM_TOKEN.")

    if cloud_org_id and org_id:
        raise SystemExit("Use either TRACKER_ORG_ID or TRACKER_CLOUD_ORG_ID, not both.")

    if cloud_org_id:
        return TrackerClient(token=token, cloud_org_id=cloud_org_id)
    if org_id:
        return TrackerClient(token=token, org_id=org_id)

    raise SystemExit("Set TRACKER_ORG_ID or TRACKER_CLOUD_ORG_ID with TRACKER_TOKEN.")
