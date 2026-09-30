"""Deterministic layered layout for directed use-case dependency graphs."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def dependency_layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(node["use_case_id"]) for node in nodes]
    known = set(ids)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in edges:
        source, target = str(edge.get("from_use_case", "")), str(edge.get("to_use_case", ""))
        if source in known and target in known and target not in adjacency[source]:
            adjacency[source].append(target)

    # Tarjan SCC: cycles remain visible, but are explicitly marked for review.
    index = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node_id: str) -> None:
        nonlocal index
        indices[node_id] = lowlink[node_id] = index
        index += 1
        stack.append(node_id)
        on_stack.add(node_id)
        for target in adjacency[node_id]:
            if target not in indices:
                visit(target)
                lowlink[node_id] = min(lowlink[node_id], lowlink[target])
            elif target in on_stack:
                lowlink[node_id] = min(lowlink[node_id], indices[target])
        if lowlink[node_id] == indices[node_id]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node_id:
                    break
            components.append(component)

    for node_id in ids:
        if node_id not in indices:
            visit(node_id)

    cyclic_components = [component for component in components if len(component) > 1 or component[0] in adjacency[component[0]]]
    component_of = {node_id: i for i, component in enumerate(components) for node_id in component}
    dag: dict[int, set[int]] = {i: set() for i in range(len(components))}
    indegree = {i: 0 for i in range(len(components))}
    for source, targets in adjacency.items():
        source_component = component_of[source]
        for target in targets:
            target_component = component_of[target]
            if source_component != target_component and target_component not in dag[source_component]:
                dag[source_component].add(target_component)
                indegree[target_component] += 1
    ready = deque(sorted((component for component, degree in indegree.items() if degree == 0), key=lambda i: min(ids.index(x) for x in components[i])))
    rank = {component: 0 for component in dag}
    while ready:
        source = ready.popleft()
        for target in sorted(dag[source], key=lambda i: min(ids.index(x) for x in components[i])):
            rank[target] = max(rank[target], rank[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)

    layers: dict[int, list[str]] = defaultdict(list)
    original_order = {node_id: i for i, node_id in enumerate(ids)}
    for node_id in ids:
        layers[rank[component_of[node_id]]].append(node_id)
    for nodes_in_layer in layers.values():
        nodes_in_layer.sort(key=lambda node_id: original_order[node_id])

    # A few stable barycentric sweeps reduce edge crossings without an external
    # graph-layout dependency.
    positions = {node_id: i for group in layers.values() for i, node_id in enumerate(group)}
    for layer_index in range(1, max(layers, default=0) + 1):
        incoming = defaultdict(list)
        for source, targets in adjacency.items():
            for target in targets:
                if rank[component_of[target]] == layer_index and rank[component_of[source]] < layer_index:
                    incoming[target].append(positions.get(source, 0))
        layers[layer_index].sort(key=lambda node_id: (sum(incoming[node_id]) / len(incoming[node_id]) if incoming[node_id] else positions[node_id], original_order[node_id]))
        positions.update({node_id: i for i, node_id in enumerate(layers[layer_index])})

    # Assign vertical slots, then move intermediate nodes that a direct
    # left-to-right dependency line would pass through.
    row_positions = {node_id: row for group in layers.values() for row, node_id in enumerate(group)}

    def conflicts(positions: dict[str, int]) -> list[tuple[str, str, str]]:
        found = []
        for edge in edges:
            source, target = str(edge.get("from_use_case", "")), str(edge.get("to_use_case", ""))
            if source not in known or target not in known:
                continue
            source_layer, target_layer = rank[component_of[source]], rank[component_of[target]]
            if target_layer - source_layer <= 1:
                continue
            y1, y2 = positions[source], positions[target]
            for middle_layer in range(source_layer + 1, target_layer):
                ratio = (middle_layer - source_layer) / (target_layer - source_layer)
                line_y = y1 + ratio * (y2 - y1)
                for obstacle in layers[middle_layer]:
                    if abs(positions[obstacle] - line_y) < 0.8:
                        found.append((source, target, obstacle))
        return found

    original_rows = dict(row_positions)
    for _ in range(max(1, len(ids) * 3)):
        current_conflicts = conflicts(row_positions)
        if not current_conflicts:
            break
        candidates = []
        for node_id in dict.fromkeys(item[2] for item in current_conflicts):
            node_layer = rank[component_of[node_id]]
            occupied = {row_positions[other] for other in layers[node_layer] if other != node_id}
            max_row = max(row_positions.values(), default=0)
            for row in range(max_row + len(ids) + 2):
                if row in occupied or row == row_positions[node_id]:
                    continue
                trial = dict(row_positions)
                trial[node_id] = row
                candidates.append((len(conflicts(trial)), abs(row-original_rows[node_id]), row, original_order[node_id], node_id))
        if not candidates:
            break
        best = min(candidates)
        if best[0] >= len(current_conflicts):
            break
        row_positions[best[4]] = best[2]

    cycle_node_sets = [set(component) for component in cyclic_components]
    cycle_edge_ids = {
        str(edge.get("edge_id", ""))
        for edge in edges
        if any(str(edge.get("from_use_case", "")) in component and str(edge.get("to_use_case", "")) in component for component in cycle_node_sets)
    }
    return {
        "layers": [layers[index] for index in sorted(layers)],
        "row_positions": row_positions,
        "direct_edge_conflicts": [list(item) for item in conflicts(row_positions)],
        "cycles": [sorted(component, key=original_order.get) for component in cyclic_components],
        "cycle_edge_ids": sorted(cycle_edge_ids),
    }
