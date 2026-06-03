import pytest
import threading

from plasmaagent.ai.dag import (
    DependencyGraph,
    GraphNode,
    NodeStatus,
)


class TestDependencyGraphInit:
    def test_init_empty(self):
        graph = DependencyGraph()
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_len_empty(self):
        graph = DependencyGraph()
        assert len(graph) == 0


class TestDependencyGraphAddNode:
    def test_add_node_basic(self):
        graph = DependencyGraph()
        node = graph.add_node("task1", "Task 1")
        assert node.node_id == "task1"
        assert node.name == "Task 1"
        assert node.status == NodeStatus.PENDING
        assert graph.node_count == 1

    def test_add_node_with_metadata(self):
        graph = DependencyGraph()
        metadata = {"priority": "high", "timeout": 300}
        node = graph.add_node("task1", "Task 1", metadata=metadata)
        assert node.metadata == metadata

    def test_add_duplicate_node_raises(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        with pytest.raises(ValueError, match="already exists"):
            graph.add_node("task1", "Task 1 Duplicate")

    def test_add_node_invalid_id_empty(self):
        from pydantic import ValidationError
        graph = DependencyGraph()
        with pytest.raises(ValidationError, match="at least 1 character"):
            graph.add_node("", "Task 1")

    def test_add_node_invalid_id_null_byte(self):
        graph = DependencyGraph()
        with pytest.raises(ValueError, match="null bytes"):
            graph.add_node("task\x001", "Task 1")

    def test_add_node_invalid_id_special_chars(self):
        graph = DependencyGraph()
        with pytest.raises(ValueError, match="must be alphanumeric"):
            graph.add_node("task@1", "Task 1")

    def test_add_node_valid_id_with_underscore(self):
        graph = DependencyGraph()
        node = graph.add_node("task_1", "Task 1")
        assert node.node_id == "task_1"

    def test_add_node_valid_id_with_hyphen(self):
        graph = DependencyGraph()
        node = graph.add_node("task-1", "Task 1")
        assert node.node_id == "task-1"

    def test_add_node_valid_id_with_dot(self):
        graph = DependencyGraph()
        node = graph.add_node("task.1", "Task 1")
        assert node.node_id == "task.1"


class TestDependencyGraphAddEdge:
    def test_add_edge_basic(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        edge = graph.add_edge("task1", "task2")
        assert edge.from_node == "task1"
        assert edge.to_node == "task2"
        assert graph.edge_count == 1

    def test_add_edge_nonexistent_source_raises(self):
        graph = DependencyGraph()
        graph.add_node("task2", "Task 2")
        with pytest.raises(ValueError, match="Source node.*does not exist"):
            graph.add_edge("task1", "task2")

    def test_add_edge_nonexistent_target_raises(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        with pytest.raises(ValueError, match="Target node.*does not exist"):
            graph.add_edge("task1", "task2")

    def test_add_edge_self_loop_raises(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        with pytest.raises(ValueError, match="self-loop"):
            graph.add_edge("task1", "task1")

    def test_add_duplicate_edge_raises(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        with pytest.raises(ValueError, match="already exists"):
            graph.add_edge("task1", "task2")

    def test_add_edge_creates_cycle_raises(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")
        with pytest.raises(ValueError, match="would create a cycle"):
            graph.add_edge("task3", "task1")


class TestDependencyGraphRemoveNode:
    def test_remove_node_existing(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.remove_node("task1") is True
        assert graph.node_count == 0

    def test_remove_node_nonexistent(self):
        graph = DependencyGraph()
        assert graph.remove_node("task1") is False

    def test_remove_node_removes_edges(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        graph.remove_node("task1")
        assert graph.edge_count == 0

    def test_remove_node_updates_adjacency(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")
        graph.remove_node("task2")
        assert "task2" not in graph
        assert graph.get_dependents("task1") == []
        assert graph.get_dependencies("task3") == []


class TestDependencyGraphRemoveEdge:
    def test_remove_edge_existing(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        assert graph.remove_edge("task1", "task2") is True
        assert graph.edge_count == 0

    def test_remove_edge_nonexistent(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        assert graph.remove_edge("task1", "task2") is False


class TestDependencyGraphGetNode:
    def test_get_node_existing(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        node = graph.get_node("task1")
        assert node is not None
        assert node.node_id == "task1"

    def test_get_node_nonexistent(self):
        graph = DependencyGraph()
        assert graph.get_node("task1") is None


class TestDependencyGraphGetAllNodes:
    def test_get_all_nodes_empty(self):
        graph = DependencyGraph()
        assert graph.get_all_nodes() == []

    def test_get_all_nodes_multiple(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        nodes = graph.get_all_nodes()
        assert len(nodes) == 2
        node_ids = [n.node_id for n in nodes]
        assert "task1" in node_ids
        assert "task2" in node_ids


class TestDependencyGraphDependencies:
    def test_get_dependencies_empty(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.get_dependencies("task1") == []

    def test_get_dependencies_single(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        deps = graph.get_dependencies("task2")
        assert deps == ["task1"]

    def test_get_dependencies_multiple(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task3")
        graph.add_edge("task2", "task3")
        deps = graph.get_dependencies("task3")
        assert len(deps) == 2
        assert "task1" in deps
        assert "task2" in deps

    def test_get_dependencies_nonexistent_raises(self):
        graph = DependencyGraph()
        with pytest.raises(ValueError, match="does not exist"):
            graph.get_dependencies("task1")


class TestDependencyGraphDependents:
    def test_get_dependents_empty(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.get_dependents("task1") == []

    def test_get_dependents_single(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        dependents = graph.get_dependents("task1")
        assert dependents == ["task2"]

    def test_get_dependents_multiple(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task1", "task3")
        dependents = graph.get_dependents("task1")
        assert len(dependents) == 2
        assert "task2" in dependents
        assert "task3" in dependents

    def test_get_dependents_nonexistent_raises(self):
        graph = DependencyGraph()
        with pytest.raises(ValueError, match="does not exist"):
            graph.get_dependents("task1")


class TestDependencyGraphReadyNodes:
    def test_get_ready_nodes_empty(self):
        graph = DependencyGraph()
        assert graph.get_ready_nodes() == []

    def test_get_ready_nodes_single_no_deps(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "task1"

    def test_get_ready_nodes_multiple_no_deps(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        ready = graph.get_ready_nodes()
        assert len(ready) == 2

    def test_get_ready_nodes_with_deps_not_satisfied(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "task1"

    def test_get_ready_nodes_with_deps_satisfied(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        graph.mark_node_completed("task1")
        ready = graph.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].node_id == "task2"


class TestDependencyGraphStatusMarking:
    def test_mark_node_running(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.mark_node_running("task1") is True
        node = graph.get_node("task1")
        assert node.status == NodeStatus.RUNNING

    def test_mark_node_completed(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.mark_node_completed("task1") is True
        node = graph.get_node("task1")
        assert node.status == NodeStatus.COMPLETED

    def test_mark_node_failed(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.mark_node_failed("task1") is True
        node = graph.get_node("task1")
        assert node.status == NodeStatus.FAILED

    def test_mark_node_skipped(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert graph.mark_node_skipped("task1") is True
        node = graph.get_node("task1")
        assert node.status == NodeStatus.SKIPPED

    def test_mark_nonexistent_node(self):
        graph = DependencyGraph()
        assert graph.mark_node_completed("task1") is False


class TestDependencyGraphCycleDetection:
    def test_has_cycle_empty_graph(self):
        graph = DependencyGraph()
        assert graph.has_cycle() is False

    def test_has_cycle_no_cycle(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        assert graph.has_cycle() is False

    def test_has_cycle_simple_cycle(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        try:
            graph.add_edge("task2", "task1")
        except ValueError:
            pass
        assert graph.has_cycle() is False

    def test_has_cycle_complex_cycle(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")
        try:
            graph.add_edge("task3", "task1")
        except ValueError:
            pass
        assert graph.has_cycle() is False


class TestDependencyGraphTopologicalSort:
    def test_topological_sort_empty(self):
        graph = DependencyGraph()
        assert graph.topological_sort() == []

    def test_topological_sort_single_node(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        result = graph.topological_sort()
        assert result == ["task1"]

    def test_topological_sort_linear_chain(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task2", "task3")
        result = graph.topological_sort()
        assert result == ["task1", "task2", "task3"]

    def test_topological_sort_parallel_nodes(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        result = graph.topological_sort()
        assert len(result) == 3
        assert set(result) == {"task1", "task2", "task3"}

    def test_topological_sort_diamond(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_node("task4", "Task 4")
        graph.add_edge("task1", "task2")
        graph.add_edge("task1", "task3")
        graph.add_edge("task2", "task4")
        graph.add_edge("task3", "task4")
        result = graph.topological_sort()
        assert result[0] == "task1"
        assert result[-1] == "task4"
        assert set(result[1:3]) == {"task2", "task3"}


class TestDependencyGraphExecutionPlan:
    def test_execution_plan_empty(self):
        graph = DependencyGraph()
        plan = graph.get_execution_plan()
        assert plan.node_count == 0
        assert plan.has_cycles is False

    def test_execution_plan_linear(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        plan = graph.get_execution_plan()
        assert plan.is_valid
        assert plan.node_count == 2
        assert plan.ordered_nodes == ("task1", "task2")
        assert len(plan.parallel_groups) == 2

    def test_execution_plan_parallel(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_edge("task1", "task2")
        graph.add_edge("task1", "task3")
        plan = graph.get_execution_plan()
        assert plan.is_valid
        assert plan.node_count == 3
        assert plan.ordered_nodes[0] == "task1"
        assert len(plan.parallel_groups) == 2
        assert plan.parallel_groups[0] == ("task1",)
        assert set(plan.parallel_groups[1]) == {"task2", "task3"}


class TestDependencyGraphClear:
    def test_clear_empty(self):
        graph = DependencyGraph()
        graph.clear()
        assert graph.node_count == 0

    def test_clear_with_data(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        graph.clear()
        assert graph.node_count == 0
        assert graph.edge_count == 0


class TestDependencyGraphASCII:
    def test_to_ascii_empty(self):
        graph = DependencyGraph()
        ascii_str = graph.to_ascii()
        assert "empty graph" in ascii_str

    def test_to_ascii_single_node(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        ascii_str = graph.to_ascii()
        assert "task1" in ascii_str
        assert "Task 1" in ascii_str

    def test_to_ascii_with_edges(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        ascii_str = graph.to_ascii()
        assert "Depends on" in ascii_str or "Required by" in ascii_str


class TestDependencyGraphMagicMethods:
    def test_contains_existing(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        assert "task1" in graph
        assert "task2" not in graph

    def test_repr(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_edge("task1", "task2")
        repr_str = repr(graph)
        assert "nodes=2" in repr_str
        assert "edges=1" in repr_str


class TestDependencyGraphThreadSafety:
    def test_concurrent_add_nodes(self):
        graph = DependencyGraph()
        errors = []

        def add_node(node_id: str) -> None:
            try:
                graph.add_node(node_id, f"Task {node_id}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_node, args=(f"task{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert graph.node_count == 10

    def test_concurrent_add_edges(self):
        graph = DependencyGraph()
        for i in range(10):
            graph.add_node(f"task{i}", f"Task {i}")

        errors = []

        def add_edge(i: int) -> None:
            try:
                if i < 9:
                    graph.add_edge(f"task{i}", f"task{i+1}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_edge, args=(i,)) for i in range(9)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert graph.edge_count == 9


class TestDependencyGraphEdgeCases:
    def test_complex_graph(self):
        graph = DependencyGraph()
        for i in range(20):
            graph.add_node(f"task{i}", f"Task {i}")

        for i in range(19):
            graph.add_edge(f"task{i}", f"task{i+1}")

        plan = graph.get_execution_plan()
        assert plan.is_valid
        assert plan.node_count == 20

    def test_disconnected_components(self):
        graph = DependencyGraph()
        graph.add_node("task1", "Task 1")
        graph.add_node("task2", "Task 2")
        graph.add_node("task3", "Task 3")
        graph.add_node("task4", "Task 4")
        graph.add_edge("task1", "task2")
        graph.add_edge("task3", "task4")

        plan = graph.get_execution_plan()
        assert plan.is_valid
        assert plan.node_count == 4

    def test_very_long_node_id(self):
        graph = DependencyGraph()
        long_id = "a" * 100
        node = graph.add_node(long_id, "Long ID Task")
        assert node.node_id == long_id

    def test_very_long_node_name(self):
        graph = DependencyGraph()
        long_name = "x" * 200
        node = graph.add_node("task1", long_name)
        assert node.name == long_name
