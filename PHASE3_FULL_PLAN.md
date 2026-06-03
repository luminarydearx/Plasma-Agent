# Phase 3 Full - Intelligence Engine (Advanced)

**Status:** Planning
**Start Date:** 2026-06-02
**Estimated Duration:** 23 hours (~31 tasks)
**Prerequisites:** Phase 3 MVP complete (107/107 tests passing)

---

## Executive Summary

Phase 3 Full builds upon the MVP by adding:
- Self-improvement loop (learn dari execution history)
- Advanced reasoning (task decomposition, context-aware)
- Template evolution (auto-generate new templates)
- Smart suggestions (next action recommendations)

All tetap mengikuti constraint:
- ❌ No Ollama/local LLM storage
- ✅ Rule-based first, LLM-ready architecture
- ✅ Database-centric (all state di PostgreSQL)
- ✅ No Docker, no Redis, no filesystem
- ✅ No comments in code (permanen)
- ✅ No frontend

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Intelligence Layer                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │
│  │ TaskGenerator   │  │ TemplateOptimizer│  │ Suggestion │  │
│  │ (existing MVP)  │  │ (NEW 3.6)       │  │ Engine     │  │
│  │                 │  │                 │  │ (NEW 3.7)  │  │
│  └────────┬────────┘  └────────┬────────┘  └─────┬──────┘  │
│           │                    │                  │         │
│           ▼                    ▼                  ▼         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            MetricsTracker (NEW 3.4)                   │  │
│  │  - Track execution success/failure                    │  │
│  │  - Analyze patterns                                   │  │
│  │  - Generate insights                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│           │                                                 │
│           ▼                                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            ReasoningEngine (NEW 3.5)                  │  │
│  │  - Task decomposition                                 │  │
│  │  - Context-aware execution                            │  │
│  │  - Error recovery suggestions                         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (existing)                  │
│  - telemetry table (extend with metrics)                    │
│  - task_templates (NEW: learned templates)                  │
│  - execution_history (extend with patterns)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Sub-Phase Breakdown

### Sub-Phase 3.4: Self-Improvement Loop (~6 hours, 8 tasks)

**Goal:** Track execution metrics dan learn dari patterns.

**Components:**
1. ExecutionMetricsTracker
   - Track success/failure per template
   - Calculate success rates
   - Track average duration
   - Identify failure patterns

2. Pattern Analyzer
   - Extract patterns dari successful executions
   - Identify common failure modes
   - Generate insights

3. Auto-Adjust Confidence
   - Update template confidence based on success rate
   - Lower confidence untuk templates dengan high failure
   - Boost confidence untuk reliable templates

**Database Changes:**
```sql
CREATE TABLE template_metrics (
    id UUID PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    avg_duration_ms INTEGER,
    last_used TIMESTAMP,
    confidence_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE execution_patterns (
    id UUID PRIMARY KEY,
    template_name VARCHAR(100),
    pattern_type VARCHAR(50),
    pattern_data JSONB,
    frequency INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**CLI Commands:**
```bash
plasma metrics show                  # Show template metrics
plasma metrics analyze               # Analyze patterns
plasma metrics optimize              # Auto-adjust confidence
```

---

### Sub-Phase 3.5: Advanced Reasoning (~8 hours, 10 tasks)

**Goal:** Decompose complex tasks dan context-aware execution.

**Components:**
1. Task Decomposer
   - Parse complex natural language
   - Break into sub-tasks
   - Identify dependencies

2. Context Manager
   - Track previous task results
   - Pass context ke next task
   - Conditional execution based on context

3. Error Recovery
   - Analyze failed executions
   - Suggest recovery actions
   - Auto-retry dengan different parameters

**Example:**
```bash
# User input:
"backup database, then upload to S3, then notify admin"

# Decomposed:
Task 1: Backup database (postgresql plasmaagent)
Task 2: Upload backup to S3 (depends on Task 1 success)
Task 3: Send notification (depends on Task 2 success)
```

**Database Changes:**
```sql
CREATE TABLE task_dependencies (
    id UUID PRIMARY KEY,
    parent_task_id UUID REFERENCES tasks(id),
    child_task_id UUID REFERENCES tasks(id),
    dependency_type VARCHAR(50),
    condition JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE task_context (
    id UUID PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    context_key VARCHAR(100),
    context_value JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**CLI Commands:**
```bash
plasma task decompose --input "complex task"  # Decompose into sub-tasks
plasma task run --id <id> --with-context      # Run with context from previous task
```

---

### Sub-Phase 3.6: Template Evolution (~5 hours, 7 tasks)

**Goal:** Learn dari user-created tasks dan auto-generate new templates.

**Components:**
1. Template Learner
   - Analyze successful user-created tasks
   - Extract patterns
   - Generate new templates

2. Template Versioning
   - Track template versions
   - A/B test different versions
   - Rollback ke previous version

3. Template Retirement
   - Identify low-success templates
   - Auto-retire atau suggest improvements
   - Archive old templates

**Database Changes:**
```sql
CREATE TABLE learned_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    pattern_regex TEXT NOT NULL,
    template_function TEXT NOT NULL,
    confidence DECIMAL(3,2),
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    source_task_id UUID REFERENCES tasks(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**CLI Commands:**
```bash
plasma template learn                # Learn from successful tasks
plasma template list                 # List all templates (built-in + learned)
plasma template retire <name>        # Retire low-success template
plasma template rollback <name> <v>  # Rollback to previous version
```

---

### Sub-Phase 3.7: Smart Suggestions (~4 hours, 6 tasks)

**Goal:** Provide intelligent recommendations dan next action suggestions.

**Components:**
1. Next Action Recommender
   - Suggest next task based on current context
   - Recommend similar tasks
   - Predict user intent

2. Anomaly Detector
   - Detect unusual commands
   - Warn about potential issues
   - Suggest safer alternatives

3. Performance Optimizer
   - Identify slow templates
   - Suggest optimizations
   - Auto-optimize commands

**Example:**
```bash
# After successful backup:
"✓ Backup completed. Suggested next: upload to cloud storage"

# Unusual command detected:
"⚠ Warning: This command will delete all files. Are you sure?"
```

**CLI Commands:**
```bash
plasma suggest next                  # Suggest next task
plasma suggest similar <task-id>     # Find similar tasks
plasma suggest optimize              # Optimize slow templates
```

---

## Technical Decisions

### Decision 1: Metrics Storage
**Choice:** Separate table (`template_metrics`) instead of extending `telemetry`
**Rationale:**
- Cleaner separation of concerns
- Easier queries untuk metrics aggregation
- Better performance untuk analytics

### Decision 2: Template Learning
**Choice:** Rule-based pattern extraction, not ML
**Rationale:**
- Zero storage overhead (no model files)
- Deterministic (same input = same output)
- Faster (< 10ms)
- Easier to debug

### Decision 3: Context Management
**Choice:** Store context in database, not in-memory
**Rationale:**
- Survives crashes
- Can be audited
- Can be shared across tasks
- Follows database-centric architecture

### Decision 4: Template Versioning
**Choice:** Simple integer versioning
**Rationale:**
- Simple to implement
- Easy to rollback
- No need untuk complex semver

---

## Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Template learning generates bad templates | Medium | High | Validation step, human approval option |
| Context management complex | Medium | Medium | Start simple, iterate |
| Metrics storage grows too large | Low | Medium | Retention policy, cleanup job |
| Decomposition fails untuk complex tasks | Medium | Low | Fallback ke manual task creation |

---

## Success Metrics

### Functional
- [ ] MetricsTracker tracks all executions
- [ ] Template learning generates at least 1 new template from test data
- [ ] Task decomposition works untuk 2-3 level depth
- [ ] Context passing works antara dependent tasks
- [ ] Smart suggestions appear after task completion

### Non-Functional
- [ ] Metrics tracking adds < 5ms overhead per execution
- [ ] Template learning completes dalam < 100ms
- [ ] All operations 100% offline
- [ ] Zero additional storage (no model files)
- [ ] 100% test coverage untuk new components

---

## Constraints Checklist

- [x] No Ollama/local LLM storage
- [x] Rule-based first, LLM-ready architecture
- [x] Database-centric (all state di PostgreSQL)
- [x] No Docker
- [x] No Redis
- [x] No filesystem access
- [x] Python only
- [x] PostgreSQL only
- [x] No comments in code
- [x] No frontend

---

## Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| Week 1 | Sub-Phase 3.4 | MetricsTracker, Pattern Analyzer |
| Week 2 | Sub-Phase 3.5 | Task Decomposer, Context Manager |
| Week 3 | Sub-Phase 3.6 | Template Learner, Versioning |
| Week 4 | Sub-Phase 3.7 | Suggestion Engine, Final Integration |

---

## Next Steps

1. Review dan approve this plan
2. Create detailed task breakdown (TASK_BREAKDOWN_PHASE3_FULL.md)
3. Start Sub-Phase 3.4: Self-Improvement Loop
4. Test setiap component satu per satu
5. Iterate based on findings

---

**Status:** Awaiting Approval
**Author:** PlasmaAgent Architecture Team
**Last Updated:** 2026-06-02
