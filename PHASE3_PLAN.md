# Phase 3: Intelligence Engine

**Status:** 🚧 IN PROGRESS  
**Start Date:** 2026-06-02  
**Architecture:** Hybrid (Rule-based first, LLM-ready)

---

## 🎯 Overview

Phase 3 mengintegrasikan **intelligence layer** ke PlasmaAgent untuk:
- Generate tasks dari natural language
- Decompose complex tasks menjadi steps
- Self-improvement dari execution history
- Future-proof untuk LLM integration (Ollama/OpenAI/Anthropic)

**Key Decision:** 
- ❌ No local LLM storage (Ollama ditunda)
- ✅ Rule-based provider dulu (zero storage, deterministic)
- ✅ Pluggable architecture (bisa swap ke LLM kapan saja)

---

## 📋 Scope

### MVP (Phase 3.1-3.3) — CURRENT FOCUS

#### 3.1 Intelligence Provider Abstraction
- Protocol interface untuk semua providers
- RuleBasedProvider (pattern matching + templates)
- Provider factory & configuration
- Token counting abstraction

#### 3.2 Task Generation Engine
- Natural language parser (regex + heuristics)
- Template library untuk common tasks
- Step decomposition logic
- Command generation dari task description

#### 3.3 Confirmation & Preview Flow
- Preview generated task sebelum execute
- Edit capabilities (override AI suggestions)
- Confirmation prompts
- Dry-run mode

### Full (Phase 3.4-3.6) — FUTURE

#### 3.4 Self-Improvement Loop
- Success metrics tracking
- Failure pattern analysis
- Auto-generate better templates
- Learn dari execution history

#### 3.5 Advanced Reasoning
- Task decomposition (complex → sub-tasks)
- Context-aware execution
- Error recovery suggestions
- Dependency detection

#### 3.6 LLM Providers (Optional)
- OllamaProvider (local inference)
- OpenAIProvider (GPT-4, GPT-3.5)
- AnthropicProvider (Claude)
- GroqProvider (fast inference)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Input                            │
│  "backup database postgresql setiap hari jam 2 pagi"    │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              TaskGenerator Service                       │
│  ├─ Parse natural language                              │
│  ├─ Select provider (rule-based/LLM)                    │
│  ├─ Generate task + steps                               │
│  └─ Return preview                                      │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│            Intelligence Provider (Protocol)              │
├─────────────────────────────────────────────────────────┤
│  RuleBasedProvider  ← MVP (current)                     │
│  ├─ Pattern matching                                    │
│  ├─ Template library                                    │
│  └─ Heuristic rules                                     │
├─────────────────────────────────────────────────────────┤
│  OllamaProvider      ← Future                           │
│  OpenAIProvider     ← Future                            │
│  AnthropicProvider  ← Future                            │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Generated Task Preview                      │
│  Name: Backup PostgreSQL Database                       │
│  Steps:                                                 │
│    1. pg_dump -U postgres plasmaagent > backup.sql     │
│    2. Verify backup size > 0                            │
│  Schedule: Daily at 02:00                               │
│  [Confirm] [Edit] [Cancel]                              │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Execute Task (Phase 2)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 MVP Tasks Breakdown

### 3.1 Intelligence Provider Abstraction (8 tasks)
1. Create `IntelligenceProvider` protocol
2. Define data models (TaskSuggestion, StepSuggestion)
3. Implement provider factory
4. Add configuration system (provider selection)
5. Create base exception classes
6. Add token counting abstraction
7. Implement provider health check
8. Write unit tests untuk protocol

### 3.2 RuleBasedProvider Implementation (12 tasks)
1. Create `RuleBasedProvider` class
2. Implement pattern matching engine (regex library)
3. Create template library (backup, cleanup, monitoring, dll)
4. Implement task name extraction
5. Implement step decomposition logic
6. Add command generation dari templates
7. Implement confidence scoring
8. Add pattern priority system
9. Create template validation
10. Implement fallback patterns
11. Add template documentation
12. Write integration tests

### 3.3 Task Generation Service (10 tasks)
1. Create `TaskGenerator` service
2. Implement natural language parser
3. Add provider selection logic
4. Implement preview generation
5. Add edit capabilities (override suggestions)
6. Implement confirmation flow
7. Add dry-run mode
8. Create error handling
9. Add logging
10. Write unit tests

### 3.4 CLI Integration (6 tasks)
1. Add `plasma task generate` command
2. Implement interactive prompts (typer)
3. Add `--preview` flag (no execute)
4. Implement `--confirm` flag (auto-confirm)
5. Add `--template` flag (use specific template)
6. Write integration tests

### 3.5 Template Library (15 tasks)
1. Database backup templates (PostgreSQL, MySQL)
2. File cleanup templates (temp files, logs)
3. System monitoring templates (disk, memory, CPU)
4. Git operations templates (commit, push, pull)
5. Docker operations templates (build, run, cleanup)
6. Network tools templates (ping, traceroute)
7. Security audit templates (port scan, vulnerability check)
8. Performance testing templates (load test, benchmark)
9. Data export templates (CSV, JSON, XML)
10. Notification templates (email, webhook)
11. Custom template creation system
12. Template validation
13. Template versioning
14. Template documentation
15. Write tests untuk semua templates

---

## 🎯 MVP Success Criteria

### Functional Requirements
- ✅ User bisa input natural language
- ✅ System generate task + steps otomatis
- ✅ Preview ditampilkan sebelum execute
- ✅ User bisa edit/override suggestions
- ✅ Confirmation flow bekerja
- ✅ Dry-run mode tersedia

### Non-Functional Requirements
- ✅ Response time < 100ms (rule-based)
- ✅ Zero storage overhead (no model files)
- ✅ 100% offline capable
- ✅ Deterministic output (same input = same output)
- ✅ Extensible architecture (easy add new providers)

### Test Coverage
- ✅ Unit tests: 90%+ coverage
- ✅ Integration tests: all providers
- ✅ Manual tests: 10+ real-world examples

---

## 🚀 Implementation Order

1. **Week 1:** 3.1 Intelligence Provider Abstraction
2. **Week 2:** 3.2 RuleBasedProvider Implementation
3. **Week 3:** 3.3 Task Generation Service + 3.4 CLI Integration
4. **Week 4:** 3.5 Template Library + Testing

**Total:** ~51 tasks, ~4 weeks

---

## 📝 Technical Decisions

### Why Rule-Based First?
1. **Zero storage** — no model files (40GB+ saved)
2. **Deterministic** — same input = same output
3. **Fast** — < 10ms response time
4. **Offline** — no internet required
5. **Testable** — easy to unit test
6. **Secure** — no data leaves machine

### Why Pluggable Architecture?
1. **Future-proof** — easy add LLM later
2. **Flexible** — user pilih provider sesuai kebutuhan
3. **Testable** — mock providers untuk testing
4. **Maintainable** — clean separation of concerns

### Pattern Matching Strategy
1. **Regex patterns** untuk keyword extraction
2. **Template matching** untuk common tasks
3. **Heuristic rules** untuk edge cases
4. **Confidence scoring** untuk multiple matches
5. **Fallback patterns** untuk unknown inputs

---

## 🔧 Dependencies

### New Dependencies
- `regex` — advanced pattern matching (optional, bisa pakai re bawaan)
- `pyyaml` — template configuration (optional)

### Existing Dependencies (Reuse)
- `typer` — CLI commands
- `rich` — formatted output
- `pydantic` — data models
- `psycopg` — database operations

---

## 📊 Metrics & Observability

### Track Metrics
- Task generation success rate
- Average response time
- Most used templates
- Pattern match confidence
- User override rate (how often user edit AI suggestions)

### Logging
- Input natural language
- Selected provider
- Generated task + steps
- User actions (confirm/edit/cancel)
- Execution time

---

## 🎓 Example Use Cases

### Example 1: Database Backup
```bash
$ plasma task generate

Input: "backup database postgresql setiap hari jam 2 pagi ke folder D:\backups"

Generated:
  Name: Backup PostgreSQL Database
  Steps:
    1. pg_dump -U postgres -F c plasmaagent > D:\backups\backup_$(date).sql
    2. powershell -Command "if ((Get-Item D:\backups\backup_*.sql).Length -eq 0) { exit 1 }"
  Schedule: Daily at 02:00 (Phase 4)

[Confirm] [Edit] [Cancel]
```

### Example 2: Cleanup Temp Files
```bash
$ plasma task generate

Input: "hapus file temporary di C:\Temp yang lebih dari 7 hari"

Generated:
  Name: Cleanup Old Temp Files
  Steps:
    1. powershell -Command "Get-ChildItem C:\Temp -Recurse | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force"
    2. echo "Cleanup completed"

[Confirm] [Edit] [Cancel]
```

### Example 3: System Monitoring
```bash
$ plasma task generate

Input: "cek disk space dan kirim alert jika kurang dari 10GB"

Generated:
  Name: Monitor Disk Space
  Steps:
    1. powershell -Command "$free = (Get-PSDrive C).Free / 1GB; if ($free -lt 10) { Write-Error 'Low disk space: $free GB' }"
    2. echo "Disk check completed"

[Confirm] [Edit] [Cancel]
```

---

## 🚨 Risks & Mitigations

### Risk 1: Limited Natural Language Understanding
**Mitigation:**
- Start dengan common patterns saja
- Provide clear error messages untuk unknown inputs
- Allow manual task creation sebagai fallback
- Expand pattern library iteratif

### Risk 2: Template Maintenance
**Mitigation:**
- Document semua templates dengan jelas
- Version templates untuk backward compatibility
- Allow user custom templates
- Community contribution system (future)

### Risk 3: Performance Degradation
**Mitigation:**
- Pattern matching sangat cepat (< 10ms)
- Cache frequent patterns
- Lazy load templates
- Monitor response time metrics

---

## 📚 References

### Similar Projects
- [Natural Language Shell](https://github.com/alexandru/nlsh) — NL to shell commands
- [Tellina](https://github.com/TellinaTool/tellina) — NL to bash scripts
- [Bashexplainer](https://github.com/nickvdyck/bashexplainer) — Explain bash commands

### Design Patterns
- Strategy Pattern (provider abstraction)
- Factory Pattern (provider selection)
- Template Method (task generation flow)
- Observer Pattern (metrics & logging)

---

## ✅ Definition of Done

### MVP Complete When:
- [ ] All 3.1-3.3 tasks completed
- [ ] 5+ templates implemented
- [ ] CLI command working
- [ ] 90%+ test coverage
- [ ] Manual testing dengan 10+ examples
- [ ] Documentation complete
- [ ] No critical bugs

### Full Complete When:
- [ ] All 3.4-3.6 tasks completed
- [ ] 15+ templates implemented
- [ ] Self-improvement loop working
- [ ] LLM provider (optional) integrated
- [ ] Performance benchmarks met
- [ ] Production-ready

---

## 🎯 Next Steps

1. **Create PHASE3_PLAN.md** ✅ (this document)
2. **Implement 3.1 Intelligence Provider Abstraction**
3. **Implement 3.2 RuleBasedProvider**
4. **Implement 3.3 Task Generation Service**
5. **Add CLI integration**
6. **Build template library**
7. **Test & iterate**
8. **Document everything**

---

**Ready to start coding!** 🚀
