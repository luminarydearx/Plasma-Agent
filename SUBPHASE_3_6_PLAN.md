# Sub-Phase 3.6 Plan: Template Evolution

**Goal:** Learn from user-created tasks and evolve templates automatically.

## Scope

1. **Template Learner** - Extract patterns from successful user tasks
2. **Template Versioning** - Track template changes over time
3. **A/B Testing** - Test multiple template versions simultaneously
4. **Template Retirement** - Auto-retire low-performing templates
5. **Auto-template Generation** - Create new templates from user patterns
6. **Comprehensive Testing** - Integration, stress, security, edge cases
7. **Cleanup** - Delete planning file

## Architecture Decisions

- **Database-centric:** All template evolution data in `template_versions` table
- **Statistical learning:** Pattern frequency analysis, confidence scoring
- **Safe defaults:** New templates start with low confidence, require validation
- **No ML:** Pure statistical analysis (no local LLM storage)

## Tasks Breakdown

### Task 3.6.1: Template Learner
- Analyze successful user tasks
- Extract command patterns
- Generate candidate templates
- Score by frequency + success rate

### Task 3.6.2: Template Versioning
- `template_versions` table migration
- Track changes over time
- Rollback capability

### Task 3.6.3: A/B Testing
- Serve multiple template versions
- Track performance per version
- Auto-select best performer

### Task 3.6.4: Template Retirement
- Identify low-performing templates
- Auto-retire below threshold
- Archive for audit

### Task 3.6.5: Auto-template Generation
- Detect new patterns from user tasks
- Generate template candidates
- Human approval workflow

### Task 3.6.6: Comprehensive Testing
- Unit tests (model, service, CLI)
- Integration tests (end-to-end)
- Stress tests (1000+ templates)
- Security tests (injection, isolation)

### Task 3.6.7: Cleanup
- Delete SUBPHASE_3_6_PLAN.md
- Update ROADMAP.md

## Success Criteria
- All tests passing (unit + integration)
- Zero regression in Phase 1, 2, 3 MVP, 3.4, 3.5
- Template evolution works end-to-end
- Performance < 5s for analysis
- No security vulnerabilities
