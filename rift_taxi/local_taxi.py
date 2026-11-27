"""Standalone destination-first Taxi prototype, using local graph pathfinding.

A versioned, authored synthetic graph declares traversable directed edges.
A* selects a route at query time; a blocked edge can be excluded without
changing the map. The existing constrained controller follows the selected
geometry in the ideal synthetic plant. No game input, sibling imports,
network, AI, guessed links, or physical clearance claim. Python 3.11+.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import heapq
import json
import math
from pathlib import Path
import re

from .contracts import (MovementTrace, Point, PoseSample, TraceError,
                        _read_bounded, _strict_json, _number)
from .synthetic_constrained_journey import run_constrained_journey

SCHEMA = "taxi.local-route-graph/1"
MAX_GRAPH_BYTES = 512 * 1024
MAX_NODES, MAX_EDGES = 256, 2048
IDENT = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
FRAME = {"frameId": "synthetic-local-xyz", "axisOrder": ["x", "y", "z"],
         "upAxis": "y", "units": "synthetic-units"}


def require(ok, message):
    if not ok:
        raise TraceError("local taxi: " + message)


def identifier(value, label):
    require(isinstance(value, str) and IDENT.fullmatch(value), "invalid " + label)
    return value


def coordinates(value):
    require(isinstance(value, list) and len(value) == 3, "XYZ must contain three numbers")
    result = tuple(_number(v, "XYZ") for v in value)
    require(all(abs(v) <= 1e6 for v in result), "XYZ exceeds model bounds")
    return result


@dataclass(frozen=True)
class Node:
    id: str
    xyz: tuple[float, float, float]
    kind: str
    region: tuple | None


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    length: float


@dataclass(frozen=True)
class Graph:
    map_id: str
    sha256: str
    nodes: dict[str, Node]
    edges: dict[str, Edge]
    destinations: dict[str, tuple[str, str]]  # destination ID -> (label, node ID)


def decode_graph(raw: bytes) -> Graph:
    """Validate explicit graph connectivity and finite flat model coordinates.

    Each edge is a declared directed straight segment. Missing links are
    never filled in by proximity; the caller owns the authored geometry.
    This first execution adapter supports only synthetic, single-plane maps.
    """
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_GRAPH_BYTES,
            "invalid graph byte count")
    doc = _strict_json(raw, "local route graph")
    require(isinstance(doc, dict) and set(doc) == {
        "schema", "classification", "mapId", "nodes", "edges", "destinations"
    } and doc["schema"] == SCHEMA and doc["classification"] == "SYNTHETIC_MODEL_ONLY",
        "unsupported graph schema or classification")
    map_id = identifier(doc["mapId"], "map ID")
    nodes, edges, destinations = {}, {}, {}
    rows = doc["nodes"]
    require(isinstance(rows, list) and 2 <= len(rows) <= MAX_NODES, "node inventory outside bound")
    plane = None
    seen_xyz = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) in (
            {"id", "xyz", "kind"}, {"id", "xyz", "kind", "region"}), "invalid node fields")
        node_id = identifier(row["id"], "node ID")
        xyz = coordinates(row["xyz"])
        kind = row["kind"]
        require(isinstance(kind, str) and kind in ("guide", "mandatory_passage", "hard_stop"),
                "invalid node kind")
        require(node_id not in nodes and xyz not in seen_xyz, "duplicate node ID or XYZ")
        if plane is None:
            plane = xyz[1]
        require(xyz[1] == plane, "prototype requires one Y plane")
        region = None
        require(("region" in row) == (kind == "mandatory_passage"), "passage region required only for mandatory node")
        if kind == "mandatory_passage":
            bounds = row["region"]
            require(isinstance(bounds, dict) and set(bounds) == {"minXYZ", "maxXYZ"}, "invalid region fields")
            lo, hi = coordinates(bounds["minXYZ"]), coordinates(bounds["maxXYZ"])
            require(all(a < b and a <= v <= b for a, v, b in zip(lo, xyz, hi)),
                    "invalid passage region")
            region = (lo, hi)
        nodes[node_id] = Node(node_id, xyz, kind, region)
        seen_xyz.add(xyz)
    rows = doc["edges"]
    require(isinstance(rows, list) and 1 <= len(rows) <= MAX_EDGES, "edge inventory outside bound")
    pairs = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"id", "from", "to"}, "invalid edge fields")
        edge_id = identifier(row["id"], "edge ID")
        source, target = identifier(row["from"], "edge source"), identifier(row["to"], "edge target")
        require(source in nodes and target in nodes and source != target, "edge endpoint invalid")
        require(edge_id not in edges and (source, target) not in pairs, "duplicate edge ID or directed connection")
        distance = math.dist(nodes[source].xyz, nodes[target].xyz)
        require(distance > 1e-9, "degenerate edge")
        edges[edge_id] = Edge(edge_id, source, target, distance)
        pairs.add((source, target))
    rows = doc["destinations"]
    require(isinstance(rows, list) and 1 <= len(rows) <= MAX_NODES, "destination inventory outside bound")
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"id", "label", "node"}, "invalid destination fields")
        dest = identifier(row["id"], "destination ID")
        node = identifier(row["node"], "destination node")
        label = row["label"]
        require(isinstance(label, str) and 0 < len(label) <= 128 and label == label.strip()
                and label.isprintable(), "invalid destination label")
        require(dest not in destinations and node in nodes, "duplicate or unknown destination")
        destinations[dest] = (label, node)
    return Graph(map_id, hashlib.sha256(raw).hexdigest(), nodes, edges, destinations)


def demo_graph() -> Graph:
    """Small bundled route network with a main corridor and a longer detour.

    The omitted direct entrance-to-bank connection represents an obstacle.
    Both routes are authored synthetic segments, not extracted RIFT geometry.
    The junction before the bank is an explicit required model stop.
    """
    rows = [
        ("entrance", [0, 0, 0], "guide"),
        ("main-west", [4, 0, 0], "guide"),
        ("main-east", [8, 0, 0], "guide"),
        ("north-west", [0, 0, 4], "guide"),
        ("north-east", [8, 0, 4], "guide"),
        ("junction", [12, 0, 0], "hard_stop"),
        ("bank", [16, 0, 0], "guide"),
        ("inn", [12, 0, 4], "guide"),
    ]
    links = [
        ("entrance", "main-west"), ("main-west", "main-east"), ("main-east", "junction"),
        ("entrance", "north-west"), ("north-west", "north-east"), ("north-east", "junction"),
        ("junction", "bank"), ("junction", "inn"),
    ]
    # Reverse connections are explicitly authored here; A* never invents them.
    links += [(b, a) for a, b in links]
    doc = {"schema": SCHEMA, "classification": "SYNTHETIC_MODEL_ONLY",
           "mapId": "taxi-demo", "nodes": [{"id": i, "xyz": xyz, "kind": kind} for i, xyz, kind in rows],
           "edges": [{"id": a + "-to-" + b, "from": a, "to": b} for a, b in links],
           "destinations": [{"id": "bank", "label": "Demo bank", "node": "bank"},
                            {"id": "inn", "label": "Demo inn", "node": "inn"},
                            {"id": "entrance", "label": "Demo entrance", "node": "entrance"}]}
    return decode_graph(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode())


def plan_route(graph: Graph, start: str, destination: str, *, blocked_edges=()):
    """Compute shortest available directed path by A* with a Euclidean heuristic.

    Edge cost is its explicit length, so straight-line distance is a
    consistent lower bound. Stable neighbor/heap ordering breaks equal-cost
    ties reproducibly; no unknown edge, reversal or snap is allowed.
    """
    require(isinstance(start, str) and start in graph.nodes, "unknown start node")
    require(isinstance(destination, str) and destination in graph.destinations, "unknown destination")
    require(isinstance(blocked_edges, (list, tuple)) and len(blocked_edges) <= MAX_EDGES
            and all(isinstance(e, str) and e in graph.edges for e in blocked_edges),
            "unknown or invalid blocked edge")
    blocked = set(blocked_edges)
    label, goal = graph.destinations[destination]
    base = {"schema": "taxi.local-route-plan/1", "classification": "SYNTHETIC_MODEL_ONLY",
            "mapId": graph.map_id, "graphSHA256": graph.sha256, "startNode": start,
            "destinationId": destination, "destinationLabel": label, "destinationNode": goal,
            "blockedEdges": sorted(blocked), "physicalQualification": False,
            "productionInputAuthorized": False, "gameInputSent": False}
    neighbors = {node: [] for node in graph.nodes}
    for edge in sorted(graph.edges.values(), key=lambda e: e.id):
        if edge.id not in blocked:
            neighbors[edge.source].append(edge)
    cost = {start: 0.}
    parent = {}
    def heuristic(node):
        return math.dist(graph.nodes[node].xyz, graph.nodes[goal].xyz)
    queue = [(heuristic(start), 0., start)]
    while queue:
        _, g, node = heapq.heappop(queue)
        if g != cost[node]:
            continue  # stale entry after discovering a shorter prefix
        if node == goal:
            path_nodes, path_edges = [node], []
            while node != start:
                prev, edge = parent[node]
                path_edges.append(edge)
                path_nodes.append(prev)
                node = prev
            path_nodes.reverse()
            path_edges.reverse()
            points = []
            for index, node in enumerate(path_nodes):
                record = graph.nodes[node]
                kind = ("destination" if index == len(path_nodes)-1 else
                        "guide" if index == 0 else record.kind)
                points.append({"name": node, "kind": kind, "xyz": list(record.xyz)})
            return {**base, "status": "already-at-destination" if start == goal else "route-found",
                    "nodes": path_nodes, "edges": path_edges, "points": points, "distance": g}
        for edge in neighbors[node]:
            new = g + edge.length
            if new < cost.get(edge.target, math.inf):
                cost[edge.target] = new
                parent[edge.target] = (node, edge.id)
                heapq.heappush(queue, (new + heuristic(edge.target), new, edge.target))
    return {**base, "status": "no-route", "nodes": [], "edges": [], "points": [], "distance": None}


def run_local_journey(graph: Graph, start: str, destination: str, *, blocked_edges=(),
                      initial_yaw=None, delay_steps=0):
    """Plan then run the existing constrained ideal-model journey to settlement.

    A route's internal hard stops and mandatory regions are preserved. The
    start is an exact named graph node (no unverified position connector).
    A failed controller leg is retained, never relabeled as arrival.
    """
    plan = plan_route(graph, start, destination, blocked_edges=blocked_edges)
    result = {"schema": "taxi.local-journey/1", "classification": "SYNTHETIC_MODEL_ONLY",
              "plan": plan, "status": plan["status"], "journey": None,
              "physicalQualification": False, "productionInputAuthorized": False,
              "gameInputSent": False}
    if plan["status"] != "route-found":
        return result
    points = tuple(Point(p["name"], p["kind"], tuple(p["xyz"])) for p in plan["points"])
    require(sum(p.kind in ("hard_stop", "destination") for p in points) <= 8,
            "selected route exceeds current controller stop budget")
    # RIFT's synthetic heading convention uses atan2(-dx, dz).
    if initial_yaw is None:
        a, b = points[0].xyz, points[1].xyz
        initial_yaw = math.degrees(math.atan2(-(b[0]-a[0]), b[2]-a[2]))
    yaw = _number(initial_yaw, "initial yaw")
    require(abs(yaw) <= 1e6, "initial yaw exceeds model bounds")
    trace_hash = hashlib.sha256(json.dumps(
        {"graphSHA256": graph.sha256, "nodes": plan["nodes"], "edges": plan["edges"],
         "initialYaw": yaw}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    trace = MovementTrace("synthetic", {"generator": "taxi-local-graph/1"}, FRAME.copy(),
                          graph.map_id + ":" + start + ":" + destination,
                          points, .3, 0., 1.,
                          (PoseSample(0., points[0].xyz, yaw),), (), trace_hash, None)
    regions = []
    for index, p in enumerate(points):
        if p.kind == "mandatory_passage":
            lo, hi = graph.nodes[p.name].region
            regions.append({"pointIndex": index, "minXYZ": list(lo), "maxXYZ": list(hi)})
    policy = {"schema": "taxi.synthetic-route-constraints/1", "traceSHA256": trace_hash,
              "maxSampleGapSeconds": .2, "stopDwellSeconds": .3, "stopYTolerance": .1,
              "passageRegions": regions}
    journey = run_constrained_journey(trace, policy, delay_steps=delay_steps)
    return {**result, "status": "model-arrived" if journey["allObligationsObserved"] else "model-blocked",
            "journey": journey}


def main(argv=None):
    """Local-only CLI. Exit 0 success, 1 no route/model blocked, 2 invalid input."""
    parser = argparse.ArgumentParser(prog="rift-taxi-local", description=__doc__)
    parser.add_argument("--map", type=Path, help="local graph JSON; omit for the bundled synthetic demo")
    parser.add_argument("--map-sha256", help="optional exact external graph byte pin")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("destinations", help="list local destinations and valid start nodes")
    for action in ("plan", "journey"):
        command = sub.add_parser(action, help="compute route" if action == "plan" else "plan and run synthetic model")
        command.add_argument("--start", required=True)
        command.add_argument("--destination", required=True)
        command.add_argument("--blocked-edge", action="append", default=[])
        if action == "journey":
            command.add_argument("--initial-yaw", type=float)
            command.add_argument("--delay-steps", type=int, default=0)
        command.add_argument("--out", type=Path, help="exclusive new full JSON report")
    args = parser.parse_args(argv)
    try:
        if args.map is None:
            require(args.map_sha256 is None, "map pin requires an explicit file")
            graph = demo_graph()
        else:
            raw = _read_bounded(args.map, MAX_GRAPH_BYTES, "local graph")
            if args.map_sha256 is not None:
                require(re.fullmatch(r"[0-9a-fA-F]{64}", args.map_sha256)
                        and hashlib.sha256(raw).hexdigest() == args.map_sha256.lower(), "map SHA mismatch")
            graph = decode_graph(raw)
        if args.operation == "destinations":
            print(json.dumps({"mapId": graph.map_id, "classification": "SYNTHETIC_MODEL_ONLY",
                              "destinations": [{"id": i, "label": label, "node": node}
                                               for i, (label, node) in sorted(graph.destinations.items())],
                              "startNodes": sorted(graph.nodes)}, indent=2))
            return 0
        if args.out is not None:
            require(not args.out.exists() and not args.out.is_symlink(), "output already exists")
        if args.operation == "plan":
            result = plan_route(graph, args.start, args.destination, blocked_edges=args.blocked_edge)
        else:
            result = run_local_journey(graph, args.start, args.destination, blocked_edges=args.blocked_edge,
                                       initial_yaw=args.initial_yaw, delay_steps=args.delay_steps)
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write("\n")
        # Show a compact operational result; detailed frame evidence is optional.
        plan = result.get("plan", result)
        print(json.dumps({"status": result["status"], "mapId": graph.map_id,
                          "destination": plan["destinationLabel"], "nodes": plan["nodes"],
                          "edges": plan["edges"], "distance": plan["distance"],
                          "classification": "SYNTHETIC_MODEL_ONLY"}, indent=2, allow_nan=False))
        return 1 if result["status"] in ("no-route", "model-blocked") else 0
    except (TraceError, OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Local Taxi refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
