# PlasmaAgent - Master Roadmap

> Single source of truth untuk navigasi project. Diupdate setiap milestone selesai.

## Current State

| Metric | Value |
|---|---|
| **Latest Commit** | `021123c` |
| **Total Tests** | 214 |
| **Test Status** | 100% PASS |
| **Current Phase** | 3.5 Advanced Reasoning |
| **Overall Progress** | ~35% |

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

---

## In Progress

### Sub-Phase 3.5 - Advanced Reasoning 🔄
**Goal:** Make agent reason about complex tasks, decompose them, and recover from errors.

**Scope:**
1. Task decomposition engine (complex → sub-tasks)
2. Context manager (execution history awareness)
3. Error recovery suggestions
4. Dependency graph builder (DAG)
5. Conditional step execution (if/else logic)
6. Parallel step execution (independent branches)
7. Retry strategies (exponential backoff, circuit breaker)

**Estimated:** ~8 hours | ~10 tasks

---

## Upcoming Phases

### Sub-Phase 3.6 - Template Evolution
- Learn from successful user tasks
- Auto-generate new templates from patterns
- Template versioning & A/B testing
- Template retirement (low success rate)

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

## Current Focus: Sub-Phase 3.5

**Next Action:** Start Task 3.5.1 - Task Decomposition Engine

**Planning Doc:** `SUBPHASE_3_5_PLAN.md` (created at start, deleted when done)
