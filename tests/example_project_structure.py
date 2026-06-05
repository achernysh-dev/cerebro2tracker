# coding: utf-8
"""
Tracker structure: portfolios + projects + tasks with parent/child hierarchy.

Matches the "Проекты и портфели → Структура" view:
  - portfolio — container, may nest other portfolios and projects
  - project — nested under portfolios; queues (e.g. ASSETPROD) hold tasks under projects

Uses Tracker Entities API v3 for names, parentEntity, assignees, links, queues.
Writes tracker_structure.json and prints a nested tree.

Env: TRACKER_TOKEN + TRACKER_CLOUD_ORG_ID or TRACKER_ORG_ID (see tracker_env.py).

Optional:
    STRUCTURE_OUTPUT_FILE, STRUCTURE_NO_FILE, STRUCTURE_ISSUES_PER_QUEUE=100
    STRUCTURE_ENTITY_LIMIT=500   max portfolios+projects to load (paginated; min 50)
    STRUCTURE_QUEUE_KEYS=ASSETPROD (attach queue to project when names match)
"""

from __future__ import print_function

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from tracker_env import make_client

DEFAULT_OUTPUT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tracker_structure.json")
)

PORTFOLIO_FIELDS = (
    "summary,entityStatus,parentEntity,author,lead,followers,teamUsers,start,end"
)
PROJECT_FIELDS = PORTFOLIO_FIELDS + ",issueQueues"


def _v3_search_all(client, entity_type, fields, max_items=500):
    """POST /v3/entities/{type}/_search — follow pages until all entities loaded."""
    url = client._connection.build_url("/v3/entities/%s/_search" % entity_type)
    per_page = min(50, max_items)
    all_values = []
    page = 1
    while len(all_values) < max_items:
        resp = client._connection.session.post(
            url,
            params={"perPage": per_page, "page": page, "fields": fields},
            json={},
            headers=dict(client._connection.session.headers),
            timeout=client._connection.timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                "%s search failed: %s %s" % (entity_type, resp.status_code, resp.text)
            )
        data = resp.json()
        batch = data.get("values") or []
        all_values.extend(batch)
        total_pages = data.get("pages") or 1
        if page >= total_pages or not batch:
            break
        page += 1
    return all_values[:max_items]


def _v3_links(client, entity_type, entity_id):
    url = client._connection.build_url(
        "/v3/entities/%s/%s/links" % (entity_type, entity_id)
    )
    try:
        resp = client._connection.session.get(
            url,
            params={"fields": "id,summary"},
            headers=dict(client._connection.session.headers),
            timeout=client._connection.timeout,
        )
        if resp.status_code >= 400:
            return []
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception:
        return []


def _parse_user(u):
    if not u or not isinstance(u, dict):
        return None
    return {
        "id": u.get("id"),
        "display": u.get("display"),
        "login": u.get("login"),
        "cloudUid": u.get("cloudUid"),
    }


def _parse_users(lst):
    if not lst:
        return []
    return [_parse_user(u) for u in lst if u]


def _parse_parent(parent_entity):
    if not parent_entity or not isinstance(parent_entity, dict):
        return None
    primary = parent_entity.get("primary")
    if not primary:
        return None
    return {
        "id": primary.get("id"),
        "name": primary.get("display") or primary.get("summary"),
        "self": primary.get("self"),
    }


def _parse_link(item):
    if not isinstance(item, dict):
        return None
    vals = item.get("linkFieldValues") or item
    return {
        "type": item.get("type") or item.get("relationship"),
        "id": vals.get("id"),
        "name": vals.get("summary") or vals.get("display"),
    }


def _normalize_entity(raw, links):
    """One flat record before tree build."""
    fields = raw.get("fields") or {}
    entity_type = raw.get("entityType")  # portfolio | project
    node_type = entity_type  # portfolio | project

    queues = []
    for q in fields.get("issueQueues") or []:
        if isinstance(q, dict) and q.get("key"):
            queues.append(
                {
                    "id": q.get("id"),
                    "key": q.get("key"),
                    "name": q.get("display"),
                }
            )

    return {
        "nodeType": node_type,
        "entityType": entity_type,
        "id": raw.get("id"),
        "shortId": raw.get("shortId"),
        "name": fields.get("summary"),
        "status": fields.get("entityStatus"),
        "parent": _parse_parent(fields.get("parentEntity")),
        "author": _parse_user(fields.get("author") or raw.get("createdBy")),
        "lead": _parse_user(fields.get("lead")),
        "assignee": _parse_user(fields.get("lead")),
        "followers": _parse_users(fields.get("followers")),
        "teamUsers": _parse_users(fields.get("teamUsers")),
        "start": fields.get("start"),
        "end": fields.get("end"),
        "queues": queues,
        "links": links,
        "createdAt": raw.get("createdAt"),
        "updatedAt": raw.get("updatedAt"),
        "self": raw.get("self"),
        "_children": [],
    }


def _collect_entities(client, limit):
    flat = []
    for entity_type, fields in (
        ("portfolio", PORTFOLIO_FIELDS),
        ("project", PROJECT_FIELDS),
    ):
        try:
            values = _v3_search_all(client, entity_type, fields, max_items=limit)
        except Exception as ex:
            flat.append(
                {
                    "nodeType": entity_type,
                    "entityType": entity_type,
                    "error": str(ex),
                    "id": None,
                    "name": entity_type,
                    "_children": [],
                }
            )
            continue
        for raw in values:
            eid = raw.get("id")
            links = _v3_links(client, entity_type, eid) if eid else []
            links = [_parse_link(x) for x in links if _parse_link(x)]
            flat.append(_normalize_entity(raw, links))
    return flat


def _build_tree(flat):
    """Nest by parent.id (portfolio/project hierarchy from Tracker UI)."""
    by_id = {}
    for rec in flat:
        if rec.get("id"):
            by_id[str(rec["id"])] = rec

    roots = []
    for rec in flat:
        if rec.get("error"):
            roots.append(rec)
            continue
        parent = rec.get("parent")
        pid = parent.get("id") if parent else None
        if pid and str(pid) in by_id and str(pid) != str(rec.get("id")):
            by_id[str(pid)]["_children"].append(rec)
        else:
            roots.append(rec)
    return roots


def _issue_parent_key(issue):
    parent = getattr(issue, "parent", None)
    if parent is None and hasattr(issue, "_value"):
        parent = issue._value.get("parent")
    if parent is None:
        return None
    if isinstance(parent, str):
        return parent
    return getattr(parent, "key", None) or (
        parent.get("key") if isinstance(parent, dict) else None
    )


def _ref(obj, *attrs):
    if obj is None:
        return None
    if isinstance(obj, dict):
        for a in attrs:
            if a in obj and obj[a] is not None:
                return obj[a]
        return obj.get("display") or obj.get("key") or obj.get("id")
    for a in attrs:
        v = getattr(obj, a, None)
        if v is not None:
            return v
    return None


def _task_node(issue, depth=0):
    assignee = _ref(getattr(issue, "assignee", None), "display", "login", "id")
    parent_key = _issue_parent_key(issue)
    parent = {"id": parent_key, "name": parent_key} if parent_key else None
    return {
        "nodeType": "task",
        "id": issue.key,
        "key": issue.key,
        "name": getattr(issue, "summary", None),
        "status": _ref(getattr(issue, "status", None), "key", "display"),
        "type": _ref(getattr(issue, "type", None), "key", "name", "display"),
        "assignee": {"display": assignee} if assignee else None,
        "parent": parent,
        "depth": depth,
        "children": [],
    }


def _build_task_tree(issues):
    nodes = {i.key: _task_node(i) for i in issues}
    child_keys = defaultdict(list)
    roots = []
    keys = set(nodes)

    for issue in issues:
        pk = _issue_parent_key(issue)
        if pk and pk in keys:
            child_keys[pk].append(issue.key)
        else:
            roots.append(issue.key)

    def nest(key, depth):
        node = nodes[key]
        node["depth"] = depth
        node["children"] = [nest(k, depth + 1) for k in child_keys.get(key, [])]
        return node

    return [nest(k, 0) for k in roots]


def _enrich_queue(client, queue_ref):
    """Load queue details from Tracker /v2/queues/{key} and merge with issueQueues ref."""
    ref = dict(queue_ref or {})
    key = ref.get("key")
    if not key:
        return ref
    ref.setdefault("key", key)
    try:
        q = client.queues[key]
        ref["id"] = str(getattr(q, "id", None) or ref.get("id") or "")
        ref["key"] = getattr(q, "key", key) or key
        ref["name"] = getattr(q, "name", None) or ref.get("name") or key
        ref["description"] = getattr(q, "description", None)
        ref["lead"] = _parse_user(getattr(q, "lead", None))
        ref["self"] = getattr(q, "self", None)
        ref["defaultType"] = _ref(getattr(q, "defaultType", None), "name", "key", "display")
        ref["defaultPriority"] = _ref(getattr(q, "defaultPriority", None), "name", "key", "display")
    except Exception as ex:
        ref.setdefault("name", ref.get("name") or key)
        ref["fetchError"] = str(ex)
    return ref


def _queue_node(client, queue_ref, project_rec, block, registry):
    """Build hierarchy node nodeType=queue; register in top-level queues map."""
    meta = _enrich_queue(client, queue_ref)
    key = meta.get("key")
    if key:
        registry[key] = {k: v for k, v in meta.items() if not k.startswith("_")}

    node = {
        "nodeType": "queue",
        "id": meta.get("id"),
        "key": key,
        "name": meta.get("name") or key,
        "description": meta.get("description"),
        "lead": meta.get("lead"),
        "defaultType": meta.get("defaultType"),
        "defaultPriority": meta.get("defaultPriority"),
        "self": meta.get("self"),
        "parent": {
            "id": project_rec.get("id"),
            "name": project_rec.get("name"),
            "nodeType": "project",
        },
        "taskCount": block.get("count", 0),
        "links": [],
        "error": block.get("error"),
        "fetchError": meta.get("fetchError"),
        "_children": block.get("tasks") or [],
    }
    return node


def _fetch_tasks(client, queue_key, per_page):
    try:
        issues = list(
            client.issues.find(
                filter={"queue": queue_key},
                order=["-updatedAt"],
                per_page=per_page,
            )
        )
        return {"queue": queue_key, "count": len(issues), "tasks": _build_task_tree(issues)}
    except Exception as ex:
        return {"queue": queue_key, "count": 0, "error": str(ex), "tasks": []}


def _extra_queue_keys():
    raw = os.environ.get("STRUCTURE_QUEUE_KEYS", "").strip()
    if not raw:
        return []
    return [q.strip() for q in raw.split(",") if q.strip()]


def _match_extra_queues(project_name, extra_keys):
    """Attach STRUCTURE_QUEUE_KEYS to project when name matches queue key (e.g. Динозавры)."""
    if not project_name or not extra_keys:
        return []
    matched = []
    for qk in extra_keys:
        if qk.lower() in (project_name or "").lower() or (project_name or "").lower() in qk.lower():
            matched.append(qk)
    return matched


def _attach_tasks(client, rec, per_page, registry):
    """Append queue → task trees under project nodes."""
    if rec.get("nodeType") != "project":
        for ch in rec.get("_children") or []:
            _attach_tasks(client, ch, per_page, registry)
        return

    by_key = {}
    for q in rec.get("queues") or []:
        if q.get("key"):
            by_key[q["key"]] = dict(q)
    for qk in _match_extra_queues(rec.get("name"), _extra_queue_keys()):
        if qk not in by_key:
            by_key[qk] = {"key": qk}

    for qk in sorted(by_key.keys()):
        block = _fetch_tasks(client, qk, per_page)
        rec["_children"].append(
            _queue_node(client, by_key[qk], rec, block, registry)
        )

    for ch in rec.get("_children") or []:
        if ch.get("nodeType") in ("portfolio", "project"):
            _attach_tasks(client, ch, per_page, registry)


def _strip_internal(rec):
    """Convert _children → children for JSON output."""
    out = {k: v for k, v in rec.items() if k != "_children" and not k.startswith("_")}
    if rec.get("nodeType") == "task":
        out["children"] = [_strip_internal(c) for c in (rec.get("children") or [])]
        return out
    out["children"] = [_strip_internal(c) for c in (rec.get("_children") or [])]
    return out


def build_hierarchy(client, limit, per_page):
    flat = _collect_entities(client, limit)
    roots = _build_tree(flat)
    registry = {}
    for root in roots:
        _attach_tasks(client, root, per_page, registry)
    hierarchy = [_strip_internal(r) for r in _sort_roots(roots)]
    return hierarchy, registry


def _sort_roots(roots):
    """Cases first, then top-level projects (same order as Tracker structure view)."""
    portfolios = [r for r in roots if r.get("nodeType") == "portfolio"]
    projects = [r for r in roots if r.get("nodeType") == "project"]
    portfolios.sort(key=lambda n: n.get("name") or "")
    projects.sort(key=lambda n: n.get("name") or "")
    return portfolios + projects


def _document(hierarchy, queues):
    queue_list = [queues[k] for k in sorted(queues.keys())]
    return {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": (
                "portfolio → project → queue → task; "
                "parentEntity defines portfolio/project nesting; "
                "issue parent defines task nesting"
            ),
            "nodeTypes": {
                "portfolio": "portfolio / container (портфель)",
                "project": "project (проект)",
                "queue": "issue queue (e.g. ASSETPROD)",
                "task": "issue (задача), may have subtasks in children",
            },
        },
        "queues": queues,
        "queuesList": queue_list,
        "hierarchy": hierarchy,
    }


def _write_json(path, document):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, ensure_ascii=False, indent=2, default=str)
    return path


def _node_label(node):
    nt = node.get("nodeType")
    name = node.get("name") or node.get("key") or node.get("id") or "?"
    if nt == "portfolio":
        return "[portfolio] %s  (id=%s, status=%s)" % (
            name, node.get("shortId") or node.get("id"), node.get("status")
        )
    if nt == "project":
        lead = (node.get("assignee") or {}).get("display") or "-"
        return "[project] %s  (id=%s, lead=%s)" % (
            name, node.get("shortId") or node.get("id"), lead
        )
    if nt == "queue":
        return "[queue] %s  %s  (%s tasks)" % (
            node.get("key"),
            (node.get("name") or "")[:30],
            node.get("taskCount", 0),
        )
    if nt == "task":
        return "[task] %s  %s  [%s]" % (
            node.get("key"), (name or "")[:45], node.get("status")
        )
    return "[%s] %s" % (nt, name)


def _print_tree(nodes, parent_prefix=""):
    count = len(nodes)
    for i, node in enumerate(nodes):
        is_last = i == count - 1
        branch = "└── " if is_last else "├── "
        print("%s%s%s" % (parent_prefix, branch, _node_label(node)))
        if node.get("error"):
            err_p = parent_prefix + ("    " if is_last else "│   ")
            print("%s  error: %s" % (err_p, node["error"]))
        ext = parent_prefix + ("    " if is_last else "│   ")
        links = node.get("links") or []
        for j, link in enumerate(links[:3]):
            lip = ext + ("└── " if j == min(2, len(links) - 1) and not node.get("children") else "├── ")
            print("%s[link] %s → %s" % (lip, link.get("type"), link.get("name")))
        children = node.get("children") or []
        if children:
            _print_tree(children, ext)


def _print_structure(document, output_path):
    print("Tracker structure (portfolios → projects → queues → tasks)")
    queues = document.get("queues") or {}
    if queues:
        print("Queues: %s" % ", ".join(sorted(queues.keys())))
    print("=" * 60)
    hierarchy = document.get("hierarchy") or []
    if hierarchy:
        _print_tree(hierarchy)
    else:
        print("(empty)")
    print("=" * 60)
    if output_path:
        print("JSON written to: %s" % output_path)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    client = make_client()
    limit = int(os.environ.get("STRUCTURE_ENTITY_LIMIT", "500"))
    if limit < 50:
        limit = 500
    per_page = int(os.environ.get("STRUCTURE_ISSUES_PER_QUEUE", "100"))

    hierarchy, queues = build_hierarchy(client, limit, per_page)
    document = _document(hierarchy, queues)

    output_path = None
    if os.environ.get("STRUCTURE_NO_FILE", "").lower() not in ("1", "true", "yes"):
        output_path = os.path.abspath(
            os.environ.get("STRUCTURE_OUTPUT_FILE", DEFAULT_OUTPUT)
        )
        _write_json(output_path, document)

    _print_structure(document, output_path)

    if os.environ.get("STRUCTURE_JSON", "").lower() in ("1", "true", "yes"):
        print(json.dumps(document, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
