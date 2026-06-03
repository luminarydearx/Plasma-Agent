import pytest
from plasmaagent.ai.decomposer import TaskDecomposer, DecomposedTask, SubTask, ExecutionMode


@pytest.fixture
def decomposer() -> TaskDecomposer:
    return TaskDecomposer()


class TestDecomposerValidation:
    def test_reject_empty_string(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(ValueError):
            decomposer.decompose("")

    def test_reject_whitespace_only(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(ValueError):
            decomposer.decompose("   \n\t  ")

    def test_reject_none(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(TypeError):
            decomposer.decompose(None)  # type: ignore

    def test_reject_non_string(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(TypeError):
            decomposer.decompose(123)  # type: ignore

    def test_reject_null_bytes(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(ValueError):
            decomposer.decompose("backup\x00database")

    def test_reject_too_long_input(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(ValueError):
            decomposer.decompose("x" * 10001)

    def test_accept_max_length_input(self, decomposer: TaskDecomposer) -> None:
        text = "a " * 4990 + "then " + "b " * 5
        assert len(text) <= 10000
        result = decomposer.decompose(text)
        assert isinstance(result, DecomposedTask)


class TestDecomposerSingleTask:
    def test_short_input_single_task(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("hi")
        assert result.is_single_task
        assert len(result.sub_tasks) == 1
        assert result.execution_mode == ExecutionMode.SEQUENTIAL

    def test_simple_task_no_markers(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("backup the postgresql database")
        assert result.is_single_task
        assert result.confidence == 1.0

    def test_single_task_wraps_original(self, decomposer: TaskDecomposer) -> None:
        text = "check disk space on drive C"
        result = decomposer.decompose(text)
        assert result.original_input == text
        assert result.sub_tasks[0].natural_language == text
        assert result.sub_tasks[0].task_id == "t0"
        assert result.sub_tasks[0].depends_on == []
        assert result.sub_tasks[0].parallel_group == 0


class TestDecomposerSequential:
    def test_split_by_then(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("backup the database then notify the admin")
        assert not result.is_single_task
        assert len(result.sub_tasks) == 2
        assert result.sub_tasks[0].natural_language == "backup the database"
        assert result.sub_tasks[1].natural_language == "notify the admin"
        assert result.sub_tasks[1].depends_on == ["t0"]

    def test_split_by_after_that(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("clone the repo after that run the tests")
        assert len(result.sub_tasks) == 2
        assert result.execution_mode in (ExecutionMode.SEQUENTIAL, ExecutionMode.MIXED)

    def test_split_by_next(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("build the project next deploy to staging")
        assert len(result.sub_tasks) == 2

    def test_split_by_kemudian(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("backup database kemudian kirim email")
        assert len(result.sub_tasks) == 2

    def test_split_by_lalu(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("install dependencies lalu run tests")
        assert len(result.sub_tasks) == 2

    def test_three_step_sequential(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose(
            "clone repo then install deps then run tests then deploy"
        )
        assert len(result.sub_tasks) >= 3
        for i in range(1, len(result.sub_tasks)):
            assert result.sub_tasks[i].depends_on == [f"t{i-1}"]

    def test_sequential_mode_detection(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("step one then step two then step three")
        assert result.execution_mode == ExecutionMode.SEQUENTIAL

    def test_dependency_chain_integrity(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("task one then task two then task three then task four")
        assert result.validate_dependencies()
        assert result.detect_cycle() is None

    def test_short_segments_split(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("aa then bb then cc")
        assert len(result.sub_tasks) == 3
        assert result.sub_tasks[0].natural_language == "aa"
        assert result.sub_tasks[1].natural_language == "bb"
        assert result.sub_tasks[2].natural_language == "cc"


class TestDecomposerParallel:
    def test_parallel_marker_preserves_segment(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("first task then simultaneously run tests and build")
        assert len(result.sub_tasks) == 2
        assert "simultaneously" in result.sub_tasks[1].natural_language

    def test_parallel_grouping_after_split(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose(
            "clone repo then simultaneously install deps and run lint"
        )
        assert len(result.sub_tasks) == 2
        assert result.execution_mode in (
            ExecutionMode.SEQUENTIAL,
            ExecutionMode.MIXED,
            ExecutionMode.PARALLEL,
        )

    def test_parallel_marker_removes_dependency(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("backup db then simultaneously run tests")
        assert len(result.sub_tasks) == 2
        assert result.sub_tasks[1].depends_on == []
        assert result.sub_tasks[1].parallel_group == result.sub_tasks[0].parallel_group


class TestDecomposerListFormat:
    def test_numbered_list(self, decomposer: TaskDecomposer) -> None:
        text = "1. Backup database\n2. Run tests\n3. Deploy"
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 3
        assert "Backup database" in result.sub_tasks[0].natural_language

    def test_bullet_list(self, decomposer: TaskDecomposer) -> None:
        text = "- Backup database\n- Run tests\n- Deploy"
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 3

    def test_dash_list(self, decomposer: TaskDecomposer) -> None:
        text = "• Step one\n• Step two"
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 2


class TestDecomposerSentenceBoundary:
    def test_split_by_sentences(self, decomposer: TaskDecomposer) -> None:
        text = "Backup the database. Run the tests. Deploy to production."
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 3

    def test_split_by_semicolons(self, decomposer: TaskDecomposer) -> None:
        text = "Backup database; Run tests; Deploy"
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 3

    def test_split_by_newlines(self, decomposer: TaskDecomposer) -> None:
        text = "Backup database\nRun tests\nDeploy"
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) == 3


class TestDecomposerConfidence:
    def test_confidence_in_range(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("task one then task two then task three")
        assert 0.0 <= result.confidence <= 1.0

    def test_single_task_confidence_one(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("simple task without any markers")
        assert result.confidence == 1.0

    def test_multi_with_sequential_markers_boosts_confidence(self, decomposer: TaskDecomposer) -> None:
        with_seq = decomposer.decompose("backup then notify then deploy")
        with_sentences = decomposer.decompose("Backup database. Run tests. Deploy.")
        assert with_seq.confidence > 0.5
        assert with_sentences.confidence > 0.5

    def test_confidence_bounded_by_one(self, decomposer: TaskDecomposer) -> None:
        text = "aa then bb then cc then dd then ee then ff then gg then hh"
        result = decomposer.decompose(text)
        assert result.confidence <= 1.0


class TestDecomposerEdgeCases:
    def test_case_insensitive_markers(self, decomposer: TaskDecomposer) -> None:
        r1 = decomposer.decompose("backup THEN notify")
        r2 = decomposer.decompose("backup then notify")
        assert len(r1.sub_tasks) == len(r2.sub_tasks)

    def test_unicode_input(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("データベースをバックアップ それから テストを実行")
        assert isinstance(result, DecomposedTask)

    def test_emoji_in_input(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("🚀 deploy to prod then 🎉 celebrate")
        assert len(result.sub_tasks) == 2

    def test_special_chars_preserved(self, decomposer: TaskDecomposer) -> None:
        text = "backup 'my_db' then rm -rf /tmp/*"
        result = decomposer.decompose(text)
        assert "'my_db'" in result.sub_tasks[0].natural_language
        assert "/tmp/*" in result.sub_tasks[1].natural_language

    def test_max_sub_tasks_limit(self, decomposer: TaskDecomposer) -> None:
        text = " then ".join([f"step {i}" for i in range(100)])
        result = decomposer.decompose(text)
        assert len(result.sub_tasks) <= 50

    def test_decomposition_time_recorded(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("simple task")
        assert result.decomposition_time_ms >= 0

    def test_execution_order_groups(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("aa then bb then cc")
        order = result.get_execution_order()
        assert len(order) == 3
        assert order[0] == ["t0"]
        assert order[1] == ["t1"]
        assert order[2] == ["t2"]

    def test_no_cycle_in_sequential(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("aa then bb then cc then dd")
        assert result.detect_cycle() is None

    def test_get_tasks_in_group(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("task one then task two then task three")
        group0 = result.get_tasks_in_group(0)
        assert len(group0) == 1
        assert group0[0].task_id == "t0"

    def test_has_dependencies_property(self, decomposer: TaskDecomposer) -> None:
        single = decomposer.decompose("simple task")
        assert not single.has_dependencies
        multi = decomposer.decompose("task one then task two")
        assert multi.has_dependencies


class TestDecomposerPerformance:
    def test_decomposition_under_100ms(self, decomposer: TaskDecomposer) -> None:
        result = decomposer.decompose("backup then test then deploy")
        assert result.decomposition_time_ms < 100

    def test_long_text_under_200ms(self, decomposer: TaskDecomposer) -> None:
        text = " then ".join([f"step number {i} with some extra text" for i in range(20)])
        result = decomposer.decompose(text)
        assert result.decomposition_time_ms < 200

    def test_repeated_decomposition_stable(self, decomposer: TaskDecomposer) -> None:
        text = "backup then test then deploy"
        r1 = decomposer.decompose(text)
        r2 = decomposer.decompose(text)
        assert len(r1.sub_tasks) == len(r2.sub_tasks)
        assert r1.execution_mode == r2.execution_mode


class TestDecomposerPydanticModels:
    def test_subtask_frozen(self) -> None:
        st = SubTask(task_id="t0", natural_language="test")
        with pytest.raises(Exception):
            st.task_id = "t1"  # type: ignore

    def test_decomposed_task_frozen(self) -> None:
        dt = DecomposedTask(original_input="test", sub_tasks=[])
        with pytest.raises(Exception):
            dt.original_input = "new"  # type: ignore

    def test_subtask_id_length_limit(self) -> None:
        with pytest.raises(Exception):
            SubTask(task_id="x" * 33, natural_language="test")

    def test_subtask_nl_length_limit(self) -> None:
        with pytest.raises(Exception):
            SubTask(task_id="t0", natural_language="x" * 2001)

    def test_confidence_range_validation(self) -> None:
        with pytest.raises(Exception):
            DecomposedTask(original_input="test", confidence=1.5)
        with pytest.raises(Exception):
            DecomposedTask(original_input="test", confidence=-0.1)


class TestDecomposerSecurity:
    def test_sql_injection_safe(self, decomposer: TaskDecomposer) -> None:
        text = "backup db'; DROP TABLE tasks;-- then notify admin"
        result = decomposer.decompose(text)
        assert isinstance(result, DecomposedTask)
        assert len(result.sub_tasks) >= 1

    def test_command_injection_safe(self, decomposer: TaskDecomposer) -> None:
        text = "backup db && rm -rf / then deploy"
        result = decomposer.decompose(text)
        assert isinstance(result, DecomposedTask)

    def test_null_byte_rejection(self, decomposer: TaskDecomposer) -> None:
        with pytest.raises(ValueError):
            decomposer.decompose("test\x00inject")

    def test_very_long_segment_truncated(self, decomposer: TaskDecomposer) -> None:
        text = "step one then " + "x" * 3000 + " then step three"
        result = decomposer.decompose(text)
        for st in result.sub_tasks:
            assert len(st.natural_language) <= 2000
