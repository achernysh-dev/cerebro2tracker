# coding: utf-8
import unittest

from twin_plugin.sync_engine import collect_sync_jobs


def _nodes(*pairs):
    """pairs: (id, name, parent_id)"""
    out = {}
    for tid, name, parent in pairs:
        out[tid] = {"id": tid, "name": name, "cerebro_parent_id": parent}
    return out


class CollectSyncJobsTests(unittest.TestCase):
    def test_nested_checked_becomes_project_not_cerebro_root(self):
        """Check BlackKing under SHAHMAT → project BlackKing, not root SHAHMAT."""
        nodes = _nodes(
            (1, "SHAHMAT", None),
            (2, "characters", 1),
            (3, "BlackKing", 2),
        )
        checked = [nodes[3]]
        jobs = collect_sync_jobs(checked, nodes, root_ids={1})

        projects = [j for j in jobs if j["kind"] == "project"]
        issues = [j for j in jobs if j["kind"] == "issue"]
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["node"]["name"], "BlackKing")
        self.assertEqual(projects[0]["root_id"], 3)
        self.assertEqual(issues, [])

    def test_checked_parent_and_child(self):
        nodes = _nodes(
            (1, "Root", None),
            (2, "SubGroup", 1),
            (3, "BranchA", 2),
            (4, "BranchB", 2),
        )
        checked = [nodes[2], nodes[3]]
        jobs = collect_sync_jobs(checked, nodes, root_ids={1})

        projects = {j["root_id"]: j for j in jobs if j["kind"] == "project"}
        issues = [j for j in jobs if j["kind"] == "issue"]
        self.assertEqual(set(projects.keys()), {2})
        self.assertEqual(projects[2]["node"]["name"], "SubGroup")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["node"]["name"], "BranchA")
        self.assertEqual(issues[0]["root_id"], 2)
        self.assertIsNone(issues[0]["cerebro_parent_id"])

    def test_sibling_branches_each_own_project(self):
        nodes = _nodes(
            (1, "Root", None),
            (2, "SubGroup", 1),
            (3, "BranchA", 2),
            (4, "BranchB", 2),
        )
        checked = [nodes[3], nodes[4]]
        jobs = collect_sync_jobs(checked, nodes, root_ids={1})

        projects = [j for j in jobs if j["kind"] == "project"]
        issues = [j for j in jobs if j["kind"] == "issue"]
        self.assertEqual(len(projects), 2)
        self.assertEqual({p["node"]["name"] for p in projects}, {"BranchA", "BranchB"})
        self.assertEqual(issues, [])

    def test_nested_issue_parent_link(self):
        nodes = _nodes(
            (1, "Root", None),
            (2, "SubGroup", 1),
            (3, "BranchA", 2),
            (4, "BranchB", 3),
        )
        checked = [nodes[2], nodes[3], nodes[4]]
        jobs = collect_sync_jobs(checked, nodes, root_ids={1})

        issues = {j["node"]["id"]: j for j in jobs if j["kind"] == "issue"}
        self.assertIsNone(issues[3]["cerebro_parent_id"])
        self.assertEqual(issues[4]["cerebro_parent_id"], 3)
        self.assertEqual(issues[4]["root_id"], 2)

    def test_cerebro_root_checked_still_project(self):
        nodes = _nodes((1, "Root", None), (2, "Child", 1))
        checked = [nodes[1]]
        jobs = collect_sync_jobs(checked, nodes, root_ids={1})

        projects = [j for j in jobs if j["kind"] == "project"]
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["node"]["name"], "Root")


if __name__ == "__main__":
    unittest.main()
