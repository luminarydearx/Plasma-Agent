# Phase 4: Production Hardening

**Status**: 🚧 IN PROGRESS  
**Started**: 2026-06-03  
**Estimated Duration**: ~32 hours  
**Total Tasks**: ~40 tasks

---

## 🎯 Overview

Phase 4 fokus pada production hardening untuk membuat PlasmaAgent siap deployment di environment production dengan reliability, security, dan observability yang tinggi.

---

## 📦 Sub-Phases

### Sub-Phase 4.1: Scheduling & Automation (~10 hours)
**Goal**: Implementasi task scheduling system untuk recurring dan one-time scheduled tasks.

#### Tasks:
- **4.1.1** Cron expression parser
- **4.1.2** Scheduler service (background worker)
- **4.1.3** One-time scheduled tasks
- **4.1.4** Recurring task patterns (daily, weekly, monthly)
- **4.1.5** Task dependencies & triggers
- **4.1.6** Scheduler persistence (survive restarts)
- **4.1.7** CLI commands (`plasma schedule create/list/run`)
- **4.1.8** Comprehensive testing

#### Technical Decisions:
- Use `croniter` library for cron parsing
- Background scheduler dengan asyncio
- Store schedules in `task_schedules` table
- Support timezone-aware scheduling

---

### Sub-Phase 4.2: Observability & Monitoring (~8 hours)
**Goal**: Implementasi monitoring dan alerting system untuk production visibility.

#### Tasks:
- **4.2.1** Metrics aggregation service
- **4.2.2** Real-time terminal dashboard (Rich Live)
- **4.2.3** Performance metrics (execution time, success rate, throughput)
- **4.2.4** Alert system (webhook integration)
- **4.2.5** Telegram bot notifications
- **4.2.6** Health monitoring endpoint
- **4.2.7** CLI commands (`plasma monitor dashboard/alerts`)
- **4.2.8** Comprehensive testing

#### Technical Decisions:
- Use Rich Live for terminal dashboard
- Webhook support untuk Slack/Discord/Telegram
- Metrics stored in `metrics_snapshots` table
- Configurable alert thresholds

---

### Sub-Phase 4.3: Security & Audit (~8 hours)
**Goal**: Implementasi authentication, authorization, dan audit logging.

#### Tasks:
- **4.3.1** User model & authentication (JWT)
- **4.3.2** Role-based access control (RBAC)
- **4.3.3** Permission system (task CRUD, execution, admin)
- **4.3.4** Audit log (who did what when)
- **4.3.5** Command sandboxing (whitelist/blacklist)
- **4.3.6** Secret management (encrypted credentials)
- **4.3.7** CLI commands (`plasma auth login/logout/users`)
- **4.3.8** Comprehensive testing

#### Technical Decisions:
- JWT tokens dengan refresh token rotation
- RBAC dengan roles: admin, operator, viewer
- Audit log immutable (append-only)
- Secrets encrypted dengan Fernet (symmetric encryption)

---

### Sub-Phase 4.4: Reliability Engineering (~6 hours)
**Goal**: Implementasi patterns untuk high availability dan graceful degradation.

#### Tasks:
- **4.4.1** Circuit breaker pattern
- **4.4.2** Connection retry dengan exponential backoff
- **4.4.3** Graceful shutdown (drain running tasks)
- **4.4.4** Health checks & readiness probes
- **4.4.5** Disaster recovery (backup/restore)
- **4.4.6** Rate limiting (per user/task)
- **4.4.7** Comprehensive testing

#### Technical Decisions:
- Circuit breaker dengan states: CLOSED, OPEN, HALF_OPEN
- Graceful shutdown dengan SIGTERM handler
- Backup/restore dengan pg_dump
- Rate limiting dengan token bucket algorithm

---

## 🗄️ Database Schema Changes

### New Tables:

#### `task_schedules`
```sql
CREATE TABLE task_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    cron_expression VARCHAR(100) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    enabled BOOLEAN DEFAULT true,
    next_run_at TIMESTAMP WITH TIME ZONE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `metrics_snapshots`
```sql
CREATE TABLE metrics_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_type VARCHAR(50) NOT NULL,
    metrics JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `audit_logs`
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 🧪 Testing Strategy

### Unit Tests
- Setiap component minimal 30-50 tests
- Edge cases, error handling, security tests
- Target: 1000+ unit tests total

### Integration Tests
- End-to-end workflows
- Database integration
- Concurrent execution tests
- Target: 200+ integration tests

### Stress Tests
- 1000 concurrent schedules
- 10000 audit log entries
- Rate limiting under load

---

## 📊 Success Metrics

### Functional
- ✅ Scheduler runs tasks at specified times
- ✅ Dashboard shows real-time metrics
- ✅ Authentication works with JWT
- ✅ Circuit breaker prevents cascading failures

### Non-Functional
- ✅ Scheduler latency < 1 second
- ✅ Dashboard refresh rate < 5 seconds
- ✅ Authentication latency < 100ms
- ✅ Zero data loss during graceful shutdown

### Security
- ✅ All secrets encrypted at rest
- ✅ Audit log immutable
- ✅ RBAC enforced on all endpoints
- ✅ Command sandboxing prevents injection

---

## 🚀 Next Steps

1. Start Sub-Phase 4.1 (Scheduling & Automation)
2. Implement cron parser and scheduler service
3. Add CLI commands for schedule management
4. Comprehensive testing
5. Move to Sub-Phase 4.2 (Observability)

---

## 📝 Notes

- Phase 4 akan membuat PlasmaAgent production-ready
- Setelah Phase 4, lanjut ke Phase 5 (Intelligence Expansion)
- Phase 6 (Ecosystem) adalah optional untuk web UI dan plugins
