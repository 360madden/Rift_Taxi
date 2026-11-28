"""Build a portable review catalog from explicitly pinned local packages.

No game access, route generation, coordinate conversion or movement
authorization occurs here. The plan supplies only local labels and external
package IDs; scope and requested goal are derived from verified package bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .contracts import TraceError, _read_bounded, _strict_json
from .world_candidate_review import content_id, require, xyz
from .world_review_package import open_package
from .world_route_catalog import (
    SCHEMA, MAX_CATALOG_BYTES, MAX_ENTRIES, FILENAME, RESERVED,
    _id, _sha, _ordinary,
)

PLAN_SCHEMA = "taxi.world-review-catalog-plan/1"


def _filename(value):
    require(isinstance(value, str) and FILENAME.fullmatch(value)
            and value.split(".")[0] not in RESERVED,
            "invalid package or output filename")
    return value


def build_catalog(plan_path, *, expected_plan_sha256):
    """Return deterministic UTF-8 catalog bytes; never write or mutate files.

    The exact plan pin protects the caller's chosen labels and package IDs.
    Reopening each externally pinned package establishes consistency with
    those IDs, not source authenticity or physical route traversability.
    A wrong package or contradictory label invalidates the entire catalog.
    """
    _sha(expected_plan_sha256, "plan SHA")
    path = Path(plan_path)
    _ordinary(path)
    raw = _read_bounded(path, MAX_CATALOG_BYTES, "world catalog plan")
    require(hashlib.sha256(raw).hexdigest() == expected_plan_sha256,
            "catalog plan SHA mismatch")
    plan = _strict_json(raw, "world catalog plan")
    require(isinstance(plan, dict) and set(plan) == {"schema", "entries"}
            and plan["schema"] == PLAN_SCHEMA, "invalid catalog plan schema")
    items = plan["entries"]
    require(isinstance(items, list) and 1 <= len(items) <= MAX_ENTRIES,
            "invalid catalog plan size")
    # Validate the complete inventory before opening even one package.
    routes, names, pins = set(), set(), set()
    for row in items:
        require(isinstance(row, dict) and set(row) == {
            "routeId", "destinationId", "packageFile", "packageId"},
            "invalid catalog plan entry")
        route = _id(row["routeId"], "route ID")
        _id(row["destinationId"], "destination ID")
        name = _filename(row["packageFile"])
        pin = _sha(row["packageId"], "package ID")
        require(route not in routes and name not in names and pin not in pins,
                "duplicate catalog identity")
        routes.add(route)
        names.add(name)
        pins.add(pin)

    rows, goals = [], {}
    for row in sorted(items, key=lambda x: x["routeId"]):
        package = path.parent / row["packageFile"]
        _ordinary(package)
        review = open_package(package, expected_package_id=row["packageId"])
        world = review["world"]["sourceWorld"]
        require(isinstance(world, str) and 0 < len(world) <= 128
                and world == world.strip(), "invalid source world")
        frame = content_id(review["coordinates"])
        patch = _sha(review["patchId"], "patch ID")
        goal = xyz(review["query"]["requestedGoalXYZ"])
        # Local labels cannot conflate different destinations in one scope.
        # Use the exact same scope and coordinate equality as the selector.
        scope = (row["destinationId"], world, frame, patch)
        require(scope not in goals or goals[scope] == goal,
                "contradictory destination coordinates")
        goals[scope] = goal
        rows.append({**row, "sourceWorld": world, "frameSHA256": frame,
                     "patchId": patch, "destinationXYZ": list(goal)})

    # Stable bytes independent of input inventory order, source whitespace,
    # platform newline convention and working-directory spelling.
    encoded = (json.dumps({"schema": SCHEMA, "entries": rows},
                          sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    require(len(encoded) <= MAX_CATALOG_BYTES, "catalog exceeds byte limit")
    return encoded


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan", type=Path)
    p.add_argument("--expected-plan-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        _filename(a.out.name)
        # A catalog resolves package basenames relative to its own directory.
        # Do not produce an apparently valid but unusable relocated catalog.
        require(a.out.parent.resolve() == a.plan.parent.resolve(),
                "output must share the plan/package directory")
        encoded = build_catalog(a.plan, expected_plan_sha256=a.expected_plan_sha256)
        # Exclusive binary creation preserves canonical bytes and never
        # overwrites existing receipts, plans or source packages.
        with a.out.open("xb") as stream:
            stream.write(encoded)
        print(json.dumps({
            "schema": "taxi.world-review-catalog-build/1",
            "classification": "OFFLINE_REVIEW_ONLY",
            "planSHA256": a.expected_plan_sha256,
            "catalogSHA256": hashlib.sha256(encoded).hexdigest(),
            "entryCount": len(json.loads(encoded)["entries"]),
            "physicalQualification": False,
            "productionInputAuthorized": False,
            "gameInputSent": False,
        }, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (TraceError, OSError, ValueError, RecursionError) as exc:
        p.exit(2, f"World catalog build refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
