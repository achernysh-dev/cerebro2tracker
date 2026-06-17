# coding: utf-8
"""
Tracker hierarchy fetch (portfolios → projects → queues → tasks).
Adapted from tests/example_project_structure.py for plugin use.
"""
from collections import defaultdict

PORTFOLIO_FIELDS = (
    "summary,entityStatus,parentEntity,author,lead,followers,teamUsers,start,end"
)
PROJECT_FIELDS = PORTFOLIO_FIELDS + ",issueQueues"
DEFAULT_ENTITY_LIMIT = 500
DEFAULT_ISSUES_PER_QUEUE = 100


def _v3_search_all(client, entity_type, fields, max_items=500):
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
    fields = raw.get("fields") or {}
    entity_type = raw.get("entityType")
    queues = []
    for q in fields.get("issueQueues") or []:
        if isinstance(q, dict) and q.get("key"):
            queues.append(
                {"id": q.get("id"), "key": q.get("key"), "name": q.get("display")}
            )
    return {
        "nodeType": entity_type,
        "entityType": entity_type,
        "id": raw.get("id"),
        "shortId": raw.get("shortId"),
        "name": fields.get("summary"),
        "status": fields.get("entityStatus"),
        "parent": _parse_parent(fields.get("parentEntity")),
        "queues": queues,
        "links": links,
        "_children": [],
    }


def _collect_entities(client, limit, include_links=True, include_queues=True):
    flat = []
    project_fields = PROJECT_FIELDS if include_queues else PORTFOLIO_FIELDS
    for entity_type, fields in (
        ("portfolio", PORTFOLIO_FIELDS),
        ("project", project_fields),
    ):
        try:
            values = _v3_search_all(client, entity_type, fields, max_items=limit)
        except Exception as ex:
            flat.append(
                {
                    "nodeType": entity_type,
                    "error": str(ex),
                    "id": None,
                    "name": entity_type,
                    "_children": [],
                }
            )
            continue
        for raw in values:
            eid = raw.get("id")
            if include_links and eid:
                links = _v3_links(client, entity_type, eid)
                links = [_parse_link(x) for x in links if _parse_link(x)]
            else:
                links = []
            flat.append(_normalize_entity(raw, links))
    return flat


def _build_tree(flat):
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
    return {
        "nodeType": "task",
        "id": issue.key,
        "key": issue.key,
        "name": getattr(issue, "summary", None),
        "status": _ref(getattr(issue, "status", None), "key", "display"),
        "children": [],
        "depth": depth,
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
    ref = dict(queue_ref or {})
    key = ref.get("key")
    if not key:
        return ref
    ref.setdefault("key", key)
    try:
        q = client.queues[key]
        ref["name"] = getattr(q, "name", None) or ref.get("name") or key
    except Exception as ex:
        ref.setdefault("name", ref.get("name") or key)
        ref["fetchError"] = str(ex)
    return ref


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


def _queue_node(client, queue_ref, project_rec, block):
    meta = _enrich_queue(client, queue_ref)
    key = meta.get("key")
    return {
        "nodeType": "queue",
        "id": meta.get("id"),
        "key": key,
        "name": meta.get("name") or key,
        "taskCount": block.get("count", 0),
        "error": block.get("error"),
        "children": block.get("tasks") or [],
    }


def _attach_tasks(client, rec, per_page):
    if rec.get("nodeType") != "project":
        for ch in rec.get("_children") or []:
            _attach_tasks(client, ch, per_page)
        return
    for q in rec.get("queues") or []:
        if not q.get("key"):
            continue
        block = _fetch_tasks(client, q["key"], per_page)
        rec["_children"].append(_queue_node(client, q, rec, block))
    for ch in rec.get("_children") or []:
        if ch.get("nodeType") in ("portfolio", "project"):
            _attach_tasks(client, ch, per_page)


def _strip_internal(rec):
    out = {k: v for k, v in rec.items() if k != "_children" and not k.startswith("_")}
    if rec.get("nodeType") == "task":
        out["children"] = [_strip_internal(c) for c in (rec.get("children") or [])]
        return out
    out["children"] = [_strip_internal(c) for c in (rec.get("_children") or [])]
    return out


def _sort_roots(roots):
    portfolios = [r for r in roots if r.get("nodeType") == "portfolio"]
    projects = [r for r in roots if r.get("nodeType") == "project"]
    portfolios.sort(key=lambda n: n.get("name") or "")
    projects.sort(key=lambda n: n.get("name") or "")
    return portfolios + projects


def build_hierarchy(
    client,
    limit=None,
    per_page=None,
    include_queues=True,
    include_links=True,
    exclude_orphan_projects=False,
):
    limit = limit or DEFAULT_ENTITY_LIMIT
    per_page = per_page or DEFAULT_ISSUES_PER_QUEUE
    flat = _collect_entities(
        client, limit, include_links=include_links, include_queues=include_queues
    )
    roots = _build_tree(flat)
    if exclude_orphan_projects:
        roots = [r for r in roots if r.get("nodeType") != "project"]
    if include_queues:
        for root in roots:
            _attach_tasks(client, root, per_page)
    return [_strip_internal(r) for r in _sort_roots(roots)]


def node_display_label(node):
    nt = node.get("nodeType") or "?"
    name = node.get("name") or node.get("key") or node.get("id") or "?"
    if nt == "queue":
        return "[%s] %s (%s tasks)" % (nt, name, node.get("taskCount", 0))
    if nt == "task":
        return "[%s] %s" % (nt, name)
    return "[%s] %s" % (nt, name)
