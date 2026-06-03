from __future__ import annotations

import threading
from collections import deque
from typing import Any

from plasmaagent.ai.dag.models import (
    ExecutionPlan,
    GraphEdge,
    GraphNode,
    NodeStatus,
)


class DependencyGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, set[str]] = {}
        self._reverse_adjacency: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    @property
    def edge_count(self) -> int:
        with self._lock:
            return len(self._edges)

    def add_node(
        self,
        node_id: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        with self._lock:
            if node_id in self._nodes:
                raise ValueError(f"Node '{node_id}' already exists")

            node = GraphNode(
                node_id=node_id,
                name=name,
                status=NodeStatus.PENDING,
                metadata=metadata or {},
            )
            self._nodes[node_id] = node
            self._adjacency[node_id] = set()
            self._reverse_adjacency[node_id] = set()
            return node

    def add_edge(self, from_node: str, to_node: str) -> GraphEdge:
        with self._lock:
            if from_node not in self._nodes:
                raise ValueError(f"Source node '{from_node}' does not exist")
            if to_node not in self._nodes:
                raise ValueError(f"Target node '{to_node}' does not exist")
            if from_node == to_node:
                raise ValueError("Cannot add self-loop edge")

            for edge in self._edges:
                if edge.from_node == from_node and edge.to_node == to_node:
                    raise ValueError(f"Edge from '{from_node}' to '{to_node}' already exists")

            edge = GraphEdge(from_node=from_node, to_node=to_node)
            self._edges.append(edge)
            self._adjacency[from_node].add(to_node)
            self._reverse_adjacency[to_node].add(from_node)

            if self._has_cycle_from(from_node):
                self._edges.pop()
                self._adjacency[from_node].remove(to_node)
                self._reverse_adjacency[to_node].remove(from_node)
                raise ValueError(f"Adding edge from '{from_node}' to '{to_node}' would create a cycle")

            return edge

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False

            self._edges = [e for e in self._edges if e.from_node != node_id and e.to_node != node_id]

            for dependent in self._adjacency.get(node_id, set()):
                self._reverse_adjacency[dependent].discard(node_id)

            for dependency in self._reverse_adjacency.get(node_id, set()):
                self._adjacency[dependency].discard(node_id)

            del self._nodes[node_id]
            del self._adjacency[node_id]
            del self._reverse_adjacency[node_id]
            return True

    def remove_edge(self, from_node: str, to_node: str) -> bool:
        with self._lock:
            original_count = len(self._edges)
            self._edges = [e for e in self._edges if not (e.from_node == from_node and e.to_node == to_node)]

            if len(self._edges) < original_count:
                self._adjacency[from_node].discard(to_node)
                self._reverse_adjacency[to_node].discard(from_node)
                return True
            return False

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._lock:
            return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[GraphNode]:
        with self._lock:
            return list(self._nodes.values())

    def get_all_edges(self) -> list[GraphEdge]:
        with self._lock:
            return list(self._edges)

    def get_dependencies(self, node_id: str) -> list[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node '{node_id}' does not exist")
            return list(self._reverse_adjacency.get(node_id, set()))

    def get_dependents(self, node_id: str) -> list[str]:
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node '{node_id}' does not exist")
            return list(self._adjacency.get(node_id, set()))

    def get_ready_nodes(self) -> list[GraphNode]:
        with self._lock:
            ready = []
            for node_id, node in self._nodes.items():
                if node.status != NodeStatus.PENDING:
                    continue

                dependencies = self._reverse_adjacency.get(node_id, set())
                all_satisfied = all(
                    self._nodes[dep].status == NodeStatus.COMPLETED
                    for dep in dependencies
                )

                if all_satisfied:
                    ready.append(node)

            return ready

    def mark_node_running(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False

            node = self._nodes[node_id]
            self._nodes[node_id] = GraphNode(
                node_id=node.node_id,
                name=node.name,
                status=NodeStatus.RUNNING,
                metadata=node.metadata,
            )
            return True

    def mark_node_completed(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False

            node = self._nodes[node_id]
            self._nodes[node_id] = GraphNode(
                node_id=node.node_id,
                name=node.name,
                status=NodeStatus.COMPLETED,
                metadata=node.metadata,
            )
            return True

    def mark_node_failed(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False

            node = self._nodes[node_id]
            self._nodes[node_id] = GraphNode(
                node_id=node.node_id,
                name=node.name,
                status=NodeStatus.FAILED,
                metadata=node.metadata,
            )
            return True

    def mark_node_skipped(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False

            node = self._nodes[node_id]
            self._nodes[node_id] = GraphNode(
                node_id=node.node_id,
                name=node.name,
                status=NodeStatus.SKIPPED,
                metadata=node.metadata,
            )
            return True

    def has_cycle(self) -> bool:
        with self._lock:
            return self._detect_cycle() is not None

    def _has_cycle_from(self, start_node: str) -> bool:
        visited = set()
        stack = [start_node]

        while stack:
            current = stack.pop()
            if current == start_node and len(visited) > 0:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(self._adjacency.get(current, set()))

        return False

    def _detect_cycle(self) -> list[str] | None:
        visited = set()
        rec_stack = set()
        parent_map = {}

        def dfs(node_id: str) -> list[str] | None:
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in self._adjacency.get(node_id, set()):
                if neighbor not in visited:
                    parent_map[neighbor] = node_id
                    cycle = dfs(neighbor)
                    if cycle is not None:
                        return cycle
                elif neighbor in rec_stack:
                    cycle = [neighbor]
                    current = node_id
                    while current != neighbor:
                        cycle.append(current)
                        current = parent_map.get(current, neighbor)
                    cycle.append(neighbor)
                    return list(reversed(cycle))

            rec_stack.remove(node_id)
            return None

        for node_id in self._nodes:
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle is not None:
                    return cycle

        return None

    def topological_sort(self) -> list[str]:
        with self._lock:
            cycle = self._detect_cycle()
            if cycle is not None:
                raise ValueError(f"Graph contains cycle: {' -> '.join(cycle)}")

            in_degree = {node_id: 0 for node_id in self._nodes}
            for edge in self._edges:
                in_degree[edge.to_node] += 1

            queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
            result = []

            while queue:
                node_id = queue.popleft()
                result.append(node_id)

                for dependent in self._adjacency.get(node_id, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            if len(result) != len(self._nodes):
                raise ValueError("Graph contains cycle (topological sort incomplete)")

            return result

    def get_execution_plan(self) -> ExecutionPlan:
        with self._lock:
            cycle = self._detect_cycle()
            if cycle is not None:
                return ExecutionPlan(
                    ordered_nodes=(),
                    parallel_groups=(),
                    has_cycles=True,
                    cycle_nodes=tuple(cycle),
                )

            try:
                ordered = self.topological_sort()
            except ValueError:
                return ExecutionPlan(
                    ordered_nodes=(),
                    parallel_groups=(),
                    has_cycles=True,
                    cycle_nodes=(),
                )

            levels: list[list[str]] = []
            in_degree = {node_id: 0 for node_id in self._nodes}
            for edge in self._edges:
                in_degree[edge.to_node] += 1

            queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

            while queue:
                current_level = []
                next_queue = deque()

                while queue:
                    node_id = queue.popleft()
                    current_level.append(node_id)

                    for dependent in self._adjacency.get(node_id, set()):
                        in_degree[dependent] -= 1
                        if in_degree[dependent] == 0:
                            next_queue.append(dependent)

                levels.append(current_level)
                queue = next_queue

            parallel_groups = tuple(tuple(level) for level in levels)

            return ExecutionPlan(
                ordered_nodes=tuple(ordered),
                parallel_groups=parallel_groups,
                has_cycles=False,
                cycle_nodes=(),
            )

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._adjacency.clear()
            self._reverse_adjacency.clear()

    def to_ascii(self) -> str:
        with self._lock:
            if not self._nodes:
                return "(empty graph)"

            lines = []
            lines.append("Dependency Graph:")
            lines.append("=" * 60)

            for node_id, node in self._nodes.items():
                status_icon = {
                    NodeStatus.PENDING: "⏳",
                    NodeStatus.RUNNING: "🔄",
                    NodeStatus.COMPLETED: "✅",
                    NodeStatus.FAILED: "❌",
                    NodeStatus.SKIPPED: "⏭️",
                }.get(node.status, "?")

                lines.append(f"{status_icon} {node_id}: {node.name}")

                dependencies = self._reverse_adjacency.get(node_id, set())
                if dependencies:
                    lines.append(f"   Depends on: {', '.join(sorted(dependencies))}")

                dependents = self._adjacency.get(node_id, set())
                if dependents:
                    lines.append(f"   Required by: {', '.join(sorted(dependents))}")

            lines.append("=" * 60)

            if self.has_cycle():
                lines.append("⚠️  WARNING: Graph contains cycles!")
            else:
                lines.append("✓ Graph is valid (no cycles)")

            return "\n".join(lines)

    def __len__(self) -> int:
        return self.node_count

    def __contains__(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    def __repr__(self) -> str:
        return f"DependencyGraph(nodes={self.node_count}, edges={self.edge_count})"
