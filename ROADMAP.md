# PlasmaAgent - Master Roadmap

> Single source of truth untuk navigasi project. Diupdate setiap milestone selesai.

## Current State

| Metric | Value |
|---|---|
| **Latest Commit** | `cccf733` |
| **Total Tests** | 607 |
| **Test Status** | 100% PASS |
| **Current Phase** | 3.6 Template Evolution |
| **Overall Progress** | ~40% |

---

## Completed Phases

### Phase 1 - Foundation ✅
- Database schema (PostgreSQL + pgvector ready)
- PTSM (PostgreSQL Transactional State Machine)
- Async psycopg3 connection pool
- CLI foundation (typer + rich)
- Task CRUD lifecycle

### Phase 2 - Execution Engine ✅
- Shell executor (subprocess + async)
- Real-time output capture
- Step management (pending → running → completed/failed)
- Execution logging (stdout, stderr, exit_code, duration)
- Retry mechanism
- CLI `plasma task run`

### Phase 3 MVP - Intelligence ✅
- Provider abstraction layer (pluggable)
- RuleBasedProvider (5 patterns: backup, cleanup, disk, git, system)
- TaskGenerator service
- CLI `plasma task generate`
- CLI robustness (7 critical bugs fixed)

### Sub-Phase 3.4 - Self-Improvement Loop ✅
- Template metrics tracking (table `template_metrics`)
- Execution metrics tracker
- Template optimizer
- CLI `plasma metrics show/analyze/optimize`
- 37 comprehensive tests (cross-phase, stress, security, edge cases)

### Sub-Phase 3.5 - Advanced Reasoning ✅
- TaskDecomposer (54 unit tests) — pattern-based decomposition
- ContextManager (84 unit tests) — session isolation, variable substitution
- ErrorAnalyzer (62 unit tests) — error pattern matching, recovery suggestions
- DependencyGraph (70 unit tests) — DAG with cycle detection, topological sort
- ConditionalEvaluator (39 unit tests) — conditional step execution
- ParallelExecutor (30 unit tests) — semaphore-based concurrency, fail-fast
- RetryExecutor (31 unit tests) — exponential backoff with jitter
- ReasoningService (38 unit tests) — orchestrates all components
- 22 integration tests (end-to-end, stress, security, performance, regression)

---

## In Progress

### Sub-Phase 3.6 - Template Evolution 🔄
**Goal:** Learn from user-created tasks and evolve templates automatically.

**Scope:**
1. Template learner (extract patterns from successful tasks)
2. Template versioning
3. A/B testing for templates
4. Template retirement (low success rate)
5. Auto-template generation from user patterns

**Estimated:** ~5 hours | ~7 tasks

---

## Upcoming Phases

### Sub-Phase 3.7 - Smart Suggestions
- Next action recommendations
- Similar task lookup
- Anomaly detection
- Performance optimization hints

### Phase 4 - Production Hardening
- **4.1 Scheduling** - Cron-like scheduler, one-time/recurring tasks
- **4.2 Observability** - Real-time dashboard, alerts (webhook/Telegram)
- **4.3 Security** - Auth, permissions, audit log, command sandboxing
- **4.4 Reliability** - Graceful degradation, circuit breaker, disaster recovery

### Phase 5 - Intelligence Expansion
- **5.1 Memory System** - Short-term + long-term (pgvector embeddings)
- **5.2 RAG** - Document ingestion, semantic search
- **5.3 Multi-Agent** - Planner + executor + reviewer coordination
- **5.4 Tool Use & Skills** - Skill registry, dynamic loading, versioning

### Phase 6 - Ecosystem & Polish
- **6.1 API Gateway** - REST (FastAPI), WebSocket, rate limiting
- **6.2 Web Dashboard** - React/Svelte frontend
- **6.3 Plugin System** - Hot-reload, sandboxing, marketplace
- **6.4 Cloud LLM Integration** - OpenAI/Anthropic/Groq (optional)
- **6.5 Distribution** - Installer (MSI/deb), auto-updater, docs

---

## Milestones

| Milestone | Definition | ETA |
|---|---|---|
| **M1: Usable AI Agent** | Tahap A (Phase 3 Full) complete | Current |
| **M2: Production AI Agent** | Tahap B (Phase 4) complete | After M1 |
| **M3: Mature AI Agent** | Tahap C (Phase 5) complete | After M2 |
| **M4: Complete Ecosystem** | Tahap D (Phase 6) complete | After M3 |

---

## Project Conventions

### Code Quality
- **NO comments** (`#` or `"""`) - code must be self-documenting
- **Single blank line** between code blocks (no double enters)
- **Type hints** mandatory for all functions
- **Pydantic V2** with `ConfigDict` (no deprecated `class Config`)
- **psycopg3 async** with `dict_row` factory

### Testing
- **Hybrid approach:** Test at end of each sub-phase
- **Edge cases mandatory:** Empty input, unicode, injection, concurrency
- **Cross-phase regression:** Always test Phase 1, 2, 3 MVP don't break
- **Stress tests:** 1000+ entries, concurrent ops, rapid succession

### File Management
- **Planning files** (SUBPHASE_X_Y_PLAN.md) created at start of sub-phase
- **Planning files deleted** when sub-phase is 100% complete and tested
- **ROADMAP.md** is permanent navigation source
- **README.md** updated at each milestone

### Architecture
- **Database-centric:** All state in PostgreSQL (no filesystem)
- **PTSM enforced:** Valid state transitions only
- **Provider abstraction:** Rule-based now, LLM-ready later
- **No local LLM storage:** Ollama etc. deferred until explicitly needed

---

## Current Focus: Sub-Phase 3.6

**Next Action:** Start Task 3.6.1 - Template Learner

**Planning Doc:** `SUBPHASE_3_6_PLAN.md` (to be created at start)
