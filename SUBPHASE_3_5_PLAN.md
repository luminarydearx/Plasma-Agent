# Sub-Phase 3.5: Advanced Reasoning

> Temporary planning document. Will be deleted when sub-phase complete.

## Goal

Make PlasmaAgent reason about complex tasks: decompose them, recover from errors, manage dependencies, execute conditionally, and run steps in parallel when possible.

## Scope (10 Tasks)

### Task 3.5.1 - Task Decomposition Engine
- Parse complex natural language into multi-step workflows
- Auto-detect task boundaries (sequential vs parallel)
- Generate dependency graph from decomposition
- **File:** `src/plasmaagent/ai/reasoning/decomposer.py`
- **Tests:** `tests/unit/test_decomposer.py`

### Task 3.5.2 - Context Manager
- Track execution history per session
- Pass context between sequential tasks (output → input)
- Variable substitution in commands (`${prev_task.output}`)
- **File:** `src/plasmaagent/ai/reasoning/context.py`
- **Tests:** `tests/unit/test_context_manager.py`

### Task 3.5.3 - Error Recovery Suggestions
- Analyze failed step output
- Pattern match known errors (file not found, permission denied, timeout)
- Generate fix suggestions (create dir, chmod, retry)
- **File:** `src/plasmaagent/ai/reasoning/recovery.py`
- **Tests:** `tests/unit/test_error_recovery.py`

### Task 3.5.4 - Dependency Graph Builder (DAG)
- Build directed acyclic graph from task relationships
- Detect cycles (invalid deps)
- Topological sort for execution order
- **File:** `src/plasmaagent/ai/reasoning/dependency_graph.py`
- **Tests:** `tests/unit/test_dependency_graph.py`

### Task 3.5.5 - Conditional Step Execution
- `if`/`else` logic in steps (e.g., "only run if previous step succeeded")
- Expression evaluation (safe, no arbitrary code exec)
- Skip steps based on conditions
- **File:** `src/plasmaagent/ai/reasoning/conditions.py`
- **Tests:** `tests/unit/test_conditions.py`

### Task 3.5.6 - Parallel Step Execution
- Execute independent branches concurrently
- Use `asyncio.gather` with pool limits
- Merge outputs after completion
- **File:** `src/plasmaagent/executor/parallel.py`
- **Tests:** `tests/unit/test_parallel_execution.py`

### Task 3.5.7 - Retry Strategies
- Exponential backoff
- Circuit breaker (fail-fast after N failures)
- Configurable per-step retry policy
- **File:** `src/plasmaagent/ai/reasoning/retry.py`
- **Tests:** `tests/unit/test_retry_strategies.py`

### Task 3.5.8 - Reasoning Service Integration
- Orchestrate all reasoning components
- CLI: `plasma task plan --input "..."`
- Preview decomposition before execution
- **File:** `src/plasmaagent/services/reasoning_service.py`
- **Tests:** `tests/integration/test_reasoning_service.py`

### Task 3.5.9 - Comprehensive Testing
- Cross-phase regression (Phase 1, 2, 3 MVP, 3.4 still work)
- Stress tests (1000 steps, complex DAGs)
- Security (injection in expressions, malicious conditions)
- Edge cases (empty DAG, single step, all-parallel, all-sequential)
- **File:** `tests/integration/test_subphase_3_5_comprehensive.py`

### Task 3.5.10 - Cleanup & Documentation
- Remove planning doc (this file)
- Update ROADMAP.md status
- Update README.md if needed
- Commit with clear message

## Success Criteria

- [ ] All 10 tasks implemented
- [ ] 100+ new tests passing
- [ ] Zero regression in previous phases (214+ tests still green)
- [ ] Edge cases covered (injection, concurrency, empty inputs)
- [ ] This file deleted

## Technical Decisions

1. **No arbitrary code execution** in conditions - use safe expression evaluator (asteval or similar)
2. **Parallel execution pool limit** - max 4 concurrent branches (configurable)
3. **DAG stored in PostgreSQL** - new table `task_dependencies`
4. **Context variables scoped per session** - no cross-session leakage

## Estimated Time

- Tasks 3.5.1-3.5.7: ~6 hours (core implementation)
- Tasks 3.5.8-3.5.9: ~2 hours (integration + testing)
- Task 3.5.10: ~15 min (cleanup)
- **Total:** ~8 hours
