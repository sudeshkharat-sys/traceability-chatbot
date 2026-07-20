"""
Orphaned 3D Placement Cleanup Script
=====================================
One-time cleanup for a data-integrity bug (now fixed going forward): the 3D
Layout view used to leave a placed model's row behind in
`z3d_layout_placements` even after its line's assignment was removed in
Layout Preparation, or after its station box was deleted/redrawn. Those
leftover rows kept rendering as a stray/stale model on a box that Layout
Preparation shows as unassigned.

What this script does:
  - Reads (never writes) `station_boxes` and `line_model_mappings`.
  - For each layout, finds every placement whose line_group_id matches a
    box that STILL EXISTS in that layout, but for which NO mapping exists
    (no assignment at all, for any car model) — i.e. exactly the "box is
    empty in Layout Preparation but 3D still shows a model" case.
  - Deletes ONLY those rows from `z3d_layout_placements`.

What it will NEVER touch:
  - The model library (`z3d_library` / uploaded GLB files) — not read or
    written at all.
  - Any placement whose line currently has an active mapping (a real
    assigned model is left completely alone).
  - Placements with no line_group_id (manual/ad-hoc placements not tied to
    a line) — left alone, since there's no assignment concept to compare
    them against.
  - Placements whose line_group_id doesn't match any current box at all
    (leftover from a box that's since been deleted/renamed) — those are
    already cleaned up automatically the next time that layout is saved in
    Layout Preparation, so this script skips them to stay narrowly scoped.

Usage:
    cd nashik-chatbot-pq

    # Dry run (default) — reports what WOULD be deleted, deletes nothing
    python scripts/cleanup_orphaned_placements.py

    # Restrict to one layout
    python scripts/cleanup_orphaned_placements.py --layout-id 12

    # Actually delete the rows found above
    python scripts/cleanup_orphaned_placements.py --apply
    python scripts/cleanup_orphaned_placements.py --layout-id 12 --apply
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.connectors.state_db_connector import StateDBConnector
from app.queries import LayoutQueries, StationBoxQueries, LineModelMappingQueries, Z3DPlacementQueries


def _row(r) -> dict:
    return dict(r._mapping)


def find_orphaned_placements(connector: StateDBConnector, layout_id: int) -> list:
    boxes = [_row(b) for b in connector.execute_query(StationBoxQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})]
    valid_box_names = {b["name"] for b in boxes if b.get("name")}

    mappings = [_row(m) for m in connector.execute_query(LineModelMappingQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})]
    mapped_lines = {m["line_group_id"] for m in mappings}

    placements = [_row(p) for p in connector.execute_query(Z3DPlacementQueries.LIST_BY_LAYOUT, {"layout_id": layout_id})]

    orphaned = []
    for p in placements:
        line = p.get("line_group_id")
        if not line:
            continue                    # not tied to a line — leave alone
        if line not in valid_box_names:
            continue                    # box itself is gone — handled by normal save, skip here
        if line in mapped_lines:
            continue                    # still assigned — never touch
        orphaned.append(p)
    return orphaned


def main():
    parser = argparse.ArgumentParser(description="Clean up orphaned 3D placements on unassigned lines")
    parser.add_argument("--layout-id", type=int, default=None, help="Restrict to a single layout ID")
    parser.add_argument("--apply", action="store_true", help="Actually delete the rows found (default is dry-run report only)")
    args = parser.parse_args()

    connector = StateDBConnector()

    if args.layout_id is not None:
        exists = connector.execute_query(LayoutQueries.CHECK_EXISTS, {"layout_id": args.layout_id})
        if not exists:
            print(f"Layout {args.layout_id} not found.")
            return
        layout_ids = [args.layout_id]
    else:
        layout_ids = [_row(r)["id"] for r in connector.execute_query(LayoutQueries.LIST_LAYOUTS, {"user_id": None})]

    total = 0
    for layout_id in layout_ids:
        orphaned = find_orphaned_placements(connector, layout_id)
        if not orphaned:
            continue
        print(f"\nLayout {layout_id}: {len(orphaned)} orphaned placement(s)")
        for p in orphaned:
            print(f"  - placement id={p['id']}  line='{p['line_group_id']}'  "
                  f"station='{p['station_id']}'  model='{p['model_name']}'")
            if args.apply:
                connector.execute_update(Z3DPlacementQueries.DELETE, {"placement_id": p["id"]})
        total += len(orphaned)

    print(f"\n{'Deleted' if args.apply else 'Found (dry run, nothing deleted)'}: {total} orphaned placement(s) total.")
    if not args.apply and total:
        print("Re-run with --apply to actually delete these rows.")


if __name__ == "__main__":
    main()
