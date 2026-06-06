# coding: utf-8
"""Sync selected Cerebro tasks to Yandex Tracker (main-thread incremental runner)."""
import re
from datetime import date, datetime, timedelta

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import sync_settings
from . import sync_log
from .cerebro_task_meta import enrich_node
from .status_map import DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY, cerebro_status_to_tracker_key
from .tracker_client import make_client_from_settings
from .sync_settings import task_map_issue_key, tracker_issue_url


def queue_key_from_project_name(project_name):
    letters = re.sub(r"[^A-Za-z]", "", project_name or "")
    if not letters:
        letters = "CBRO"
    return letters.upper()[:15]


def _headers(client):
    return dict(client._connection.session.headers)


def _resolve_portfolio_id(client, portfolio_ref):
    ref = str(portfolio_ref).strip()
    if not ref:
        raise ValueError("parent_portfolio_id is not set")
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


def _parent_entity_id(fields):
    pe = (fields or {}).get("parentEntity") or {}
    primary = pe.get("primary") or {}
    return primary.get("id")


def find_entity_project(client, project_name, portfolio_id):
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
                "existing": True,
            }
    return None


def create_entity_project(client, project_name, portfolio_id):
    portfolio_id = _resolve_portfolio_id(client, portfolio_id)
    url = client._connection.build_url("/v3/entities/project")
    payload = {
        "fields": {
            "summary": project_name,
            "entityStatus": "draft",
            "parentEntity": {"primary": portfolio_id},
        }
    }
    resp = client._connection.session.post(
        url, json=payload, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code >= 400:
        raise RuntimeError("Create project failed: %s %s" % (resp.status_code, resp.text))
    return resp.json()


def find_queue(client, queue_key):
    """Return queue dict if usable; None if missing, deleted, or no access."""
    url = client._connection.build_url("/v3/queues/%s" % queue_key)
    resp = client._connection.session.get(
        url, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("deleted"):
            return None
        data["existing"] = True
        return data
    if resp.status_code in (403, 404):
        return None
    raise RuntimeError("Queue lookup failed: %s %s" % (resp.status_code, resp.text))


def _queue_key_candidates(project_name, saved_key=None):
    seen = set()
    if saved_key:
        seen.add(saved_key)
        yield saved_key
    base = queue_key_from_project_name(project_name)
    if base not in seen:
        seen.add(base)
        yield base
    for suffix in ("CB", "CBR", "SYN", "S2", "Q2", "Q3"):
        alt = (base[: 15 - len(suffix)] + suffix)[:15]
        if alt not in seen:
            seen.add(alt)
            yield alt
    for i in range(1, 6):
        alt = ("%s%d" % (base[: max(1, 14 - len(str(i)))], i))[:15]
        if alt not in seen:
            seen.add(alt)
            yield alt


def _unique_queue_key_candidates(project_name, saved_key=None):
    return list(dict.fromkeys(_queue_key_candidates(project_name, saved_key)))


def ensure_queue_for_project(client, project_name, cerebro_root_id, settings):
    """Find or create a non-deleted queue the user can write to."""
    root_key = str(cerebro_root_id)
    queue_keys = settings.setdefault("queue_keys", {})
    saved = queue_keys.get(root_key)

    if saved:
        queue = find_queue(client, saved)
        if queue:
            return saved, queue
        queue_keys.pop(root_key, None)

    candidates = _unique_queue_key_candidates(project_name)
    for qkey in candidates:
        queue = find_queue(client, qkey)
        if queue:
            return qkey, queue

    qname = "%s Queue" % project_name
    last_error = None
    for qkey in candidates:
        try:
            queue = create_queue(client, qkey, qname, project_name)
            return qkey, queue
        except RuntimeError as ex:
            last_error = ex
            continue

    detail = str(last_error) if last_error else "no candidate keys left"
    raise RuntimeError(
        "Could not find or create a Tracker queue for project %r. %s. "
        "Create a queue manually in Tracker or ask the queue owner for access."
        % (project_name, detail)
    )


def _lead_login(client):
    me = client.myself
    if hasattr(me, "_value"):
        return me._value.get("login") or me._value.get("id")
    return getattr(me, "login", None) or getattr(me, "id", None)


def create_queue(client, queue_key, queue_name, project_name):
    url = client._connection.build_url("/v3/queues/")
    payload = {
        "key": queue_key,
        "name": queue_name,
        "description": "Synced from Cerebro project: %s" % project_name,
        "lead": _lead_login(client),
        "defaultType": "task",
        "defaultPriority": "normal",
        "issueTypesConfig": [
            {
                "issueType": "task",
                "workflow": "developmentPresetWorkflow",
                "resolutions": ["fixed", "wontFix", "duplicate", "later"],
            }
        ],
    }
    resp = client._connection.session.post(
        url, json=payload, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.status_code == 409:
        again = find_queue(client, queue_key)
        if again:
            return again
    if resp.status_code >= 400:
        raise RuntimeError("Create queue failed: %s %s" % (resp.status_code, resp.text))
    return resp.json()


CEREBRO_ID_MARKER = "cerebro_task_id:"
CEREBRO_PATH_MARKER = "cerebro_path:"
PATH_COMMENT_MARKER = "[cerebro-sync]"
LINK_TYPE_DEPENDS = ("depends",)


def _format_date(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    s = str(value)
    return s[:10] if s else None


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except ValueError:
        return None


def _issue_description(cerebro_id, cerebro_path, tracker_url=None):
    lines = [
        "Synced from Cerebro.",
        "%s%s" % (CEREBRO_ID_MARKER, cerebro_id),
        "%s%s" % (CEREBRO_PATH_MARKER, cerebro_path or ""),
    ]
    if tracker_url:
        lines.append("Tracker: %s" % tracker_url)
    return "\n".join(lines)


def _issue_status_key(issue):
    status = getattr(issue, "status", None)
    if status is None and hasattr(issue, "_value"):
        status = (issue._value or {}).get("status")
    if status is None:
        return None
    if hasattr(status, "key"):
        return status.key
    if isinstance(status, dict):
        return status.get("key") or status.get("id")
    return str(status)


def _progress_percent(progress_value):
    if progress_value is None:
        return None
    try:
        return max(0, min(100, int(round(float(progress_value)))))
    except (TypeError, ValueError):
        return None


def _patch_issue(client, issue_key, payload):
    url = client._connection.build_url("/v3/issues/%s" % issue_key)
    resp = client._connection.session.patch(
        url,
        json=payload,
        headers=_headers(client),
        timeout=client._connection.timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            "PATCH %s failed: %s %s" % (issue_key, resp.status_code, resp.text[:400])
        )
    if resp.content:
        return resp.json()
    return {}


def _sync_log(message):
    sync_log.log(message)


def _get_issue_snapshot(client, issue_key):
    url = client._connection.build_url("/v3/issues/%s" % issue_key)
    resp = client._connection.session.get(
        url, headers=_headers(client), timeout=client._connection.timeout
    )
    if resp.ok:
        return resp.json()
    return {"_error": "%s %s" % (resp.status_code, resp.text[:200])}


def _issue_accessible(client, issue_key):
    """True if GET issue succeeds (not 403/404)."""
    snap = _get_issue_snapshot(client, issue_key)
    err = str(snap.get("_error") or "")
    return "_error" not in snap and not err.startswith("403") and not err.startswith("404")


def _snapshot_queue_key(snap):
    q = snap.get("queue")
    if isinstance(q, dict):
        return q.get("key")
    return q


def _issue_in_queue(client, issue_key, queue_key):
    if not queue_key:
        return True
    snap = _get_issue_snapshot(client, issue_key)
    if snap.get("_error"):
        return False
    actual = _snapshot_queue_key(snap)
    return not actual or actual == queue_key


def _invalidate_stale_issue_mapping(task_map, cerebro_id, issue_key, reason):
    _sync_log(
        "%s: stale mapping for Cerebro %s (%s) — will sync in current project queue"
        % (issue_key, cerebro_id, reason)
    )
    task_map.pop(cerebro_id, None)


def _transition_to_key(transition):
    to_ref = getattr(transition, "to", None)
    if to_ref is None:
        return None
    if hasattr(to_ref, "key"):
        return to_ref.key
    if isinstance(to_ref, dict):
        return to_ref.get("key")
    return None


def _apply_status_by_transition(client, issue_key, target_status_key, extra_fields=None):
    """Move issue to target status via workflow transition (status is read-only on PATCH)."""
    issue = client.issues[issue_key]
    if _issue_status_key(issue) == target_status_key:
        return True
    extra_fields = dict(extra_fields or {})
    extra_fields.pop("status", None)

    try:
        transitions = list(client.issues.transitions(issue))
    except Exception:
        return False

    for transition in transitions:
        if _transition_to_key(transition) != target_status_key:
            continue
        try:
            client.issues.transitions(issue).execute(transition, **extra_fields)
            if _issue_status_key(client.issues[issue_key]) == target_status_key:
                return True
        except Exception:
            pass
    return False


def _apply_task_progress(client, issue_key, pct):
    """Write global field taskProgress (never mix with status in one PATCH)."""
    if pct is None:
        return True
    issue = client.issues[issue_key]
    try:
        issue.update(taskProgress=pct)
        return True
    except Exception as ex1:
        try:
            _patch_issue(client, issue_key, {"taskProgress": pct})
            return True
        except Exception as ex2:
            _sync_log(
                "%s: taskProgress=%s failed: %s"
                % (issue_key, pct, ex2 or ex1)
            )
            return False


def _apply_cerebro_tracker_fields(
    client, issue_key, status_info, progress_value, status_map=None
):
    """Set taskProgress via update; status only via workflow transitions (read-only field)."""
    status_map = status_map or DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY
    status_key = cerebro_status_to_tracker_key(status_info, status_map)
    pct = _progress_percent(progress_value)
    issue = client.issues[issue_key]
    current_status = _issue_status_key(issue)
    need_status = bool(status_key and current_status != status_key)
    need_progress = pct is not None

    if status_info and not status_key:
        raw_name = (status_info.get("name") or "").strip()
        if not raw_name and status_info.get("id") is not None:
            raw_name = "id=%s" % status_info.get("id")
        if raw_name:
            _sync_log(
                "%s: Cerebro status %r has no Tracker mapping — edit %s"
                % (issue_key, raw_name, sync_settings.get_status_map_path())
            )

    if not need_status and not need_progress:
        if not (status_info and not status_key):
            _sync_log("%s: nothing to update (status and progress unchanged)" % issue_key)
        return False

    progress_ok = True
    if need_progress:
        _sync_log("%s: setting taskProgress=%s" % (issue_key, pct))
        progress_ok = _apply_task_progress(client, issue_key, pct)

    status_ok = True
    if need_status:
        _sync_log(
            "%s: status %s → %s (workflow transition, not PATCH)"
            % (issue_key, current_status, status_key)
        )
        status_ok = _apply_status_by_transition(client, issue_key, status_key)

    snap = _get_issue_snapshot(client, issue_key)
    snap_status = None
    if isinstance(snap.get("status"), dict):
        snap_status = snap["status"].get("key") or snap["status"].get("id")
    elif snap.get("status"):
        snap_status = snap.get("status")
    snap_progress = snap.get("taskProgress")

    if progress_ok and (not need_status or status_ok):
        _sync_log(
            "%s: ok — status=%s, taskProgress=%s"
            % (issue_key, snap_status, snap_progress)
        )
    else:
        if need_progress and not progress_ok:
            _sync_log("%s: taskProgress update failed" % issue_key)
        if need_status and not status_ok:
            _sync_log(
                "%s: status transition to %s failed (still %s)"
                % (issue_key, status_key, snap_status)
            )

    return progress_ok and (not need_status or status_ok)


def _apply_tracker_status(client, issue_key, status_info, status_map=None):
    return _apply_cerebro_tracker_fields(
        client, issue_key, status_info, None, status_map=status_map
    )


def _apply_tracker_progress(client, issue_key, progress_value, status_map=None):
    return _apply_cerebro_tracker_fields(
        client, issue_key, None, progress_value, status_map=status_map
    )


def _issue_ref_key(obj_ref):
    if obj_ref is None:
        return None
    if hasattr(obj_ref, "key"):
        return obj_ref.key
    if isinstance(obj_ref, dict):
        return obj_ref.get("key")
    return str(obj_ref)


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


def _ensure_issue_link(client, from_key, to_key, relationship="depends on"):
    type_ids = LINK_TYPE_DEPENDS
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


def _cerebro_dependency_pairs(cerebro_ids):
    """Return (src_id, dst_id) pairs from Cerebro task_links for synced tasks."""
    try:
        from twin_plugin.pycerebro import database as cerebro_database
        from twin_plugin.pycerebro import dbtypes
    except ImportError:
        from pycerebro import database as cerebro_database
        from pycerebro import dbtypes

    db = cerebro_database.Database()
    if db.connect_from_cerebro_client() != db.CLIENT_CONNECTED:
        return []

    ids = {int(x) for x in cerebro_ids}
    seen = set()
    pairs = []
    for tid in ids:
        try:
            conns = db.task_links(tid)
        except Exception:
            continue
        for conn in conns or []:
            if conn[dbtypes.TASK_LINK_DEL]:
                continue
            src = int(conn[dbtypes.TASK_LINK_SRC])
            dst = int(conn[dbtypes.TASK_LINK_DST])
            if src not in ids or dst not in ids or src == dst:
                continue
            key = (src, dst)
            if key in seen:
                continue
            seen.add(key)
            pairs.append(key)
    return pairs


def _resolve_issue_key(cerebro_id, issue_keys, task_map):
    key = issue_keys.get(cerebro_id)
    if key:
        return key
    return task_map_issue_key(task_map.get(str(cerebro_id)))


def wire_sync_dependencies(client, jobs, nodes_by_id, root_ids, issue_keys, task_map):
    """
    Create Tracker ``depends on`` links:
    - mirror parent-child hierarchy (child depends on parent)
    - Cerebro task_links between synced tasks (src depends on dst)
    """
    cerebro_ids = set()
    for job in jobs:
        if job.get("kind") == "issue":
            cerebro_ids.add(job["node"]["id"])

    created = 0
    skipped = 0

    def link_pair(from_id, to_id):
        nonlocal created, skipped
        from_key = _resolve_issue_key(from_id, issue_keys, task_map)
        to_key = _resolve_issue_key(to_id, issue_keys, task_map)
        if not from_key or not to_key or from_key == to_key:
            skipped += 1
            return
        if _ensure_issue_link(client, from_key, to_key, "depends on"):
            created += 1
        else:
            skipped += 1

    for job in jobs:
        if job.get("kind") != "issue":
            continue
        cid = job["node"]["id"]
        pid = job.get("cerebro_parent_id")
        if pid is not None and pid in cerebro_ids:
            link_pair(cid, pid)

    for src_id, dst_id in _cerebro_dependency_pairs(cerebro_ids):
        link_pair(src_id, dst_id)

    return {"dependencies_created": created, "dependencies_skipped": skipped}


def _ensure_path_comment(client, issue_key, cerebro_path):
    """Add Cerebro path as a Tracker comment (once)."""
    if not cerebro_path:
        return
    text = "%s Cerebro path: %s" % (PATH_COMMENT_MARKER, cerebro_path)
    try:
        comments = client.issues[issue_key].comments
        get_all = getattr(comments, "get_all", None)
        if get_all:
            for comment in get_all():
                body = getattr(comment, "text", None) or getattr(comment, "longText", None)
                if body and PATH_COMMENT_MARKER in str(body):
                    return
        comments.create(text=text)
    except Exception:
        pass


def find_issue_by_cerebro_id(client, queue_key, cerebro_id):
    """Match issues created by this plugin (avoid summary-only collisions)."""
    marker = "%s%s" % (CEREBRO_ID_MARKER, cerebro_id)
    try:
        batch = list(
            client.issues.find(
                filter={"queue": queue_key, "description": marker},
                per_page=5,
            )
        )
    except Exception:
        return None
    for issue in batch:
        desc = getattr(issue, "description", None)
        if desc is None and hasattr(issue, "_value"):
            desc = (issue._value or {}).get("description")
        if desc and marker in str(desc):
            return issue
    return None


def _gantt_dates_for_node(node, cerebro_parent_id, nodes_by_id, sibling_index=0):
    """
    Use Cerebro dates when set; otherwise stagger children after parent for Gantt layout.
    Children are offset slightly forward from the parent start.
    """
    start = _parse_date(node.get("start"))
    finish = _parse_date(node.get("finish"))
    duration_days = 7
    if start and finish and finish >= start:
        duration_days = max(1, (finish - start).days)
    elif start and not finish:
        finish = start + timedelta(days=duration_days)
    elif finish and not start:
        start = finish - timedelta(days=duration_days)

    if cerebro_parent_id and cerebro_parent_id in nodes_by_id:
        parent = nodes_by_id[cerebro_parent_id]
        p_start = _parse_date(parent.get("start"))
        p_finish = _parse_date(parent.get("finish"))
        if p_start:
            offset_days = 1 + sibling_index
            if not start or start <= p_start:
                start = p_start + timedelta(days=offset_days)
            if not finish or finish <= start:
                finish = start + timedelta(days=duration_days)
        elif p_finish and not start:
            start = p_finish + timedelta(days=1 + sibling_index)
            finish = start + timedelta(days=duration_days)

    if not start:
        start = date.today() + timedelta(days=1 + sibling_index)
    if not finish or finish < start:
        finish = start + timedelta(days=duration_days)

    return start.isoformat(), finish.isoformat()


def create_or_update_issue(
    client,
    queue_key,
    node,
    parent_key,
    project_short_id,
    task_map,
    nodes_by_id,
    cerebro_parent_id,
    sibling_index=0,
    rollup_index=None,
    status_map=None,
):
    node = enrich_node(node, rollup_index=rollup_index, nodes_by_id=nodes_by_id)
    st = node.get("status") or {}
    rollup = node.get("rollup")
    if rollup:
        _sync_log(
            "Computed %s: %d leaves → progress=%s%%, status=%s"
            % (
                node.get("name") or node.get("id"),
                rollup.get("leaf_count", 0),
                node.get("progress"),
                st.get("name") or "?",
            )
        )
    else:
        _sync_log(
            "Cerebro task %s: status=%s (id=%s), progress=%s"
            % (
                node.get("id"),
                st.get("name") or "?",
                st.get("id"),
                node.get("progress"),
            )
        )
    cerebro_id = str(node["id"])
    summary = node["name"] or ("Cerebro %s" % cerebro_id)
    cerebro_path = node.get("path") or summary
    start_s, finish_s = _gantt_dates_for_node(
        node, cerebro_parent_id, nodes_by_id, sibling_index
    )
    project_spec = {"primary": int(project_short_id)} if project_short_id else None
    type_spec = {"name": "Задача"}

    existing_key = task_map_issue_key(task_map.get(cerebro_id))
    issue = None
    if existing_key:
        if not _issue_accessible(client, existing_key):
            _invalidate_stale_issue_mapping(
                task_map, cerebro_id, existing_key, "no access"
            )
            existing_key = None
        elif not _issue_in_queue(client, existing_key, queue_key):
            _invalidate_stale_issue_mapping(
                task_map,
                cerebro_id,
                existing_key,
                "queue was %s, need %s"
                % (_snapshot_queue_key(_get_issue_snapshot(client, existing_key)), queue_key),
            )
            existing_key = None
        else:
            try:
                issue = client.issues[existing_key]
            except Exception:
                issue = None
    if issue is None:
        found = find_issue_by_cerebro_id(client, queue_key, cerebro_id)
        if found:
            issue = found
            existing_key = issue.key

    if issue is not None:
        issue_key = issue.key
        tracker_url = tracker_issue_url(issue_key)
        updates = {
            "description": _issue_description(cerebro_id, cerebro_path, tracker_url),
            "start": start_s,
            "deadline": finish_s,
            "end": finish_s,
        }
        if project_spec:
            updates["project"] = project_spec
        if parent_key:
            updates["parent"] = parent_key
        try:
            issue.update(**updates)
        except Exception as ex:
            err = str(ex)
            if "403" not in err and "Нет доступа" not in err:
                raise
            _sync_log(
                "%s: update forbidden for Cerebro %s — remapping in queue %s"
                % (issue_key, cerebro_id, queue_key)
            )
            task_map.pop(cerebro_id, None)
            return create_or_update_issue(
                client,
                queue_key,
                node,
                parent_key,
                project_short_id,
                task_map,
                nodes_by_id,
                cerebro_parent_id,
                sibling_index,
                rollup_index,
                status_map=status_map,
            )
        _apply_cerebro_tracker_fields(
            client,
            issue_key,
            node.get("status"),
            node.get("progress"),
            status_map=status_map,
        )
        task_map[cerebro_id] = {"key": issue_key, "url": tracker_url}
        return issue_key, False, tracker_url

    tracker_url_placeholder = None
    description = _issue_description(cerebro_id, cerebro_path, tracker_url_placeholder)
    kwargs = {
        "queue": queue_key,
        "summary": summary,
        "type": type_spec,
        "description": description,
        "start": start_s,
        "deadline": finish_s,
        "end": finish_s,
    }
    if project_spec:
        kwargs["project"] = project_spec
    if parent_key:
        kwargs["parent"] = parent_key

    issue = client.issues.create(**kwargs)
    issue_key = issue.key
    tracker_url = tracker_issue_url(issue_key)
    issue.update(description=_issue_description(cerebro_id, cerebro_path, tracker_url))
    _apply_cerebro_tracker_fields(
        client,
        issue_key,
        node.get("status"),
        node.get("progress"),
        status_map=status_map,
    )
    _ensure_path_comment(client, issue_key, cerebro_path)
    task_map[cerebro_id] = {"key": issue_key, "url": tracker_url}
    return issue_key, True, tracker_url


def collect_sync_jobs(checked_nodes, nodes_by_id, root_ids=None):
    """
    checked_nodes: explicitly checked branch nodes visible in the Cerebro tree only.
    Hidden leaf tasks (cut from UI) are NOT synced.

    Each topmost checked node (no checked parent) becomes a Tracker *project*.
    Other checked nodes under it become issues in that project's queue.
    """
    checked_ids = {n["id"] for n in checked_nodes}
    project_root_ids = _project_roots(checked_nodes, nodes_by_id)
    jobs = []
    seen_issue_ids = set()
    siblings_under_parent = {}

    def add_issue(node, project_id, cerebro_parent_id):
        nid = node["id"]
        if nid in seen_issue_ids:
            return
        seen_issue_ids.add(nid)
        sib_key = (project_id, cerebro_parent_id)
        sibling_index = siblings_under_parent.get(sib_key, 0)
        siblings_under_parent[sib_key] = sibling_index + 1
        jobs.append(
            {
                "kind": "issue",
                "node": node,
                "root_id": project_id,
                "cerebro_parent_id": cerebro_parent_id,
                "sibling_index": sibling_index,
            }
        )

    for node in checked_nodes:
        nid = node["id"]
        if nid in project_root_ids:
            continue
        project_id = _find_project_root(nid, nodes_by_id, project_root_ids)
        add_issue(
            node,
            project_id,
            _cerebro_parent_id(nid, nodes_by_id, project_root_ids, checked_ids),
        )

    project_jobs = []
    for rid in sorted(project_root_ids):
        root_node = nodes_by_id.get(rid)
        if root_node:
            project_jobs.append({"kind": "project", "node": root_node, "root_id": rid})

    issue_jobs = [j for j in jobs if j["kind"] == "issue"]
    issue_jobs.sort(
        key=lambda j: (
            _tree_depth(j["node"]["id"], nodes_by_id, project_root_ids),
            j.get("cerebro_parent_id") or 0,
            j.get("sibling_index", 0),
            j["node"]["id"],
        )
    )
    return project_jobs + issue_jobs


def _project_roots(checked_nodes, nodes_by_id):
    """Topmost checked nodes — each maps to one Tracker project."""
    checked_ids = {n["id"] for n in checked_nodes}
    roots = set()
    for node in checked_nodes:
        nid = node["id"]
        pid = node.get("cerebro_parent_id")
        if pid is None or pid not in checked_ids:
            roots.add(nid)
    return roots


def _find_project_root(task_id, nodes_by_id, project_root_ids):
    if task_id in project_root_ids:
        return task_id
    node = nodes_by_id.get(task_id)
    while node and node.get("cerebro_parent_id") is not None:
        pid = node["cerebro_parent_id"]
        if pid in project_root_ids:
            return pid
        node = nodes_by_id.get(pid)
    return task_id


def _find_root_id(task_id, nodes_by_id, root_ids):
    """Legacy: Cerebro tree root (top-level project). Prefer _find_project_root for sync."""
    if task_id in root_ids:
        return task_id
    node = nodes_by_id.get(task_id)
    while node and node.get("cerebro_parent_id") is not None:
        pid = node["cerebro_parent_id"]
        if pid in root_ids:
            return pid
        node = nodes_by_id.get(pid)
    return task_id


def _cerebro_parent_id(task_id, nodes_by_id, project_root_ids, checked_ids=None):
    """Nearest checked ancestor for Tracker parent link (not the project root)."""
    node = nodes_by_id.get(task_id)
    if not node:
        return None
    pid = node.get("cerebro_parent_id")
    while pid is not None:
        if pid in project_root_ids:
            return None
        if checked_ids is None or pid in checked_ids:
            return pid
        node = nodes_by_id.get(pid)
        if not node:
            break
        pid = node.get("cerebro_parent_id")
    return None


def _tree_depth(task_id, nodes_by_id, project_root_ids):
    depth = 0
    node = nodes_by_id.get(task_id)
    project_root = _find_project_root(task_id, nodes_by_id, project_root_ids)
    while node and node.get("id") != project_root:
        depth += 1
        pid = node.get("cerebro_parent_id")
        if pid is None:
            break
        node = nodes_by_id.get(pid)
    return depth


class SyncRunner(QObject):
    """Execute sync jobs one per timer tick on the main thread."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, settings, jobs, nodes_by_id, root_ids, parent=None):
        super().__init__(parent)
        self._settings = dict(settings)
        self._jobs = list(jobs)
        self._nodes_by_id = nodes_by_id
        self._root_ids = set(root_ids)
        self._index = 0
        self._client = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._project_ctx = {}
        self._issue_keys = {}
        self._issue_links = {}
        self._stats = {
            "projects": 0,
            "issues_created": 0,
            "issues_updated": 0,
            "links_updated": 0,
            "dependencies_created": 0,
            "errors": [],
        }
        self._abort_sync = False
        self._rollup_index = {}
        self._status_map = {}

    def start(self):
        client, err = make_client_from_settings(self._settings)
        if err:
            self.error.emit(err)
            return
        self._client = client
        self._rollup_index = {}
        status_map_path = sync_settings.ensure_status_map_file()
        self._status_map = sync_settings.load_status_map(self._settings)
        _sync_log(
            "Status map: %s (%d entries)"
            % (status_map_path, len(self._status_map))
        )
        _sync_log("Sync started: %d job(s)" % len(self._jobs))
        self._index = 0
        self._timer.start(0)

    def stop(self):
        self._timer.stop()

    def _tick(self):
        if self._abort_sync or self._index >= len(self._jobs):
            task_map = sync_settings.normalize_task_map(
                self._settings.get("task_map") or {}
            )
            task_map.update(self._issue_links)
            self._settings["task_map"] = task_map
            self._stats["links_updated"] = len(self._issue_links)
            if self._client and not self._abort_sync:
                try:
                    dep_stats = wire_sync_dependencies(
                        self._client,
                        self._jobs,
                        self._nodes_by_id,
                        self._root_ids,
                        self._issue_keys,
                        task_map,
                    )
                    self._stats["dependencies_created"] = dep_stats.get(
                        "dependencies_created", 0
                    )
                except Exception as ex:
                    self._stats["errors"].append(
                        "Dependency links: %s" % ex
                    )
            sync_settings.save(self._settings)
            self.finished.emit(self._stats)
            return
        job = self._jobs[self._index]
        self._index += 1
        try:
            self._run_job(job)
        except Exception as ex:
            self._stats["errors"].append(str(ex))
            if job.get("kind") == "project":
                self._abort_sync = True
        self.progress.emit(self._progress_message(job))
        self._timer.start(0)

    def _progress_message(self, job):
        node = job.get("node") or {}
        name = node.get("name") or "?"
        if job["kind"] == "project":
            return "Syncing project: %s" % name
        return "Syncing task: %s" % name

    def _run_job(self, job):
        client = self._client
        node = job["node"]
        root_id = job["root_id"]

        if job["kind"] == "project":
            portfolio_id = self._settings.get("parent_portfolio_id")
            project_name = node["name"]
            existing = find_entity_project(client, project_name, portfolio_id)
            if existing:
                project = existing
            else:
                project = create_entity_project(client, project_name, portfolio_id)
                self._stats["projects"] += 1
            short_id = project.get("shortId")
            qkey, queue = ensure_queue_for_project(
                client, project_name, root_id, self._settings
            )
            if not self._settings.get("queue_keys"):
                self._settings["queue_keys"] = {}
            self._settings["queue_keys"][str(root_id)] = qkey
            self._project_ctx[root_id] = {
                "queue_key": qkey,
                "project_short_id": short_id,
                "project_name": project_name,
            }
            return

        ctx = self._project_ctx.get(root_id)
        if not ctx:
            if self._abort_sync:
                return
            raise RuntimeError(
                "No Tracker project context for Cerebro root %s. "
                "Project/queue setup failed earlier."
                % root_id
            )
        cerebro_parent_id = job.get("cerebro_parent_id")
        parent_key = None
        if cerebro_parent_id is not None:
            parent_key = self._issue_keys.get(cerebro_parent_id)
            if not parent_key:
                parent_key = task_map_issue_key(
                    (self._settings.get("task_map") or {}).get(str(cerebro_parent_id))
                )

        task_map = sync_settings.normalize_task_map(self._settings.get("task_map") or {})
        key, created, url = create_or_update_issue(
            client,
            ctx["queue_key"],
            node,
            parent_key,
            ctx["project_short_id"],
            task_map,
            self._nodes_by_id,
            cerebro_parent_id,
            job.get("sibling_index", 0),
            rollup_index=self._rollup_index,
            status_map=self._status_map,
        )
        self._issue_keys[node["id"]] = key
        self._issue_links[str(node["id"])] = task_map.get(str(node["id"])) or {
            "key": key,
            "url": url,
        }
        self._settings["task_map"] = task_map
        if created:
            self._stats["issues_created"] += 1
        else:
            self._stats["issues_updated"] += 1
