# coding: utf-8
"""Read Cerebro task fields used during Tracker sync."""

_STATUS_ID_TO_NAME = {}
_STATUS_ID_TO_FLAGS = {}


def _status_id_key(sid):
    if sid is None:
        return None
    try:
        return int(sid)
    except (TypeError, ValueError):
        return sid


def _load_status_catalogs():
    global _STATUS_ID_TO_NAME, _STATUS_ID_TO_FLAGS
    if _STATUS_ID_TO_NAME:
        return
    try:
        import cerebro
        from twin_plugin.pycerebro import dbtypes
    except ImportError:
        return
    try:
        for row in cerebro.core.statuses().data():
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            sid = _status_id_key(row[dbtypes.STATUS_DATA_ID])
            if sid is None:
                continue
            name = (row[dbtypes.STATUS_DATA_NAME] or "").strip()
            if name:
                _STATUS_ID_TO_NAME[sid] = name
            if len(row) > dbtypes.STATUS_DATA_FLAGS:
                _STATUS_ID_TO_FLAGS[sid] = row[dbtypes.STATUS_DATA_FLAGS]
    except Exception:
        pass


def _cerebro_status_catalog():
    _load_status_catalogs()
    return _STATUS_ID_TO_NAME


def _cerebro_status_flags_catalog():
    _load_status_catalogs()
    return _STATUS_ID_TO_FLAGS


def _status_name_from_catalog(sid):
    if sid is None:
        return ""
    catalog = _cerebro_status_catalog()
    return (catalog.get(_status_id_key(sid)) or catalog.get(sid) or "").strip()


def _status_tuple_to_dict(st):
    if isinstance(st, (list, tuple)) and len(st) >= 2:
        sid, name = st[0], st[1]
        name = (name or "").strip()
        if not name and sid is not None:
            name = _status_name_from_catalog(sid)
        if sid is not None or name:
            return {"id": sid, "name": name}
    if st is not None:
        return {"name": str(st).strip()}
    return None


def iter_task_status_infos(task):
    """All status tuples on a task (status(), self, cc) — not only the first named one."""
    infos = []
    seen = set()

    def add(raw):
        info = _status_tuple_to_dict(raw)
        if not info:
            return
        sid = info.get("id")
        if sid in (0, "0", None) and not info.get("name"):
            return
        key = ("id", _status_id_key(sid)) if sid is not None else ("name", info.get("name"))
        if key in seen:
            return
        seen.add(key)
        if sid is not None and not info.get("name"):
            info = dict(info)
            info["name"] = _status_name_from_catalog(sid)
        infos.append(info)

    try:
        add(task.status())
    except Exception:
        pass
    try:
        row = task.data()
        if row is not None:
            from twin_plugin.pycerebro import dbtypes

            if len(row) > dbtypes.TASK_DATA_SELF_STATUS:
                add(row[dbtypes.TASK_DATA_SELF_STATUS])
            if len(row) > dbtypes.TASK_DATA_CC_STATUS:
                add(row[dbtypes.TASK_DATA_CC_STATUS])
    except Exception:
        pass
    return infos


def _cerebro_core():
    import cerebro

    return cerebro.core


def cerebro_task_path(task):
    """Full Cerebro path (parent_url + name)."""
    try:
        parent_url = (task.parent_url() or "").strip()
        name = (task.name() or "").strip()
        if parent_url and name:
            if parent_url.endswith("/"):
                return parent_url + name
            if parent_url.endswith(name):
                return parent_url
            return parent_url + "/" + name
        return name or str(task.id())
    except Exception:
        return str(task.id())


def _task_has_own_progress(task):
    try:
        core = _cerebro_core()
        return core.has_flag(task.flags(), task.FLAG_HAS_PROGRESS)
    except Exception:
        return False


def cerebro_task_progress(task, depth=0):
    """Progress 0–100; for branch tasks without own progress, average children."""
    own = None
    try:
        value = task.progress()
        if value is not None and _task_has_own_progress(task):
            own = float(value)
    except Exception:
        pass
    if own is None:
        try:
            row = task.data()
            if row is not None:
                from twin_plugin.pycerebro import dbtypes

                if len(row) > dbtypes.TASK_DATA_PROGRESS:
                    value = row[dbtypes.TASK_DATA_PROGRESS]
                    if value is not None and _task_has_own_progress(task):
                        own = float(value)
        except Exception:
            pass

    if own is not None:
        return own

    if depth >= 6:
        return None
    try:
        core = _cerebro_core()
        if not core.has_flag(task.flags(), task.FLAG_HAS_CHILD):
            return own if own is not None else 0.0
        subtasks = core.task_children(task.id())
        child_values = []
        for sub in subtasks or []:
            child_p = cerebro_task_progress(sub, depth + 1)
            if child_p is not None:
                child_values.append(child_p)
        if child_values:
            return sum(child_values) / len(child_values)
    except Exception:
        pass
    if own is not None:
        return own
    try:
        value = task.progress()
        if value is not None:
            return float(value)
    except Exception:
        pass
    return None


def cerebro_task_status(task):
    """Best {id, name} among status(), self, and cc (prefers a resolved name)."""
    infos = iter_task_status_infos(task)
    if not infos:
        return None
    for info in infos:
        if info.get("name"):
            return info
    return infos[0]


def enrich_node(node, rollup_index=None, nodes_by_id=None):
    """Attach path; progress/status from rollup_index (computed lazily per branch)."""
    task_id = node.get("id")
    if task_id is None:
        return node
    try:
        task = _cerebro_core().task(task_id)
    except Exception:
        return node
    enriched = dict(node)
    enriched["path"] = cerebro_task_path(task)

    rollup = None
    if rollup_index is not None:
        rollup = rollup_index.get(task_id)
        if rollup is None:
            from .cerebro_computed_meta import (
                compute_rollup_for_branch,
                log_rollup_summary,
            )

            rollup = compute_rollup_for_branch(task_id, nodes_by_id)
            rollup_index[task_id] = rollup
            log_rollup_summary(task_id, rollup)

    if rollup:
        enriched["progress"] = rollup.get("progress")
        enriched["status"] = rollup.get("status")
        enriched["rollup"] = {
            "leaf_count": rollup.get("leaf_count"),
            "breakdown": rollup.get("breakdown"),
        }
    else:
        enriched["progress"] = cerebro_task_progress(task)
        enriched["status"] = cerebro_task_status(task)
    return enriched
