# coding: utf-8
"""
Examples: *boards* (agile / Kanban boards) and *saved filters*.

The yandex_tracker_client package does not define a ``dashboard`` class. In the
Tracker HTTP API, boards live under ``/v2/boards`` (TrackerClient.boards); saved
filters under ``/v2/filters`` (TrackerClient.filters). Those often back what users
call “dashboards” in the UI.

Reference repo: https://github.com/yandex/yandex_tracker_client
"""

from __future__ import print_function

import os
import sys

from tracker_env import make_client


def main():
    client = make_client()

    # --- Boards: list and inspect ---
    print("Boards (iterate client.boards):")
    for board in list(client.boards)[:10]:
        bid = getattr(board, "id", None)
        name = getattr(board, "name", None)
        print(" ", bid, name)
        if os.environ.get("EXAMPLE_BOARD_DETAIL_ID") == str(bid):
            # Sub-resources from collections.Boards (BoardColumns, BoardSprints)
            try:
                col_list = list(board.columns)
                print("    columns:", [getattr(c, "name", c) for c in col_list])
            except Exception as ex:
                print("    columns:", ex)
            try:
                sprint_list = list(board.sprints)[:5]
                print("    sprints (sample):", [getattr(s, "name", s) for s in sprint_list])
            except Exception as ex:
                print("    sprints:", ex)

    board_id = os.environ.get("EXAMPLE_BOARD_ID")
    if board_id:
        b = client.boards[board_id]
        print("Board by id:", getattr(b, "name", None), "query:", getattr(b, "query", None))
        if os.environ.get("EXAMPLE_UPDATE_BOARD", "").lower() in ("1", "true", "yes"):
            # PATCH fields supported by API for your org (name, query, etc.)
            new_name = os.environ.get("EXAMPLE_BOARD_NAME", b.name)
            b.update(name=new_name)
            print("Board updated name ->", new_name)

    # --- Saved filters (named issue queries) ---
    print("Saved filters (iterate client.filters):")
    for f in list(client.filters)[:10]:
        print(
            " ",
            getattr(f, "id", None),
            getattr(f, "name", None),
            "query:",
            getattr(f, "query", None),
        )

    if os.environ.get("EXAMPLE_CREATE_FILTER", "").lower() in ("1", "true", "yes"):
        fname = os.environ.get("EXAMPLE_FILTER_NAME", "API example filter")
        fquery = os.environ.get("EXAMPLE_FILTER_QUERY", "Assignee: me()")
        nf = client.filters.create(name=fname, query=fquery)
        print("Created filter:", getattr(nf, "id", None), getattr(nf, "name", None))

    print(
        "\nOptional: EXAMPLE_BOARD_ID, EXAMPLE_BOARD_DETAIL_ID=id while listing, "
        "EXAMPLE_UPDATE_BOARD=true, EXAMPLE_CREATE_FILTER=true."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
