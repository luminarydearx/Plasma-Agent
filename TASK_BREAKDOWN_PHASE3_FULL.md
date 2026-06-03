# Phase 3 Full - Task Breakdown

**Status:** Ready to Start
**Total Tasks:** 31
**Estimated Time:** 23 hours
**Prerequisites:** Phase 3 MVP complete (107/107 tests passing)

---

## Sub-Phase 3.4: Self-Improvement Loop (8 tasks, ~6 hours)

### Task 3.4.1: Create template_metrics table migration
**File:** `migrations/versions/003_add_template_metrics.py`
**Acceptance Criteria:**
- Migration file created dengan proper up/down
- Table `template_metrics` created dengan semua columns
- Indexes pada `template_name`, `updated_at`
- Migration runs successfully

**Test:** Manual alembic upgrade/downgrade test

---

### Task 3.4.2: Create TemplateMetrics model
**File:** `src/plasmaagent/models/template_metrics.py`
**Acceptance Criteria:**
- Pydantic model created
- All fields match database schema
- Type hints lengkap
- No comments

**Test:** Unit test untuk model validation

---

### Task 3.4.3: Implement ExecutionMetricsTracker class
**File:** `src/plasmaagent/services/metrics_tracker.py`
**Acceptance Criteria:**
- Class dengan methods:
  - `track_execution(template_name, success, duration_ms, error_message)`
  - `get_template_stats(template_name) -> dict`
  - `get_all_stats() -> list[dict]`
- Async database operations
- Atomic transactions
- Error handling

**Test:** Unit tests (track, get, edge cases)

---

### Task 3.4.4: Integrate MetricsTracker dengan ExecutionService
**File:** `src/plasmaagent/services/execution_service.py`
**Acceptance Criteria:**
- MetricsTracker dipanggil setelah setiap execution
- Success/failure tracked accurately
- Duration measured
- Error messages captured
- No performance degradation (< 5ms overhead)

**Test:** Integration test (execute task, verify metrics)

---

### Task 3.4.5: Implement Pattern Analyzer
**File:** `src/plasmaagent/services/pattern_analyzer.py`
**Acceptance Criteria:**
- Methods:
  - `analyze_success_patterns(template_name) -> list[Pattern]`
  - `analyze_failure_patterns(template_name) -> list[Pattern]`
  - `generate_insights() -> list[Insight]`
- Query execution_logs untuk patterns
- Identify common error messages
- Generate actionable insights

**Test:** Unit tests dengan mock execution logs

---

### Task 3.4.6: Implement Auto-Adjust Confidence
**File:** `src/plasmaagent/services/confidence_optimizer.py`
**Acceptance Criteria:**
- Method: `optimize_confidence_scores()`
- Calculate success rate per template
- Adjust confidence:
  - Success rate > 90%: confidence += 0.05
  - Success rate < 50%: confidence -= 0.05
  - Clamp antara 0.0 dan 1.0
- Update database

**Test:** Unit tests (high success, low success, edge cases)

---

### Task 3.4.7: Create CLI commands untuk metrics
**File:** `src/plasmaagent/cli/metrics.py`
**Acceptance Criteria:**
- Commands:
  - `plasma metrics show` - Display template metrics table
  - `plasma metrics analyze` - Run pattern analysis
  - `plasma metrics optimize` - Auto-adjust confidence
- Rich output (tables, panels)
- Plasma theme colors
- No comments

**Test:** Manual CLI test dengan real data

---

### Task 3.4.8: Comprehensive testing Sub-Phase 3.4
**Files:** `tests/unit/test_metrics_tracker.py`, `tests/integration/test_metrics_flow.py`
**Acceptance Criteria:**
- Unit tests: 20+ test cases
- Integration tests: 5+ scenarios
- All tests passing
- Edge cases covered:
  - Empty database
  - Single execution
  - Multiple executions
  - All success, all failure, mixed
  - Concurrent tracking

**Test:** `pytest -v tests/unit/test_metrics_tracker.py tests/integration/test_metrics_flow.py`

---

## Sub-Phase 3.5: Advanced Reasoning (10 tasks, ~8 hours)

### Task 3.5.1: Create task_dependencies table migration
**File:** `migrations/versions/004_add_task_dependencies.py`
**Acceptance Criteria:**
- Table `task_dependencies` created
- Foreign keys ke tasks table
- Indexes pada parent_task_id, child_task_id
- Migration runs successfully

**Test:** Manual alembic test

---

### Task 3.5.2: Create task_context table migration
**File:** `migrations/versions/005_add_task_context.py`
**Acceptance Criteria:**
- Table `task_context` created
- JSONB column untuk flexible context storage
- Indexes pada task_id
- Migration runs successfully

**Test:** Manual alembic test

---

### Task 3.5.3: Create TaskDependency dan TaskContext models
**File:** `src/plasmaagent/models/task_dependency.py`, `src/plasmaagent/models/task_context.py`
**Acceptance Criteria:**
- Pydantic models created
- Type hints lengkap
- Validation logic
- No comments

**Test:** Unit tests untuk model validation

---

### Task 3.5.4: Implement TaskDecomposer class
**File:** `src/plasmaagent/services/task_decomposer.py`
**Acceptance Criteria:**
- Method: `decompose(natural_language) -> list[GeneratedTask]`
- Parse complex input dengan multiple actions
- Identify dependencies (e.g., "then", "after", "if")
- Return list dengan proper ordering
- Handle 2-3 level depth

**Test:** Unit tests dengan various complexity levels

---

### Task 3.5.5: Implement ContextManager class
**File:** `src/plasmaagent/services/context_manager.py`
**Acceptance Criteria:**
- Methods:
  - `set_context(task_id, key, value)`
  - `get_context(task_id, key) -> Any`
  - `get_all_context(task_id) -> dict`
  - `clear_context(task_id)`
- Async database operations
- JSONB storage
- Type-safe

**Test:** Unit tests (set, get, clear, edge cases)

---

### Task 3.5.6: Integrate ContextManager dengan ExecutionService
**File:** `src/plasmaagent/services/execution_service.py`
**Acceptance Criteria:**
- Context saved setelah setiap step
- Context available ke next steps
- Context passed ke dependent tasks
- No breaking changes

**Test:** Integration test (execute with context, verify)

---

### Task 3.5.7: Implement ErrorRecovery class
**File:** `src/plasmaagent/services/error_recovery.py`
**Acceptance Criteria:**
- Methods:
  - `analyze_failure(task_id) -> RecoverySuggestion`
  - `suggest_retry_params(task_id) -> dict`
  - `apply_recovery(task_id, suggestion)`
- Analyze error messages
- Suggest fixes (retry, different params, skip)
- Apply recovery actions

**Test:** Unit tests dengan various error types

---

### Task 3.5.8: Implement conditional execution logic
**File:** `src/plasmaagent/services/conditional_executor.py`
**Acceptance Criteria:**
- Method: `execute_with_conditions(task_chain) -> ExecutionResult`
- Support conditions:
  - `on_success`: execute jika previous success
  - `on_failure`: execute jika previous failed
  - `on_exit_code`: execute jika specific exit code
- Evaluate conditions
- Execute atau skip based on condition

**Test:** Unit tests (all condition types)

---

### Task 3.5.9: Create CLI commands untuk advanced reasoning
**File:** `src/plasmaagent/cli/reasoning.py`
**Acceptance Criteria:**
- Commands:
  - `plasma task decompose --input "..."` - Decompose complex task
  - `plasma task run --id <id> --with-context` - Run with context
  - `plasma task recover --id <id>` - Apply recovery suggestions
- Rich output
- Plasma theme
- No comments

**Test:** Manual CLI test

---

### Task 3.5.10: Comprehensive testing Sub-Phase 3.5
**Files:** `tests/unit/test_decomposer.py`, `tests/unit/test_context.py`, `tests/integration/test_reasoning_flow.py`
**Acceptance Criteria:**
- Unit tests: 25+ test cases
- Integration tests: 5+ scenarios
- All tests passing
- Edge cases covered

**Test:** Full pytest suite

---

## Sub-Phase 3.6: Template Evolution (7 tasks, ~5 hours)

### Task 3.6.1: Create learned_templates table migration
**File:** `migrations/versions/006_add_learned_templates.py`
**Acceptance Criteria:**
- Table `learned_templates` created
- Columns untuk pattern, template function, version
- Indexes pada name, is_active
- Migration runs successfully

**Test:** Manual alembic test

---

### Task 3.6.2: Create LearnedTemplate model
**File:** `src/plasmaagent/models/learned_template.py`
**Acceptance Criteria:**
- Pydantic model created
- Validation untuk regex pattern
- Version tracking
- No comments

**Test:** Unit tests

---

### Task 3.6.3: Implement TemplateLearner class
**File:** `src/plasmaagent/services/template_learner.py`
**Acceptance Criteria:**
- Methods:
  - `learn_from_task(task_id) -> LearnedTemplate`
  - `extract_pattern(commands) -> str`
  - `generate_template_function(commands) -> str`
  - `validate_template(template) -> bool`
- Analyze successful user-created tasks
- Extract reusable patterns
- Generate template code
- Validate sebelum save

**Test:** Unit tests dengan mock tasks

---

### Task 3.6.4: Implement TemplateVersioner class
**File:** `src/plasmaagent/services/template_versioner.py`
**Acceptance Criteria:**
- Methods:
  - `create_version(template_id) -> int`
  - `rollback(template_id, version)`
  - `get_version_history(template_id) -> list`
- Increment version number
- Store previous versions
- Rollback functionality

**Test:** Unit tests (create, rollback, history)

---

### Task 3.6.5: Implement TemplateRetirement class
**File:** `src/plasmaagent/services/template_retirement.py`
**Acceptance Criteria:**
- Methods:
  - `identify_low_success_templates() -> list`
  - `retire_template(template_id)`
  - `archive_template(template_id)`
- Query metrics untuk low success rate
- Mark sebagai inactive
- Archive untuk audit trail

**Test:** Unit tests (identify, retire, archive)

---

### Task 3.6.6: Integrate TemplateLearner dengan RuleBasedProvider
**File:** `src/plasmaagent/ai/providers/rule_based.py`
**Acceptance Criteria:**
- Load learned templates dari database
- Include learned templates dalam pattern matching
- Prioritize learned templates dengan high confidence
- No breaking changes

**Test:** Integration test (learn template, verify it matches)

---

### Task 3.6.7: Create CLI commands untuk template evolution
**File:** `src/plasmaagent/cli/templates.py`
**Acceptance Criteria:**
- Commands:
  - `plasma template learn` - Learn from successful tasks
  - `plasma template list` - List all templates
  - `plasma template retire <name>` - Retire low-success template
  - `plasma template rollback <name> <version>` - Rollback
- Rich output
- Plasma theme
- No comments

**Test:** Manual CLI test

---

## Sub-Phase 3.7: Smart Suggestions (6 tasks, ~4 hours)

### Task 3.7.1: Implement NextActionRecommender class
**File:** `src/plasmaagent/services/next_action_recommender.py`
**Acceptance Criteria:**
- Methods:
  - `recommend_next(current_task_id) -> list[Recommendation]`
  - `find_similar_tasks(task_id) -> list[Task]`
  - `predict_user_intent(context) -> str`
- Analyze execution history
- Find patterns
- Generate recommendations

**Test:** Unit tests dengan mock history

---

### Task 3.7.2: Implement AnomalyDetector class
**File:** `src/plasmaagent/services/anomaly_detector.py`
**Acceptance Criteria:**
- Methods:
  - `detect_anomalies(commands) -> list[Anomaly]`
  - `is_dangerous(command) -> bool`
  - `suggest_alternative(command) -> str`
- Detect unusual patterns
- Flag dangerous commands (rm -rf, DROP TABLE)
- Suggest safer alternatives

**Test:** Unit tests (normal, anomalous, dangerous)

---

### Task 3.7.3: Implement PerformanceOptimizer class
**File:** `src/plasmaagent/services/performance_optimizer.py`
**Acceptance Criteria:**
- Methods:
  - `identify_slow_templates() -> list`
  - `suggest_optimizations(template_id) -> list[Optimization]`
  - `apply_optimization(template_id, optimization)`
- Query metrics untuk slow templates
- Analyze commands
- Suggest optimizations (parallel, caching, etc.)

**Test:** Unit tests (identify, suggest, apply)

---

### Task 3.7.4: Integrate suggestions dengan ExecutionService
**File:** `src/plasmaagent/services/execution_service.py`
**Acceptance Criteria:**
- Show next action suggestions setelah task completion
- Detect anomalies sebelum execution
- Show optimization hints untuk slow tasks
- Non-blocking (doesn't slow down execution)

**Test:** Integration test (execute, verify suggestions appear)

---

### Task 3.7.5: Create CLI commands untuk smart suggestions
**File:** `src/plasmaagent/cli/suggestions.py`
**Acceptance Criteria:**
- Commands:
  - `plasma suggest next` - Suggest next task
  - `plasma suggest similar <task-id>` - Find similar tasks
  - `plasma suggest optimize` - Optimize slow templates
- Rich output
- Plasma theme
- No comments

**Test:** Manual CLI test

---

### Task 3.7.6: Comprehensive testing Sub-Phase 3.7
**Files:** `tests/unit/test_recommender.py`, `tests/unit/test_anomaly.py`, `tests/integration/test_suggestions_flow.py`
**Acceptance Criteria:**
- Unit tests: 20+ test cases
- Integration tests: 5+ scenarios
- All tests passing
- Edge cases covered

**Test:** Full pytest suite

---

## Final Integration (1 task, ~1 hour)

### Task 3.8: End-to-end integration testing
**Files:** `tests/integration/test_phase3_full.py`
**Acceptance Criteria:**
- Complete flow test:
  1. Create task dari natural language
  2. Execute task
  3. Metrics tracked
  4. Template learned (jika applicable)
  5. Next action suggested
  6. Anomaly detected (jika applicable)
- All components work together
- No breaking changes
- Performance acceptable

**Test:** `pytest -v tests/integration/test_phase3_full.py`

---

## Summary

| Sub-Phase | Tasks | Time | Status |
|-----------|-------|------|--------|
| 3.4 Self-Improvement | 8 | 6h | Ready |
| 3.5 Advanced Reasoning | 10 | 8h | Ready |
| 3.6 Template Evolution | 7 | 5h | Ready |
| 3.7 Smart Suggestions | 6 | 4h | Ready |
| Final Integration | 1 | 1h | Ready |
| **Total** | **32** | **24h** | **Ready** |

---

## Testing Strategy

Setiap task akan di-test dengan:
1. **Unit tests** - Isolated component testing
2. **Integration tests** - Component interaction testing
3. **Edge case tests** - Error handling, empty inputs, concurrent access
4. **Manual CLI tests** - Real-world usage scenarios
5. **Regression tests** - Ensure no breaking changes

**Rule:** Setiap file di-test satu per satu dengan berbagai kemungkinan error sebelum lanjut ke task berikutnya.

---

## Next Steps

1. ✅ Review PHASE3_FULL_PLAN.md
2. ✅ Review TASK_BREAKDOWN_PHASE3_FULL.md
3. ⏳ Start Task 3.4.1 (template_metrics migration)
4. ⏳ Test setiap task sebelum lanjut
5. ⏳ Iterate based on findings

---

**Status:** Ready to Start
**Author:** PlasmaAgent Architecture Team
**Last Updated:** 2026-06-02
