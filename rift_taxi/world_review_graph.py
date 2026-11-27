"""Local source-pinned route-package graph, strictly for offline review.

Each complete upstream package is one directed edge between its *snapped*
endpoints, retaining its original points and flags. Exact shared endpoints
within one source frame, world metadata and planner build permit a mathematical
review chain, not a verified traversal junction. No proximity connectors,
interior splitting, inferred reverse edges, coordinate conversion, model
execution or game access. Python 3.11+, standard library only.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path

from .contracts import TraceError
from .world_candidate_review import content_id, xyz
from .world_review_package import open_package
from .world_route_catalog import _catalog, _id, _ordinary, _sha, require


def load_graph(catalog, *, catalog_sha256, source_world, frame_sha256,
               patch_id, build_id):
    """Reopen scoped packages using their external pins; return review edges.

    Catalog entries contain requested goals, not necessarily actual endpoints.
    Retain both; construct topology only from exact snapped source XYZ.
    All matching world/frame/patch packages must pass intake even if their
    planner build differs. A different build never contributes graph edges.
    """
    _sha(frame_sha256, "frame SHA")
    _sha(patch_id, "patch ID")
    if not isinstance(source_world, str) or not source_world.strip() or len(source_world) > 128:
        raise TraceError("world review graph: invalid source world")
    if not isinstance(build_id, str) or not build_id.strip() or len(build_id) > 256:
        raise TraceError("world review graph: invalid build ID")
    root, rows = _catalog(catalog, catalog_sha256)
    edges = []
    excluded = []
    world_identity = None
    for row in sorted(rows, key=lambda item: item["routeId"]):
        if (row["sourceWorld"] != source_world or row["frameSHA256"] != frame_sha256
                or row["patchId"] != patch_id):
            continue
        path = root / row["packageFile"]
        _ordinary(path)
        review = open_package(path, expected_package_id=row["packageId"])
        require(review["world"]["sourceWorld"] == source_world
                and content_id(review["coordinates"]) == frame_sha256
                and review["patchId"] == patch_id, "package scope mismatch")
        require(xyz(review["query"]["requestedGoalXYZ"]) == xyz(row["destinationXYZ"]),
                "package requested destination mismatch")
        if review["buildId"] != build_id:
            excluded.append({"routeId": row["routeId"], "reason": "different-planner-build"})
            continue
        # Names alone do not establish a common world. Refuse conflicting
        # full upstream metadata rather than combining ambiguous geometry.
        identity = content_id(review["world"])
        require(world_identity is None or world_identity == identity,
                "conflicting source world metadata")
        world_identity = identity
        start = xyz(review["query"]["snappedStartXYZ"])
        end = xyz(review["query"]["snappedGoalXYZ"])
        points = review["points"]
        length = math.fsum(math.dist(a["xyz"], b["xyz"])
                           for a, b in zip(points, points[1:]))
        # A closed route cannot improve an endpoint-to-endpoint shortest path.
        # Keep its exclusion explicit rather than make a zero-cost self-loop.
        if start == end:
            excluded.append({"routeId": row["routeId"], "reason": "same-snapped-endpoint"})
            continue
        require(math.isfinite(length) and length > 0., "invalid review path length")
        edges.append({"routeId": row["routeId"], "destinationId": row["destinationId"],
                      "packageId": row["packageId"], "candidateId": review["candidateId"],
                      "source": review["source"], "sourceEvidence": review["sourceEvidence"],
                      "query": review["query"], "endpointOffsets": review["endpointOffsets"],
                      "startXYZ": list(start), "endXYZ": list(end),
                      "pathLength3D": length, "points": points})
    return {"schema": "taxi.world-review-graph/1", "classification": "OFFLINE_REVIEW_ONLY",
            "catalogSHA256": catalog_sha256, "sourceWorld": source_world,
            "worldMetadataSHA256": world_identity, "frameSHA256": frame_sha256,
            "patchId": patch_id, "buildId": build_id, "edges": edges, "excluded": excluded,
            "sourceAuthenticityEstablished": False, "patchCoverageVerified": False,
            "transformQualified": False, "junctionTraversalVerified": False,
            "endpointConnectorsVerified": False, "physicalQualification": False,
            "productionInputAuthorized": False, "gameInputSent": False}


def list_endpoints(graph):
    """List exact XYZ endpoints and the package IDs that enter or leave them."""
    endpoints = {}
    for edge in graph["edges"]:
        for field, direction in (("startXYZ", "outgoing"), ("endXYZ", "incoming")):
            node = tuple(edge[field])
            item = endpoints.setdefault(node, {"xyz": list(node), "incoming": [], "outgoing": []})
            item[direction].append(edge["routeId"])
    for item in endpoints.values():
        item["incoming"].sort()
        item["outgoing"].sort()
    return [endpoints[key] for key in sorted(endpoints)]


def list_destinations(graph):
    """Group verified catalog labels without conflating requested and snapped XYZ.

    The catalog already enforces one requested coordinate per label/scope.
    A label is eligible for exact-endpoint review planning only if at least
    one scoped package ends exactly at that requested coordinate. A snapped
    alternative is visible but never silently substituted for the destination.
    Route IDs are catalog identifiers, not authenticated in-game place names.
    """
    groups = {}
    for edge in graph["edges"]:
        dest = edge["destinationId"]
        goal = xyz(edge["query"]["requestedGoalXYZ"])
        entry = groups.setdefault(dest, {"destinationId": dest,
                                         "requestedGoalXYZ": list(goal),
                                         "exactGoalRoutes": [], "snappedAlternatives": []})
        require(tuple(entry["requestedGoalXYZ"]) == goal,
                "contradictory destination coordinates")
        if tuple(edge["endXYZ"]) == goal:
            entry["exactGoalRoutes"].append(edge["routeId"])
        else:
            entry["snappedAlternatives"].append(
                {"routeId": edge["routeId"], "snappedGoalXYZ": edge["endXYZ"],
                 "endpointOffset": edge["endpointOffsets"]["goal"]})
    for entry in groups.values():
        entry["exactGoalRoutes"].sort()
        entry["snappedAlternatives"].sort(key=lambda row: row["routeId"])
        entry["exactGoalBound"] = bool(entry["exactGoalRoutes"])
    return [groups[key] for key in sorted(groups)]


def _blocked(graph, blocked_routes):
    """Validate route exclusions even when a destination cannot be bound."""
    known = {edge["routeId"] for edge in graph["edges"]}
    require(isinstance(blocked_routes, (list, tuple)) and len(blocked_routes) <= 64
            and all(isinstance(r, str) and r in known for r in blocked_routes),
            "unknown or invalid blocked review route")
    return set(blocked_routes)


def plan_named_destination(graph, *, start_xyz, destination_id, blocked_routes=()):
    """Resolve a catalog destination and run the existing exact-endpoint search.

    A matching package binds the requested goal, even if that package is
    blocked for this query. The search may reach the same exact goal using
    another scoped directed chain. No goal offset or physical arrival is implied.
    """
    _id(destination_id, "destination ID")
    start = xyz(start_xyz)
    blocked = _blocked(graph, blocked_routes)
    destination = next((row for row in list_destinations(graph)
                        if row["destinationId"] == destination_id), None)
    if destination is None or not destination["exactGoalBound"]:
        result = {k: v for k, v in graph.items() if k != "edges"}
        return {**result, "schema": "taxi.world-review-chain/1",
                "status": "unknown-destination" if destination is None else "unbound-destination",
                "startXYZ": list(start), "goalXYZ": None if destination is None else destination["requestedGoalXYZ"],
                "destinationId": destination_id, "destinationBinding": destination,
                "blockedRoutes": sorted(blocked), "segments": [], "junctions": [],
                "pathLength3D": None}
    result = plan_review_chain(graph, start_xyz=list(start),
                               goal_xyz=destination["requestedGoalXYZ"],
                               blocked_routes=blocked_routes)
    return {**result, "destinationId": destination_id, "destinationBinding": destination}


def plan_review_chain(graph, *, start_xyz, goal_xyz, blocked_routes=()):
    """Shortest directed package chain by actual 3D polyline length.

    Dijkstra avoids assumptions about geometric heuristics and retains
    complete source segments. The caller must supply exact snapped XYZ.
    No interpolation at joins, flattening of flags, or physical inference.
    """
    start, goal = xyz(start_xyz), xyz(goal_xyz)
    edges = graph["edges"]
    blocked = _blocked(graph, blocked_routes)
    endpoints = {tuple(row["xyz"]) for row in list_endpoints(graph)}
    base = {k: v for k, v in graph.items() if k != "edges"}
    base.update(schema="taxi.world-review-chain/1", startXYZ=list(start), goalXYZ=list(goal),
                blockedRoutes=sorted(blocked))
    if start not in endpoints or goal not in endpoints:
        return {**base, "status": "unknown-endpoint", "segments": [], "junctions": [],
                "pathLength3D": None}
    if start == goal:
        return {**base, "status": "same-review-endpoint", "segments": [], "junctions": [],
                "pathLength3D": 0.}
    neighbors = {}
    for edge in sorted(edges, key=lambda e: e["routeId"]):
        if edge["routeId"] not in blocked:
            neighbors.setdefault(tuple(edge["startXYZ"]), []).append(edge)
    costs, parents = {start: 0.}, {}
    queue = [(0., start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != costs[node]:
            continue  # stale longer prefix
        if node == goal:
            segments = []
            while node != start:
                node, edge = parents[node]
                segments.append(edge)
            segments.reverse()
            junctions = [{"xyz": a["endXYZ"], "incomingRoute": a["routeId"],
                          "outgoingRoute": b["routeId"], "exactSourceXYZMatch": True,
                          "traversalVerified": False}
                         for a, b in zip(segments, segments[1:])]
            return {**base, "status": "review-chain-found", "segments": segments,
                    "junctions": junctions, "pathLength3D": cost}
        for edge in neighbors.get(node, ()):
            target = tuple(edge["endXYZ"])
            new = cost + edge["pathLength3D"]
            if new < costs.get(target, math.inf):
                costs[target] = new
                parents[target] = (node, edge)
                heapq.heappush(queue, (new, target))
    return {**base, "status": "no-review-chain", "segments": [], "junctions": [],
            "pathLength3D": None}


def main(argv=None):
    """Offline CLI: list exact endpoints or plan a review chain. No execution."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("catalog", type=Path)
    for flag in ("catalog-sha256", "source-world", "frame-sha256", "patch-id", "build-id"):
        p.add_argument("--" + flag, required=True)
    sub = p.add_subparsers(dest="operation", required=True)
    sub.add_parser("endpoints")
    sub.add_parser("destinations", help="list local destination IDs and exact goal bindings")
    plan = sub.add_parser("plan")
    plan.add_argument("--start-xyz", nargs=3, type=float, required=True)
    goal = plan.add_mutually_exclusive_group(required=True)
    goal.add_argument("--goal-xyz", nargs=3, type=float)
    goal.add_argument("--destination", help="exact catalog destination ID")
    plan.add_argument("--blocked-route", action="append", default=[])
    plan.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    try:
        graph = load_graph(a.catalog, catalog_sha256=a.catalog_sha256,
                           source_world=a.source_world, frame_sha256=a.frame_sha256,
                           patch_id=a.patch_id, build_id=a.build_id)
        if a.operation == "endpoints":
            result = {k: v for k, v in graph.items() if k != "edges"}
            result["endpoints"] = list_endpoints(graph)
            result["status"] = "review-endpoints" if result["endpoints"] else "no-review-endpoints"
        elif a.operation == "destinations":
            result = {k: v for k, v in graph.items() if k != "edges"}
            result["destinations"] = list_destinations(graph)
            result["status"] = "review-destinations" if result["destinations"] else "no-review-destinations"
        elif a.destination is not None:
            result = plan_named_destination(graph, start_xyz=a.start_xyz,
                                            destination_id=a.destination,
                                            blocked_routes=a.blocked_route)
        else:
            result = plan_review_chain(graph, start_xyz=a.start_xyz, goal_xyz=a.goal_xyz,
                                       blocked_routes=a.blocked_route)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if getattr(a, "out", None) is not None:
            with a.out.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
        print(encoded, end="")
        return 0 if result["status"] in ("review-endpoints", "review-destinations", "review-chain-found",
                                         "same-review-endpoint") else 1
    except (TraceError, OSError, ValueError, OverflowError, RecursionError) as exc:
        p.exit(2, f"World review graph refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
