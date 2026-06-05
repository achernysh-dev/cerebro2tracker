# coding: utf-8
"""
Examples: Tracker *projects* (classic project objects).

The Python client exposes two related entry points:

1) client.projects — REST collection ``/v2/projects/{id}`` (Queues, teams, dates).
   See Projects in yandex_tracker_client.collections.

2) client.project — *entity* API ``/v2/entities/project/{id}`` (goals/portfolios product).
   See Project(Entity) in the same module; use .find() for search.

There is no separate ``dashboard`` resource in yandex_tracker_client; boards and
saved filters are the closest UI concepts — see example_boards_and_filters.py.
"""

from __future__ import print_function

import os
import sys

from tracker_env import make_client


def dump_project_brief(p):
    return {
        "id": getattr(p, "id", None),
        "key": getattr(p, "key", None),
        "name": getattr(p, "name", None),
        "status": getattr(p, "status", None),
    }


def main():
    client = make_client()

    # --- Classic projects: list / read ---
    projects = client.projects.get_all()
    print("Classic projects (first 10):")
    for p in list(projects)[:10]:
        print(" ", dump_project_brief(p))

    project_id = os.environ.get("EXAMPLE_PROJECT_ID")
    if project_id:
        proj = client.projects[project_id]
        print("Project by id %r:" % project_id, dump_project_brief(proj))
        # Optional nested reads (GET on subpaths)
        try:
            perms = proj.permissions
            print("  permissions keys:", list(perms.keys()) if isinstance(perms, dict) else type(perms))
        except Exception as ex:
            print("  permissions:", ex)
        try:
            acc = proj.access
            print("  access keys:", list(acc.keys()) if isinstance(acc, dict) else type(acc))
        except Exception as ex:
            print("  access:", ex)

    # --- Update project (PATCH) if your org allows it ---
    if os.environ.get("EXAMPLE_UPDATE_PROJECT", "").lower() in ("1", "true", "yes") and project_id:
        proj = client.projects[project_id]
        desc = os.environ.get("EXAMPLE_PROJECT_DESCRIPTION", "Updated via example_projects.py")
        proj.update(description=desc)
        print("Updated project description for", project_id)

    # --- Entity API: search projects (product “entities”) ---
    # filter/order fields depend on your Tracker configuration.
    ent_q = os.environ.get("EXAMPLE_ENTITY_PROJECT_QUERY")
    if ent_q is not None:
        try:
            entity_hits = client.project.find(search_string=ent_q, per_page=5)
            print("Entity projects search (up to 5) for %r:" % ent_q)
            for e in entity_hits:
                print(" ", getattr(e, "id", None), getattr(e, "shortId", None), e._path)
        except Exception as ex:
            print("Entity project search failed:", ex)
    else:
        print(
            "Skipping entity project search (set EXAMPLE_ENTITY_PROJECT_QUERY to enable)."
        )

    print(
        "\nSet EXAMPLE_PROJECT_ID to a numeric/string id from the list to drill in. "
        "Set EXAMPLE_UPDATE_PROJECT=true to PATCH description."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
