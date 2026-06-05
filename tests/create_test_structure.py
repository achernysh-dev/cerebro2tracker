# coding: utf-8
"""
Create a test Tracker structure in three steps (idempotent where possible):

  1) Entity *project* nested under portfolio «анимационный портфель» (shortId 11)
  2) *Queue* with a fixed key/name (Latin key, max 15 chars)
  3) *Tasks* (25) with hierarchy, Gantt dates, dependency links, and varied statuses

Tasks use the ``parent`` field (subtask links in Tracker). Additionally creates
``depends on`` links along the tree and between siblings. Statuses are set via
workflow transitions (Открыт, В работе, Ревью, Решён, …).

Before each create, checks whether the object already exists and reuses it.

Run (from tests/, loads ../.env via tracker_env):

    python create_test_structure.py

Env:

    PARENT_PORTFOLIO_ID   portfolio entity id or shortId (default: 11)
    PROJECT_NAME          project title (default: Cerebro Test Animation Project)
    QUEUE_KEY             queue key (default: CBROTESTANIM)
    QUEUE_NAME            queue display name (default: Cerebro Test Animation Queue)
    PROJECT_NAME_STAMP=1  append UTC date to project name (non-idempotent)
    QUEUE_WORKFLOW        workflow for new queue (default: developmentPresetWorkflow)
    GANTT_BASE_OFFSET     days from today for first task start (default: 1)
    TRACKER_CREATE_RUN=0  print only, no API writes
"""

from __future__ import print_function

import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

from tracker_env import make_client
from yandex_tracker_client import exceptions as tracker_exc

DEFAULT_PORTFOLIO_ID = "6a0819662fb5d761f50993a3"
DEFAULT_PORTFOLIO_SHORT_ID = 11

# Fixed names for later verification (override via env if needed).
DEFAULT_PROJECT_NAME = "Cerebro Test Animation Project"
DEFAULT_QUEUE_KEY = "CBROTESTANIM"
DEFAULT_QUEUE_NAME = "Cerebro Test Animation Queue"

# Was 5 tasks (1 + 3 children + 1 grandchild); now 5×.
TASK_CHILDREN_COUNT = 8
TASK_GRANDCHILDREN_PER_CHILD = 2

# Workflow transitions → target status id (developmentPresetWorkflow).
STATUS_TRANSITIONS = (
    "start_progress",  # В работе
    "need_info",  # Требуется информация
    "in_review",  # Ревью
    "resolve",  # Решён
    "close",  # Закрыт
    "ready_for_test",  # Можно тестировать
)
TARGET_STATUS_BY_TRANSITION = {
    "start_progress": "3",
    "need_info": "2",
    "in_review": "6",
    "resolve": "7",
    "close": "8",
    "wont_fix": "8",
    "ready_for_test": "12",
}
TRANSITION_EXECUTE_KWARGS = {
    "close": {"resolution": "fixed"},
    "wont_fix": {"resolution": "wontFix"},
}
LINK_TYPE_DEPENDS = ("depends",)
LINK_TYPE_SUBTASK = ("subtask",)


def _headers(client):
    return dict(client._connection.session.headers)


def _run_enabled():
    return os.environ.get("TRACKER_CREATE_RUN", "1").lower() not in (
        "0",
        "false",
        "no",
    )


def _resolve_portfolio_id(client, portfolio_ref):
    ref = str(portfolio_ref).strip()
    if len(ref) > 12:
        return ref
    url = client._connection.build_url("/v3/entities/portfolio/_search")
    resp = client._connection.session.post(
        url,
        params={"perPage": 50, "fields": "summary"},
        json={},
        headers=_headers(client),
        timeout=client._connection.timeout,
    )
    resp.raise_for_status()
    for item in resp.json().get("values") or []:
        if str(item.get("shortId")) == ref or item.get("id") == ref:
            return item.get("id")
    raise ValueError("Portfolio not found for ref %r" % portfolio_ref)


def queue_key_from_project_name(project_name):
    letters = re.sub(r"[^A-Za-z]", "", project_name or "")
    if not letters:
        letters = "TEST"
    return letters.upper()[:15]


def _lead_login(client):
    me = client.myself
    if hasattr(me, "_value"):
        return me._value.get("login") or me._value.get("id")
    if isinstance(me, dict):
        return me.get("login") or me.get("id")
    return getattr(me, "login", None) or getattr(me, "id", None)


def _parent_entity_id(fields):
    pe = (fields or {}).get("parentEntity") or {}
    primary = pe.get("primary") or {}
    return primary.get("id")


# --- Lookups ------------------------------------------------------------------


def find_entity_project(client, project_name, portfolio_id):
    """
    Search entity projects by exact summary + parent portfolio.
    Tracker allows duplicate names on create — returns first match or None.
    """
    portfolio_id = _resolve_portfolio_id(client, portfolio_id)
    url = client._connection.build_url("/v3/entities/project/_search")
    resp = client._connection.session.post(
        url,
        params={"perPage": 50, "fields": "summary,parentEntity"},
        json={"filter": {"summary": project_name}},
        headers=_headers(client),
        timeout=client._connection.timeout,
    )
    if not resp.ok:
        return None
    for item in resp.json().get("values") or []:
        fields = item.get("fields") or {}
        if fields.get("summary") != project_name:
            continue
        if _parent_entity_id(fields) == portfolio_id:
            return {
                "id": item.get("id"),
                "shortId": item.get("shortId"),
                "entityType": item.get("entityType"),
                "fields": fields,
                "existing": True,
            }
    return None


def find_queue(client, queue_key):
    """GET /v3/queues/{key} — 200 if exists."""
    url = client._connection.build_url("/v3/queues/%s" % queue_key)
    resp = client._connection.session.get(
        url, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code == 200:
        data = resp.json()
        data["existing"] = True
        return data
    if resp.status_code == 404:
        return None
    raise RuntimeError("Queue lookup failed: %s %s" % (resp.status_code, resp.text))


def find_issue(client, queue_key, summary):
    """Find issue by queue + exact summary (API filter may be fuzzy)."""
    try:
        batch = list(
            client.issues.find(
                filter={"queue": queue_key, "summary": summary},
                per_page=20,
            )
        )
    except Exception:
        return None
    for issue in batch:
        issue_summary = getattr(issue, "summary", None)
        if issue_summary is None and hasattr(issue, "_value"):
            issue_summary = (issue._value or {}).get("summary")
        if issue_summary == summary:
            return issue
    return None


# --- Snippet 1: project -------------------------------------------------------


def snippet_create_nested_project(client, project_name, portfolio_id):
    portfolio_id = _resolve_portfolio_id(client, portfolio_id)

    print("\n=== 1) Project in portfolio ===")
    existing = find_entity_project(client, project_name, portfolio_id)
    if existing:
        print(
            "Already exists (same name + parent), reusing: id=%s shortId=%s"
            % (existing.get("id"), existing.get("shortId"))
        )
        return existing

    url = client._connection.build_url("/v3/entities/project")
    payload = {
        "fields": {
            "summary": project_name,
            "entityStatus": "draft",
            "parentEntity": {"primary": portfolio_id},
        }
    }
    print("POST", url)
    print("payload:", payload)

    if not _run_enabled():
        print("(dry-run)")
        return {"id": None, "shortId": None, "dryRun": True, "existing": False}

    resp = client._connection.session.post(
        url, json=payload, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code >= 400:
        raise RuntimeError("Create project failed: %s %s" % (resp.status_code, resp.text))
    data = resp.json()
    data["existing"] = False
    print("Created project id=%s shortId=%s" % (data.get("id"), data.get("shortId")))
    return data


# --- Snippet 2: queue ---------------------------------------------------------


def snippet_create_queue(
    client, project_name, queue_key=None, queue_name=None, workflow=None
):
    queue_key = queue_key or os.environ.get("QUEUE_KEY") or DEFAULT_QUEUE_KEY
    queue_name = queue_name or os.environ.get("QUEUE_NAME") or DEFAULT_QUEUE_NAME
    workflow = workflow or os.environ.get(
        "QUEUE_WORKFLOW", "developmentPresetWorkflow"
    )

    print("\n=== 2) Queue ===")
    print("queue key:", queue_key, "name:", queue_name)

    existing = find_queue(client, queue_key)
    if existing:
        print(
            "Already exists, reusing: key=%s id=%s name=%s"
            % (existing.get("key"), existing.get("id"), existing.get("name"))
        )
        return existing

    url = client._connection.build_url("/v3/queues/")
    payload = {
        "key": queue_key,
        "name": queue_name,
        "description": "Queue for project: %s" % project_name,
        "lead": _lead_login(client),
        "defaultType": "task",
        "defaultPriority": "normal",
        "issueTypesConfig": [
            {
                "issueType": "task",
                "workflow": workflow,
                "resolutions": ["fixed", "wontFix", "duplicate", "later"],
            }
        ],
    }
    print("POST", url)
    print("payload:", payload)

    if not _run_enabled():
        print("(dry-run)")
        return {"key": queue_key, "dryRun": True, "existing": False}

    resp = client._connection.session.post(
        url, json=payload, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code == 409:
        again = find_queue(client, queue_key)
        if again:
            print("Create returned 409; reusing existing queue.")
            return again
    if resp.status_code >= 400:
        raise RuntimeError("Create queue failed: %s %s" % (resp.status_code, resp.text))
    data = resp.json()
    data["existing"] = False
    print("Created queue key=%s id=%s" % (data.get("key"), data.get("id")))
    return data


def snippet_link_queue_to_project(client, project_id, queue_key):
    print("\n=== Link queue → project (verify) ===")
    print(
        "Note: attach queue %s to project %s in Tracker UI if needed in «Структура»."
        % (queue_key, project_id)
    )
    if not project_id or not _run_enabled():
        return
    url = client._connection.build_url("/v3/projects/%s/queues" % project_id)
    try:
        resp = client._connection.session.get(
            url, headers=_headers(client), timeout=client._connection.timeout
        )
        if resp.ok:
            keys = [q.get("key") for q in resp.json() if isinstance(q, dict)]
            print("Project queues:", keys)
            if queue_key in keys:
                print("Queue %s is linked." % queue_key)
    except Exception as ex:
        print("Could not list project queues:", ex)


# --- Snippet 3: tasks ---------------------------------------------------------


def _gantt_dates(slot_index, duration_days=7):
    """Stagger start/deadline so bars appear on the Gantt chart."""
    base_offset = int(os.environ.get("GANTT_BASE_OFFSET", "1"))
    start = date.today() + timedelta(days=base_offset + slot_index * 3)
    end = start + timedelta(days=duration_days + (slot_index % 4))
    return start.isoformat(), end.isoformat()


def _task_tree_plan():
    """1 parent + N children + M grandchildren each → 25 tasks by default."""
    rows = [("Parent: core work", None, "parent", 0, 0)]
    for ci in range(1, TASK_CHILDREN_COUNT + 1):
        child_summary = "Child %02d: phase" % ci
        rows.append((child_summary, "Parent: core work", "child", ci, 0))
        for gi in range(1, TASK_GRANDCHILDREN_PER_CHILD + 1):
            rows.append(
                (
                    "Grandchild %02d-%02d: task" % (ci, gi),
                    child_summary,
                    "grandchild",
                    ci,
                    gi,
                )
            )
    return rows


def _dependency_link_specs(plan):
    """
    Build (from_summary, to_summary, relationship) for Gantt dependency arrows.
    Parent-child hierarchy still uses the ``parent`` field (Tracker subtask links).
    """
    specs = []
    prev_child_summary = None
    last_grandchild_by_child = {}

    for summary, parent_summary, role, ci, gi in plan:
        if parent_summary:
            specs.append((summary, parent_summary, "depends on"))
        if role == "child":
            if prev_child_summary:
                specs.append((summary, prev_child_summary, "depends on"))
            prev_child_summary = summary
            last_grandchild_by_child[summary] = None
        elif role == "grandchild":
            prev_g = last_grandchild_by_child.get(parent_summary)
            if prev_g:
                specs.append((summary, prev_g, "depends on"))
            last_grandchild_by_child[parent_summary] = summary

    return specs


def _status_transition_for_row(slot_index, role, child_index, grandchild_index):
    if role == "parent":
        return None
    if role == "child":
        idx = (child_index - 1) % len(STATUS_TRANSITIONS)
    else:
        idx = (grandchild_index + child_index) % len(STATUS_TRANSITIONS)
    return STATUS_TRANSITIONS[idx]


def _issue_ref_key(obj_ref):
    if obj_ref is None:
        return None
    if hasattr(obj_ref, "key"):
        return obj_ref.key
    if isinstance(obj_ref, dict):
        return obj_ref.get("key")
    return str(obj_ref)


def _issue_status_id(issue):
    status = getattr(issue, "status", None)
    if status is None:
        return None
    if hasattr(status, "id"):
        return str(status.id)
    if isinstance(status, dict):
        return str(status.get("id"))
    return str(status)


def _issue_has_link(client, from_key, to_key, type_ids):
    issue = client.issues[from_key]
    for link in client.issues.links(issue):
        value = link._value if hasattr(link, "_value") else {}
        link_type = value.get("type")
        type_id = link_type.id if hasattr(link_type, "id") else link_type
        if type_id not in type_ids:
            continue
        if _issue_ref_key(value.get("object")) == to_key:
            return True
    return False


def _ensure_issue_link(client, from_key, to_key, relationship):
    type_ids = LINK_TYPE_DEPENDS if relationship == "depends on" else LINK_TYPE_SUBTASK
    if _issue_has_link(client, from_key, to_key, type_ids):
        return False
    try:
        client.issues.links(client.issues[from_key]).create(
            issue=to_key, relationship=relationship
        )
        return True
    except Exception as ex:
        if "422" in str(ex) or "уже связаны" in str(ex):
            return False
        raise


def _transition_execute_kwargs(transition_id):
    return dict(TRANSITION_EXECUTE_KWARGS.get(transition_id) or {})


def _execute_transition(client, issue, transition, transition_id=None):
    transition_id = transition_id or transition.id
    kwargs = _transition_execute_kwargs(transition_id)
    client.issues.transitions(issue).execute(transition, **kwargs)


def _apply_issue_status(client, issue_key, transition_id):
    if not transition_id:
        return False
    issue = client.issues[issue_key]
    target_status = TARGET_STATUS_BY_TRANSITION.get(transition_id)
    current = _issue_status_id(issue)
    if target_status and current == target_status:
        return False

    transitions = list(client.issues.transitions(issue))
    by_id = {t.id: t for t in transitions}
    if transition_id in by_id:
        try:
            _execute_transition(client, issue, by_id[transition_id], transition_id)
            return True
        except Exception as ex:
            if "422" in str(ex) or "404" in str(ex):
                return False
            raise

    if target_status:
        for transition in transitions:
            to_ref = transition.to
            to_id = to_ref.id if hasattr(to_ref, "id") else to_ref
            if str(to_id) != str(target_status):
                continue
            try:
                _execute_transition(client, issue, transition, transition.id)
                return True
            except Exception as ex:
                if "422" in str(ex) or "404" in str(ex):
                    return False
                raise
    return False


def snippet_wire_task_links(client, plan, summary_to_key):
    specs = _dependency_link_specs(plan)
    print("\n=== 4) Task links (depends on + parent field subtasks) ===")
    print("dependency specs:", len(specs))

    if not _run_enabled():
        for from_summary, to_summary, rel in specs:
            print(
                "  %s -[%s]-> %s"
                % (
                    summary_to_key.get(from_summary, from_summary),
                    rel,
                    summary_to_key.get(to_summary, to_summary),
                )
            )
        return []

    results = []
    for from_summary, to_summary, relationship in specs:
        from_key = summary_to_key.get(from_summary)
        to_key = summary_to_key.get(to_summary)
        if not from_key or not to_key:
            continue
        created = _ensure_issue_link(client, from_key, to_key, relationship)
        mark = "linked" if created else "exists"
        print("  %s %s %s (%s)" % (from_key, relationship, to_key, mark))
        results.append(
            {
                "from": from_key,
                "to": to_key,
                "relationship": relationship,
                "created": created,
            }
        )
    return results


def snippet_apply_task_statuses(client, plan, summary_to_key):
    print("\n=== 5) Task statuses (workflow transitions) ===")

    if not _run_enabled():
        for slot_index, row in enumerate(plan):
            summary, _, role, ci, gi = row
            transition_id = _status_transition_for_row(slot_index, role, ci, gi)
            key = summary_to_key.get(summary, summary)
            target = TARGET_STATUS_BY_TRANSITION.get(transition_id or "", "?")
            print("  %s [%s] transition=%s -> status %s" % (key, role, transition_id, target))
        return []

    results = []
    for slot_index, row in enumerate(plan):
        summary, _, role, ci, gi = row
        issue_key = summary_to_key.get(summary)
        if not issue_key:
            continue
        transition_id = _status_transition_for_row(slot_index, role, ci, gi)
        changed = _apply_issue_status(client, issue_key, transition_id)
        issue = client.issues[issue_key]
        note = "updated" if changed else "ok"
        if not changed and transition_id and _issue_status_id(issue) != TARGET_STATUS_BY_TRANSITION.get(
            transition_id
        ):
            note = "skipped"
        print(
            "  %s [%s] %s -> status %s (%s)"
            % (
                issue_key,
                role,
                transition_id or "—",
                _issue_status_id(issue),
                note,
            )
        )
        results.append(
            {
                "key": issue_key,
                "role": role,
                "transition": transition_id,
                "status": _issue_status_id(issue),
                "changed": changed,
            }
        )
    return results


def _is_version_conflict(ex):
    if isinstance(ex, tracker_exc.Conflict):
        return True
    text = str(ex)
    return "409" in text or "не удалось сохранить изменения" in text


def _issue_project_primary_id(issue):
    project = getattr(issue, "project", None)
    if project is None:
        return None
    primary = getattr(project, "primary", None)
    if primary is None:
        return None
    if hasattr(primary, "id"):
        return str(primary.id)
    if isinstance(primary, dict):
        return str(primary.get("id"))
    return str(primary)


def _gantt_fields_differ(issue, start_s, deadline_s, project_short_id):
    if str(getattr(issue, "start", None) or "") != start_s:
        return True
    if str(getattr(issue, "deadline", None) or "") != deadline_s:
        return True
    if str(getattr(issue, "end", None) or "") != deadline_s:
        return True
    if project_short_id and _issue_project_primary_id(issue) != str(project_short_id):
        return True
    return False


def _ensure_issue_gantt_and_project(
    client, issue, project_short_id, slot_index, dry_fields=False
):
    start_s, deadline_s = _gantt_dates(slot_index)
    project_spec = {"primary": int(project_short_id)}
    fields = {
        "start": start_s,
        "deadline": deadline_s,
        "end": deadline_s,
        "project": project_spec,
    }
    if dry_fields:
        return fields

    issue = client.issues[issue.key]
    if not _gantt_fields_differ(issue, start_s, deadline_s, project_short_id):
        return fields

    chunks = []
    if (
        str(getattr(issue, "start", None) or "") != start_s
        or str(getattr(issue, "deadline", None) or "") != deadline_s
        or str(getattr(issue, "end", None) or "") != deadline_s
    ):
        chunks.append({"start": start_s, "deadline": deadline_s, "end": deadline_s})
    if _issue_project_primary_id(issue) != str(project_short_id):
        chunks.append({"project": project_spec})

    max_attempts = 6
    for chunk in chunks:
        for attempt in range(max_attempts):
            try:
                issue.update(**chunk)
                break
            except Exception as ex:
                if not _is_version_conflict(ex) or attempt >= max_attempts - 1:
                    raise
                time.sleep(0.4 * (attempt + 1))
                issue = client.issues[issue.key]
        issue = client.issues[issue.key]

    return fields


def _find_or_create_issue(
    client,
    queue_key,
    summary,
    parent_key,
    type_spec,
    project_short_id,
    slot_index,
):
    start_s, deadline_s = _gantt_dates(slot_index)
    project_spec = {"primary": int(project_short_id)} if project_short_id else None

    found = find_issue(client, queue_key, summary)
    if found:
        print(
            "  reuse:",
            found.key,
            "|",
            summary,
            "|",
            start_s,
            "→",
            deadline_s,
        )
        if project_short_id and _run_enabled():
            _ensure_issue_gantt_and_project(
                client, found, project_short_id, slot_index
            )
        return found, False

    kwargs = {
        "queue": queue_key,
        "summary": summary,
        "type": type_spec,
        "description": "Created by create_test_structure.py",
        "start": start_s,
        "deadline": deadline_s,
        "end": deadline_s,
    }
    if project_spec:
        kwargs["project"] = project_spec
    if parent_key:
        kwargs["parent"] = parent_key

    issue = client.issues.create(**kwargs)
    print("  created:", issue.key, "|", summary, "|", start_s, "→", deadline_s)
    return issue, True


def snippet_create_task_tree(client, queue_key, project_short_id, issue_type_name=None):
    issue_type_name = issue_type_name or os.environ.get("ISSUE_TYPE_NAME", "Задача")
    type_spec = {"name": issue_type_name}
    plan = _task_tree_plan()

    print("\n=== 3) Tasks (parent + children + grandchildren) ===")
    print("queue:", queue_key, "type:", type_spec)
    print("project shortId (issues):", project_short_id)
    print("task count:", len(plan))

    if not _run_enabled():
        print("(dry-run)")
        summary_stub = {}
        for i, row in enumerate(plan):
            summary, parent_summary, role, ci, gi = row
            summary_stub[summary] = summary
            start_s, deadline_s = _gantt_dates(i)
            print(
                "  [%s] %s parent=%s %s→%s"
                % (role, summary, parent_summary or "-", start_s, deadline_s)
            )
        snippet_wire_task_links(client, plan, summary_stub)
        snippet_apply_task_statuses(client, plan, summary_stub)
        return []

    if not project_short_id:
        raise ValueError(
            "project shortId is required to link tasks (entity shortId = classic project id)"
        )

    summary_to_key = {}
    created = []
    for slot_index, row in enumerate(plan):
        summary, parent_summary, role, ci, gi = row
        parent_key = summary_to_key.get(parent_summary) if parent_summary else None
        issue, was_created = _find_or_create_issue(
            client,
            queue_key,
            summary,
            parent_key,
            type_spec,
            project_short_id,
            slot_index,
        )
        summary_to_key[summary] = issue.key
        created.append(
            {
                "key": issue.key,
                "role": role,
                "parent": parent_key,
                "created": was_created,
                "start": _gantt_dates(slot_index)[0],
                "deadline": _gantt_dates(slot_index)[1],
            }
        )

    snippet_wire_task_links(client, plan, summary_to_key)
    statuses = snippet_apply_task_statuses(client, plan, summary_to_key)
    for item in created:
        for st in statuses:
            if st.get("key") == item.get("key"):
                item["status"] = st.get("status")
                item["transition"] = st.get("transition")
                break

    return created


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    client = make_client()
    portfolio_ref = os.environ.get("PARENT_PORTFOLIO_ID", DEFAULT_PORTFOLIO_SHORT_ID)
    project_name = os.environ.get("PROJECT_NAME", DEFAULT_PROJECT_NAME)
    queue_key = os.environ.get("QUEUE_KEY", DEFAULT_QUEUE_KEY)
    queue_name = os.environ.get("QUEUE_NAME", DEFAULT_QUEUE_NAME)

    if os.environ.get("PROJECT_NAME_STAMP", "").lower() in ("1", "true", "yes"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        project_name = "%s %s" % (project_name, stamp)

    print("Tracker create test structure (find-or-create)")
    print("portfolio ref:", portfolio_ref)
    print("project name:", project_name)
    print("queue key:", queue_key, "queue name:", queue_name)
    print("TRACKER_CREATE_RUN:", _run_enabled())

    project = snippet_create_nested_project(client, project_name, portfolio_ref)
    project_id = project.get("id")
    project_short = project.get("shortId")

    queue = snippet_create_queue(
        client, project_name, queue_key=queue_key, queue_name=queue_name
    )
    queue_key = queue.get("key") or queue_key

    snippet_link_queue_to_project(client, project_short, queue_key)

    tasks = snippet_create_task_tree(client, queue_key, project_short)

    print("\n=== Summary ===")
    print("portfolio:", portfolio_ref)
    print(
        "project:",
        project_name,
        "id:",
        project_id,
        "shortId:",
        project_short,
        "(reused)" if project.get("existing") else "(new)",
    )
    print(
        "queue:",
        queue_key,
        queue_name,
        "(reused)" if queue.get("existing") else "(new)",
    )
    print("tasks (%d):" % len(tasks), [t.get("key") for t in tasks])
    return 0


if __name__ == "__main__":
    sys.exit(main())
