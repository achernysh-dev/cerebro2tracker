# coding: utf-8
import cerebro

from .cerebro_task_meta import cerebro_task_path, cerebro_task_progress, cerebro_task_status
from .sync_log import log as sync_activity_log


def _task_has_children(task):
    try:
        return cerebro.core.has_flag(task.flags(), task.FLAG_HAS_CHILD)
    except Exception:
        return True


def task_summary_light(task, node_type="task"):
    """Minimal fields for tree display (no path/progress/status API calls)."""
    return {
        "id": task.id(),
        "name": task.name(),
        "start": task.start(),
        "finish": task.finish(),
        "type": node_type,
        "has_children": _task_has_children(task),
    }


def task_summary(task, node_type="task"):
    """Shallow task dict with path/progress/status (use at sync time, not tree scan)."""
    node = task_summary_light(task, node_type=node_type)
    node["path"] = cerebro_task_path(task)
    node["progress"] = cerebro_task_progress(task)
    node["status"] = cerebro_task_status(task)
    return node


def fetch_all_children(parent_id):
    """All immediate children (branches and leaves)."""
    children = []
    try:
        subtasks = cerebro.core.task_children(parent_id)
        if not subtasks:
            return children
        for sub in subtasks:
            children.append(task_summary_light(sub))
    except Exception as e:
        sync_activity_log("Error fetching children for %s: %s" % (parent_id, e))
    return children


def fetch_children_branches(parent_id):
    """Immediate branch children only (leaves skipped — not shown or synced)."""
    branches = []
    try:
        subtasks = cerebro.core.task_children(parent_id)
        if not subtasks:
            return branches
        for sub in subtasks:
            if _task_has_children(sub):
                branches.append(task_summary_light(sub))
    except Exception as e:
        sync_activity_log("Error fetching children for %s: %s" % (parent_id, e))
    return branches


def iter_subtree_leaves(branch_id, nodes_by_id=None):
    """
    BFS from branch_id; yield (leaf_id, leaf_node_dict) for every leaf descendant.
    If branch_id is itself a leaf, yield it once.
    """
    nodes_by_id = nodes_by_id or {}
    branch_node = nodes_by_id.get(branch_id)
    if branch_node is not None and not branch_node.get("has_children"):
        yield branch_id, branch_node
        return

    queue = [branch_id]
    while queue:
        parent_id = queue.pop(0)
        for child in fetch_all_children(parent_id):
            cid = child["id"]
            if child.get("has_children"):
                queue.append(cid)
            else:
                yield cid, child


def fetch_children_split(parent_id):
    """
    Fetch immediate children; split into branch nodes (shown in tree)
    and leaf nodes (legacy — prefer fetch_children_branches).
    Returns (branches, leaves).
    """
    branches = fetch_children_branches(parent_id)
    return branches, []


def fetch_children_shallow(parent_id):
    """All immediate children as flat list (used by blocking iterator)."""
    branches, leaves = fetch_children_split(parent_id)
    return branches + leaves


def iter_structure_bfs():
    """Blocking BFS — all levels including leaves."""
    queue = []
    for proj in cerebro.core.root_tasks():
        node = task_summary(proj, node_type="project")
        yield None, node
        if node["has_children"]:
            queue.append(node["id"])

    while queue:
        parent_id = queue.pop(0)
        for child in fetch_children_shallow(parent_id):
            yield parent_id, child
            if child["has_children"]:
                queue.append(child["id"])


def get_cerebro_structure():
    """Fetches the full project structure (blocking)."""
    nodes = {}
    roots = []
    for parent_id, node in iter_structure_bfs():
        entry = {**node, "children": []}
        nodes[node["id"]] = entry
        if parent_id is None:
            roots.append(entry)
        else:
            nodes[parent_id]["children"].append(entry)
    return roots


def main():
    print("Fetching Cerebro structure...", flush=True)
    struct = get_cerebro_structure()

    def print_node(node, indent=0):
        print("  " * indent + f"[{node['type']}] {node['name']} (ID: {node['id']})")
        for child in node["children"]:
            print_node(child, indent + 1)

    for root in struct:
        print_node(root)


if __name__ == "__main__":
    main()
