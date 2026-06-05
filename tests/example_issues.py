# coding: utf-8
"""
Examples: issues (tasks) — list from Tracker, then read/refresh one from that list.

Uses POST /v2/issues/_search via TrackerClient.issues.find() (no issue keys in code).

Env (see tracker_env.py for auth):

    TRACKER_TOKEN, TRACKER_ORG_ID or TRACKER_CLOUD_ORG_ID

Optional:

    EXAMPLE_ISSUE_QUERY   Tracker query string (default: Assignee: me())
    EXAMPLE_QUEUE         queue key for new task (if unset, taken from first listed issue)
    EXAMPLE_ISSUE_PER_PAGE  how many issues to fetch (default 15)
    EXAMPLE_ISSUE_TYPE    fallback type if search returns no issues (name in that queue)
    EXAMPLE_SKIP_SCRIPT_TASK  if true, do not create the script_task issue
"""

from __future__ import print_function

import os
import sys

from tracker_env import make_client


def _queue_key(issue):
    q = getattr(issue, "queue", None)
    if q is None:
        return None
    if isinstance(q, str):
        return q
    key = getattr(q, "key", None)
    if key:
        return key
    if isinstance(q, dict):
        return q.get("key")
    return None


def _type_create_payload(issue):
    """
    Build the ``type`` object for issues.create from an existing issue in the same queue.
    Prefer ``key`` (stable), then ``id``, then ``name`` (localized — must match queue).
    """
    t = None
    if hasattr(issue, "_value") and isinstance(issue._value, dict):
        t = issue._value.get("type")
    if t is None:
        t = getattr(issue, "type", None)
    if t is None:
        return None

    if isinstance(t, dict):
        td = t
    elif hasattr(t, "_value") and isinstance(t._value, dict):
        td = t._value
    elif hasattr(t, "as_dict"):
        td = t.as_dict()
    else:
        td = {}
        for attr in ("key", "id", "name"):
            v = getattr(t, attr, None)
            if v is not None:
                td[attr] = v

    if not td:
        return None
    if td.get("key"):
        return {"key": td["key"]}
    if td.get("id") is not None:
        return {"id": td["id"]}
    if td.get("name"):
        return {"name": td["name"]}
    return None


def _brief(issue):
    status = getattr(issue, "status", None)
    if status is not None and not isinstance(status, (str, int, float, bool)):
        status = getattr(status, "key", None) or getattr(status, "display", status)
    assignee = getattr(issue, "assignee", None)
    if assignee is not None and not isinstance(assignee, (str, type(None))):
        assignee = getattr(assignee, "display", None) or getattr(assignee, "id", assignee)
    return issue.key, issue.summary, status, assignee


def main():
    client = make_client()
    queue = os.environ.get("EXAMPLE_QUEUE")
    per_page = int(os.environ.get("EXAMPLE_ISSUE_PER_PAGE", "15"))
    query = os.environ.get("EXAMPLE_ISSUE_QUERY", "Assignee: me()")

    # --- List tasks from Tracker (no issue keys required) ---
    found = list(client.issues.find(query=query, per_page=per_page, order=["-updatedAt"]))
    print("Query %r -> %s issue(s)" % (query, len(found)))
    for issue in found:
        key, summary, status, assignee = _brief(issue)
        print(" ", key, "|", status, "|", assignee)
        print("     ", summary[:120] + ("..." if len(summary) > 120 else ""))

    if queue:
        by_queue = list(
            client.issues.find(
                filter={"queue": queue},
                order=["-updatedAt"],
                per_page=per_page,
            )
        )
        print("Queue filter %r -> %s issue(s)" % (queue, len(by_queue)))
        for issue in by_queue:
            print(" ", *_brief(issue)[:2])

    # --- Read / refresh: use first issue returned by the main query ---
    if found:
        issue = found[0]
        key, summary, status, assignee = _brief(issue)
        print("Detail (first hit):", key)
        print("  summary:", summary)
        print("  status:", status, " assignee:", assignee)
        issue.update()
        print("  refreshed from API OK")
    else:
        print("No issues for that query — widen EXAMPLE_ISSUE_QUERY or check permissions.")

    # --- Create task "script_task", assignee = first org user ---
    if os.environ.get("EXAMPLE_SKIP_SCRIPT_TASK", "").lower() in ("1", "true", "yes"):
        print("Skipping script_task create (EXAMPLE_SKIP_SCRIPT_TASK).")
        return 0

    users = list(client.users)
    if not users:
        print("No users returned from Tracker; cannot assign script_task.")
        return 1

    first_user = users[0]
    assignee_login = getattr(first_user, "login", None) or getattr(first_user, "id", None)
    print("First user (assignee):", assignee_login, getattr(first_user, "display", ""))

    queue_key = queue
    if not queue_key and found:
        queue_key = _queue_key(found[0])
    if not queue_key:
        print(
            "Cannot create script_task: set EXAMPLE_QUEUE or run a query that returns "
            "at least one issue (queue is taken from the first hit)."
        )
        return 1

    type_spec = None
    if found:
        type_spec = _type_create_payload(found[0])
    if type_spec is None:
        fallback = os.environ.get("EXAMPLE_ISSUE_TYPE")
        if fallback:
            type_spec = {"name": fallback}
    if type_spec is None:
        print(
            "Cannot determine issue type: need at least one search hit (type is copied "
            "from the first issue) or set EXAMPLE_ISSUE_TYPE to a valid type name in the queue."
        )
        return 1

    print("Create issue type:", type_spec)

    created = client.issues.create(
        queue=queue_key,
        summary="script_task",
        type=type_spec,
        assignee=assignee_login,
        description="Created by tests/example_issues.py",
    )
    print("Created script_task:", created.key, "| assignee:", assignee_login)

    return 0


if __name__ == "__main__":
    sys.exit(main())
