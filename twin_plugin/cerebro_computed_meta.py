# coding: utf-8
"""Compute Cerebro progress/status from leaf subtrees (includes UI-hidden leaves)."""

from .cerebro_task_meta import (
    _cerebro_status_catalog,
    _cerebro_status_flags_catalog,
    _status_id_key,
    _task_has_own_progress,
    iter_task_status_infos,
)
from .sync_log import log as sync_activity_log

PROGRESS_READY = 0
PROGRESS_IN_PROGRESS = 50
PROGRESS_COMPLETED = 100

# Normalized Cerebro status name -> effective progress percent for rollup
_STATUS_PROGRESS = {
    # 0% — not started / open
    "open": PROGRESS_READY,
    "opened": PROGRESS_READY,
    "not started": PROGRESS_READY,
    "открыт": PROGRESS_READY,
    "new": PROGRESS_READY,
    "новый": PROGRESS_READY,
    "backlog": PROGRESS_READY,
    "беклог": PROGRESS_READY,
    "ready to start": PROGRESS_READY,
    "selected for dev": PROGRESS_READY,
    "будем делать": PROGRESS_READY,
    # 50% — in progress
    "in progress": PROGRESS_IN_PROGRESS,
    "in_progress": PROGRESS_IN_PROGRESS,
    "in work": PROGRESS_IN_PROGRESS,
    "в работе": PROGRESS_IN_PROGRESS,
    "to correction": PROGRESS_IN_PROGRESS,
    "testing": PROGRESS_IN_PROGRESS,
    "тестируется": PROGRESS_IN_PROGRESS,
    "review": PROGRESS_IN_PROGRESS,
    "in review": PROGRESS_IN_PROGRESS,
    "ревью": PROGRESS_IN_PROGRESS,
    "paused": PROGRESS_IN_PROGRESS,
    "приостановлено": PROGRESS_IN_PROGRESS,
    "pending review": PROGRESS_IN_PROGRESS,
    # 100% — done
    "completed": PROGRESS_COMPLETED,
    "complete": PROGRESS_COMPLETED,
    "done": PROGRESS_COMPLETED,
    "approved": PROGRESS_COMPLETED,
    "утверждён": PROGRESS_COMPLETED,
    "утвержден": PROGRESS_COMPLETED,
    "утверждено": PROGRESS_COMPLETED,
    "согласован": PROGRESS_COMPLETED,
    "согласовано": PROGRESS_COMPLETED,
    "принят": PROGRESS_COMPLETED,
    "принято": PROGRESS_COMPLETED,
    "finished": PROGRESS_COMPLETED,
    "resolved": PROGRESS_COMPLETED,
    "решён": PROGRESS_COMPLETED,
    "решен": PROGRESS_COMPLETED,
    "решено": PROGRESS_COMPLETED,
    "closed": PROGRESS_COMPLETED,
    "закрыт": PROGRESS_COMPLETED,
    "confirmed": PROGRESS_COMPLETED,
    "подтверждён": PROGRESS_COMPLETED,
    "подтвержден": PROGRESS_COMPLETED,
    "achieved": PROGRESS_COMPLETED,
    "достигнута": PROGRESS_COMPLETED,
    "выполнена": PROGRESS_COMPLETED,
    "выполнено": PROGRESS_COMPLETED,
    "на утверждение": PROGRESS_IN_PROGRESS,
}

_STATUS_PROGRESS_PATTERNS = sorted(_STATUS_PROGRESS.items(), key=lambda x: -len(x[0]))


def normalize_status_name(name):
    if not name:
        return ""
    s = str(name).strip().lower().replace("_", " ")
    return " ".join(s.split())


def _progress_from_status_flags(flags):
    if flags is None:
        return None
    try:
        import cerebro
        from twin_plugin.pycerebro import dbtypes
    except ImportError:
        return None

    try:
        stopped = cerebro.core.has_flag(flags, dbtypes.STATUS_FLAG_WORK_STOPPED)
        started = cerebro.core.has_flag(flags, dbtypes.STATUS_FLAG_WORK_STARTED)
        if stopped and not started:
            return PROGRESS_COMPLETED
        if started and not stopped:
            return PROGRESS_IN_PROGRESS
    except Exception:
        pass
    return None


def progress_from_status_info(status_info, name_catalog=None, flags_catalog=None):
    """
    Map one status dict to 0, 50, or 100.
    Resolves empty names via catalog; uses status flags when name is unknown.
    """
    if not status_info:
        return None

    name = normalize_status_name(status_info.get("name"))
    sid = status_info.get("id")
    if not name and sid is not None:
        catalog = name_catalog if name_catalog is not None else _cerebro_status_catalog()
        name = normalize_status_name(
            catalog.get(_status_id_key(sid)) or catalog.get(sid) or ""
        )

    if name:
        if name in _STATUS_PROGRESS:
            return _STATUS_PROGRESS[name]
        for pattern, pct in _STATUS_PROGRESS_PATTERNS:
            if pattern in name:
                return pct

    if sid is not None and sid not in (0, "0"):
        flags_map = (
            flags_catalog if flags_catalog is not None else _cerebro_status_flags_catalog()
        )
        pct = _progress_from_status_flags(flags_map.get(_status_id_key(sid)))
        if pct is not None:
            return pct

    if name:
        return PROGRESS_READY
    return None


def leaf_progress_percent(task_id, node=None):
    """
    Map one leaf task to 0, 50, or 100 from all status sources and optional progress field.
    Empty/unknown status -> 0% (ready to start).
    """
    try:
        import cerebro

        task = cerebro.core.task(task_id)
    except Exception:
        return PROGRESS_READY

    progress_field_pct = None
    try:
        value = task.progress()
        if value is not None:
            progress_field_pct = max(
                PROGRESS_READY,
                min(PROGRESS_COMPLETED, int(round(float(value)))),
            )
            if _task_has_own_progress(task) or progress_field_pct > PROGRESS_READY:
                return progress_field_pct
    except Exception:
        pass

    pcts = []
    status_infos = iter_task_status_infos(task)
    for status_info in status_infos:
        pct = progress_from_status_info(status_info)
        if pct is not None:
            pcts.append(pct)

    if pcts:
        result = max(pcts)
        if progress_field_pct is not None:
            result = max(result, progress_field_pct)
        return result

    if progress_field_pct is not None:
        return progress_field_pct

    return PROGRESS_READY


def derive_status_from_progress(progress_pct):
    """Synthetic Cerebro status label for Tracker mapping."""
    if progress_pct >= 100:
        return {"name": "completed"}
    if progress_pct > 0:
        return {"name": "in progress"}
    return {"name": "ready to start"}


def compute_rollup_for_branch(branch_id, nodes_by_id=None):
    """
    Roll up all leaf descendants under branch_id.
    Returns dict with progress, status, leaf_count, breakdown {0, 50, 100}.
    """
    from .populate_cerebro_structure import iter_subtree_leaves

    nodes_by_id = nodes_by_id or {}
    leaf_progress = []
    branch_name = (nodes_by_id.get(branch_id) or {}).get("name") or str(branch_id)

    for i, (_leaf_id, _leaf_node) in enumerate(
        iter_subtree_leaves(branch_id, nodes_by_id)
    ):
        leaf_progress.append(leaf_progress_percent(_leaf_id, _leaf_node))
        if i % 20 == 19:
            try:
                from PyQt6.QtWidgets import QApplication

                QApplication.processEvents()
            except Exception:
                pass

    if not leaf_progress:
        return {
            "progress": float(PROGRESS_READY),
            "status": derive_status_from_progress(PROGRESS_READY),
            "leaf_count": 0,
            "breakdown": {0: 0, 50: 0, 100: 0},
            "branch_name": branch_name,
        }

    breakdown = {0: 0, 50: 0, 100: 0}
    for pct in leaf_progress:
        breakdown[pct] = breakdown.get(pct, 0) + 1

    mean_progress = sum(leaf_progress) / float(len(leaf_progress))
    rounded = int(round(mean_progress))

    return {
        "progress": float(rounded),
        "status": derive_status_from_progress(rounded),
        "leaf_count": len(leaf_progress),
        "breakdown": breakdown,
        "branch_name": branch_name,
    }


def build_rollup_index(branch_ids, nodes_by_id=None):
    """branch_id -> rollup dict for each synced branch node."""
    index = {}
    for bid in branch_ids:
        index[bid] = compute_rollup_for_branch(bid, nodes_by_id)
    return index


def log_rollup_summary(branch_id, rollup):
    """Write one-line rollup summary to activity log."""
    if not rollup:
        return
    b = rollup.get("breakdown") or {}
    sync_activity_log(
        "Rollup %s: %d leaves → %d%% (open/ready=%d, in progress=%d, done=%d)"
        % (
            rollup.get("branch_name") or branch_id,
            rollup.get("leaf_count", 0),
            int(rollup.get("progress", 0)),
            b.get(0, 0),
            b.get(50, 0),
            b.get(100, 0),
        )
    )
