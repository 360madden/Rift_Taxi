"""Build a locally searchable directed graph from pinned RiftWorld path exports.

This is the first real source-geometry adapter for Taxi's local A* planner.
Read only existing, explicitly pinned catalog packages. Preserve source XYZ
(including height) and point order; never flatten the map, manufacture a
connector, reverse an edge, or import a sibling application. Exact shared
endpoints within one world/frame/patch/navigation-build scope can join the
candidate network for offline review. A route is not a collision certificate
or a live movement authorization. Python 3.11+, standard library only.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path

from .contracts import TraceError, _number
from .local_taxi import Graph, Node, Edge, MAX_EDGES, coordinates, plan_route
from .world_candidate_review import content_id, require, xyz
from .world_route_catalog import _catalog, open_catalog_package, scoped_packages

CLASSIFICATION = "OFFLINE_REVIEW_ONLY"


@dataclass(frozen=True)
class WorldGraph:
    """A graph plus exact source identities and alias-to-node mapping.

    Route IDs are convenient destination keys; labels retain the catalog's
    destination ID. Multiple variants of a goal with different snaps remain
    separately selectable, rather than inventing a shared connector.
    """
    graph: Graph
    scope: dict
    aliases: dict
    routes: dict
    edge_sources: dict


def load_world_graph(catalog, *, catalog_sha256, anchor_route):
    """Build the connected review graph for one explicit catalog route scope.

    Anchor selection avoids asking a user to manually retype frame/build
    hashes. All matching packages are verified before use. A different
    navigation build is excluded, even if its XYZ values look similar.
    Only ordinary START/interior/END sequences are supported in this slice;
    unknown/off-mesh flags are refused rather than silently followed.
    """
    root, rows = _catalog(catalog, catalog_sha256)
    anchor = next((row for row in rows if row["routeId"] == anchor_route), None)
    require(anchor is not None, "unknown anchor route")
    first = open_catalog_package(root, anchor)
    scope = {k: anchor[k] for k in ("sourceWorld", "frameSHA256", "patchId")}
    scope["buildId"] = first["buildId"]
    # Same source-world name is insufficient: retain and compare the full
    # source world metadata before joining any independently exported paths.
    scope["worldMetadataSHA256"] = content_id(first["world"])
    scope["coordinates"] = first["coordinates"]
    scope["catalogSHA256"] = catalog_sha256
    nodes, edges, destinations, aliases, routes, sources = {}, {}, {}, {}, {}, {}
    # Endpoint sharing is exact-coordinate only and within this same scope.
    # Interior vertices stay route-local, even at coincident coordinates:
    # intersecting lines are not independently established transitions.
    endpoints = {}
    admitted, _, identity = scoped_packages(
        root, rows, source_world=scope["sourceWorld"], frame_sha256=scope["frameSHA256"],
        patch_id=scope["patchId"], build_id=scope["buildId"])
    require(identity == scope["worldMetadataSHA256"], "anchor world metadata mismatch")
    for row, review in admitted:
        points = review["points"]
        route = row["routeId"]
        require(len(edges) + len(points) - 1 <= MAX_EDGES, "review graph edge bound exceeded")
        chain = []
        for index, point in enumerate(points):
            last = index == len(points) - 1
            # Detour straight-path START/END flags are retained; other
            # flags may require separate traversal handling. No guesswork.
            require(point["flags"] == (1 if index == 0 else 2 if last else 0),
                    "unsupported path flags in " + route)
            position = xyz(point["xyz"])
            alias = f"{route}:{index}"
            if index == 0 or last:
                node_id = endpoints.setdefault(position, alias)
            else:
                node_id = alias
            if node_id not in nodes:
                nodes[node_id] = Node(node_id, position, "guide", None)
            aliases[alias] = node_id
            chain.append(node_id)
            if index == 0:
                continue
            previous = chain[index - 1]
            length = math.dist(nodes[previous].xyz, position)
            require(previous != node_id and length > 0., "zero-length candidate segment")
            edge_id = f"{route}:edge:{index-1}"
            edges[edge_id] = Edge(edge_id, previous, node_id, length)
            sources[edge_id] = {
                "routeId": route, "packageId": row["packageId"],
                "candidateId": review["candidateId"],
                "fromPointId": points[index-1]["id"], "toPointId": point["id"],
                "fromFlags": points[index-1]["flags"], "toFlags": point["flags"],
            }
        destinations[route] = (row["destinationId"], chain[-1])
        routes[route] = {
            "destinationId": row["destinationId"], "startNode": f"{route}:0",
            "goalNode": f"{route}:{len(points)-1}", "pointCount": len(points),
            "packageId": row["packageId"], "candidateId": review["candidateId"],
            "source": review["source"], "query": review["query"],
            "endpointOffsets": review["endpointOffsets"], "sourceEvidence": review["sourceEvidence"],
        }
    # Stable semantic ID covers the catalog, chosen build, exact admitted
    # source packages and the construction rule. No raw asset is copied.
    graph_sha = content_id({"schema": "taxi.world-review-graph/1", "scope": scope,
                            "packageIds": [routes[key]["packageId"] for key in sorted(routes)],
                            "joinRule": "exact-shared-endpoints-only"})
    graph = Graph("world-review-" + graph_sha[:16], graph_sha, nodes, edges,
                  destinations, CLASSIFICATION)
    return WorldGraph(graph, scope, aliases, routes, sources)


def describe_world_graph(world):
    """Expose selectable source-coordinate points and destination labels."""
    return {"schema": "taxi.world-review-graph/1", "classification": CLASSIFICATION,
            "graphSHA256": world.graph.sha256, "scope": world.scope,
            "destinations": [{"routeId": key, **row} for key, row in sorted(world.routes.items())],
            "startNodes": [{"id": alias, "xyz": list(world.graph.nodes[node].xyz)}
                           for alias, node in sorted(world.aliases.items())],
            "physicalQualification": False, "productionInputAuthorized": False,
            "gameInputSent": False}


def plan_world_route(world, *, destination, start=None, start_xyz=None, blocked_edges=()):
    """Find a route from an explicit graph point, not a guessed start snap.

    An exact XYZ match is useful for a source-coordinate selection, but
    multiple distinct same-XYZ nodes are ambiguous. The caller must select
    the intended node. Return exact requested/snapped goal differences and
    source edge bindings along with the local A* result.
    """
    require((start is None) != (start_xyz is None), "choose one start node or exact XYZ")
    if start is not None:
        require(isinstance(start, str) and start in world.aliases, "unknown start alias")
        node = world.aliases[start]
    else:
        position = coordinates(start_xyz)
        matches = [key for key, row in world.graph.nodes.items() if row.xyz == position]
        require(len(matches) == 1, "start XYZ absent or ambiguous; select an explicit node")
        node = matches[0]
    result = plan_route(world.graph, node, destination, blocked_edges=blocked_edges)
    return {**result, "scope": world.scope, "requestedStartAlias": start,
            "destinationSource": world.routes[destination],
            "edgeSources": [world.edge_sources[key] for key in result["edges"]],
            "endpointConnectorsVerified": False, "transformQualified": False,
            "corridorClearanceVerified": False}


def review_position(world, *, position, max_xz, max_y, limit=12):
    """Inspect nearby vertices and directed segments in source coordinates.

    This is a geometric review of a caller-supplied XYZ, not localization,
    collision clearance, an execution start, or a connector. Each edge uses
    the clamped closest point in full 3D; horizontal/vertical thresholds are
    applied to that particular projection, not a swept corridor. Distinct
    overlapping edges and vertices remain separate candidates.
    """
    require(world.graph.classification == CLASSIFICATION, "review graph required")
    query = coordinates(position)
    h, v = _number(max_xz, "max XZ"), _number(max_y, "max Y")
    require(0 <= h <= 100 and 0 <= v <= 100, "position review limits must be 0..100")
    require(type(limit) is int and 1 <= limit <= 64, "candidate limit must be 1..64")

    def distances(point):
        dxz = math.hypot(query[0]-point[0], query[2]-point[2])
        dy = abs(query[1]-point[1])
        return dxz, dy, math.hypot(dxz, dy)

    vertices, segments = [], []
    aliases = {}
    for alias, node_id in sorted(world.aliases.items()):
        aliases.setdefault(node_id, []).append(alias)
    exact = []
    for node in world.graph.nodes.values():
        dxz, dy, d = distances(node.xyz)
        if query == node.xyz:
            exact.append(node.id)
        if dxz <= h and dy <= v:
            vertices.append({"nodeId": node.id, "aliases": aliases[node.id],
                             "xyz": list(node.xyz), "distanceXZ": dxz,
                             "distanceY": dy, "distance3D": d})
    for edge in world.graph.edges.values():
        a, b = world.graph.nodes[edge.source].xyz, world.graph.nodes[edge.target].xyz
        delta = tuple(y-x for x,y in zip(a,b))
        # Use the already validated nonzero edge length for a stable unit
        # direction. Retain exact endpoints when the projection clamps.
        unit = tuple(x/edge.length for x in delta)
        along = math.fsum((q-x)*u for q,x,u in zip(query,a,unit))
        t = max(0., min(1., along/edge.length))
        projection = a if t == 0 else b if t == 1 else tuple(
            x+t*d for x,d in zip(a,delta))
        dxz, dy, d = distances(projection)
        if dxz <= h and dy <= v:
            segments.append({"edgeId":edge.id, "fromNode":edge.source,
                             "toNode":edge.target, "fraction":t,
                             "projectedXYZ":list(projection), "distanceXZ":dxz,
                             "distanceY":dy,"distance3D":d,
                             "edgeSource":world.edge_sources[edge.id]})
    vertices.sort(key=lambda row:(row["distance3D"],row["nodeId"]))
    segments.sort(key=lambda row:(row["distance3D"],row["edgeId"]))
    return {"schema":"taxi.world-position-review/1", "classification":CLASSIFICATION,
            "graphSHA256":world.graph.sha256, "scope":world.scope,
            "queryXYZ":list(query), "limits":{"xz":h,"y":v,"perKind":limit},
            "exactNodeIds":sorted(exact), "vertexCount":len(vertices),
            "segmentCount":len(segments), "vertices":vertices[:limit],
            "segments":segments[:limit], "status":"review-candidates" if vertices or segments else "no-candidates",
            "automaticStartBinding":False, "transformQualified":False,
            "endpointConnectorsVerified":False,"physicalQualification":False,
            "productionInputAuthorized":False,"gameInputSent":False}


def main(argv=None):
    """List a local imported map or plan a route, without connecting to RIFT."""
    p = argparse.ArgumentParser(prog="rift-taxi-world", description=__doc__)
    p.add_argument("catalog", type=Path)
    p.add_argument("--catalog-sha256", required=True)
    p.add_argument("--anchor-route", required=True, help="catalog route selecting one map/build scope")
    sub = p.add_subparsers(dest="operation", required=True)
    sub.add_parser("destinations")
    locate = sub.add_parser("locate", help="review nearby source geometry without snapping")
    locate.add_argument("--xyz", nargs=3, type=float, required=True)
    locate.add_argument("--max-xz", type=float, required=True)
    locate.add_argument("--max-y", type=float, required=True)
    locate.add_argument("--limit", type=int, default=12)
    locate.add_argument("--out", type=Path)
    route = sub.add_parser("plan")
    route.add_argument("--destination", required=True, help="route ID from destinations")
    source = route.add_mutually_exclusive_group(required=True)
    source.add_argument("--start", help="exact point alias, e.g. accepted:0")
    source.add_argument("--start-xyz", nargs=3, type=float)
    route.add_argument("--blocked-edge", action="append", default=[])
    route.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    try:
        world = load_world_graph(args.catalog, catalog_sha256=args.catalog_sha256,
                                 anchor_route=args.anchor_route)
        if args.operation == "destinations":
            result = describe_world_graph(world)
        elif args.operation == "locate":
            result = review_position(world, position=args.xyz, max_xz=args.max_xz,
                                     max_y=args.max_y, limit=args.limit)
        else:
            result = plan_world_route(world, destination=args.destination, start=args.start,
                                      start_xyz=args.start_xyz, blocked_edges=args.blocked_edge)
        if getattr(args, "out", None) is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write("\n")
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result.get("status") in ("no-route", "no-candidates") else 0
    except (TraceError, OSError, ValueError, OverflowError, RecursionError) as exc:
        p.exit(2, f"World Taxi planning refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
