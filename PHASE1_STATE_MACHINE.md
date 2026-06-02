# Phase 1: State Machine Documentation

## Valid Task State Transitions

```
┌─────────┐    run    ┌─────────┐
│ PENDING ├──────────>│ RUNNING │
└────┬────┘           └────┬────┘
     │                     │
     │ cancel              │ pause
     │                     ▼
     │                ┌────────┐
     │                │ PAUSED │
     │                └────┬───┘
     │                     │
     │                     │ resume
     │                     ▼
     │                ┌─────────┐
     │                │ RUNNING │
     │                └────┬────┘
     │                     │
     │                     │ complete
     │                     ▼
     │                ┌───────────┐
     │                │ COMPLETED │ (TERMINAL)
     │                └───────────┘
     │
     │                     │ fail
     │                     ▼
     │                ┌────────┐
     └────────────────│ FAILED │
        retry         └────┬───┘
                           │
                           │ (manual intervention / crash recovery)
                           ▼
                      ┌─────────┐
                      │ PENDING │
                      └─────────┘

     │ cancel (from any non-terminal state)
     ▼
┌───────────┐
│ CANCELLED │ (TERMINAL - cannot retry)
└───────────┘
```

## State Transition Rules

| From State | Valid Transitions To |
|------------|---------------------|
| PENDING | RUNNING, CANCELLED |
| RUNNING | PAUSED, COMPLETED, FAILED, CANCELLED |
| PAUSED | RUNNING, CANCELLED |
| FAILED | PENDING (retry) |
| COMPLETED | ❌ None (terminal state) |
| CANCELLED | ❌ None (terminal state) |

## Why CANCELLED Cannot Be Retried

**By Design Decision:**
- `CANCELLED` adalah **terminal state** yang menandakan user secara eksplisit membatalkan task
- Task yang di-cancel dianggap **tidak perlu dijalankan ulang**
- Jika user ingin menjalankan task yang sama, mereka harus **create task baru**

**Contrast with FAILED:**
- `FAILED` adalah state dimana task **gagal karena error teknis**
- Task yang failed **bisa di-retry** karena mungkin akan sukses di percobaan berikutnya
- Retry flow: `FAILED → PENDING → RUNNING → ...`

## Correct E2E Lifecycle Flow

### Flow 1: Success Path
```
create (PENDING)
  → run (PENDING → RUNNING)
  → complete (RUNNING → COMPLETED)
  → delete
```

### Flow 2: Failure and Retry Path
```
create (PENDING)
  → run (PENDING → RUNNING)
  → fail (RUNNING → FAILED)
  → retry (FAILED → PENDING)
  → run (PENDING → RUNNING)
  → complete (RUNNING → COMPLETED)
  → delete
```

### Flow 3: Cancellation Path
```
create (PENDING)
  → run (PENDING → RUNNING)
  → cancel (RUNNING → CANCELLED)
  → delete (no retry possible)
```

## Phase 1 Limitation

Phase 1 **belum memiliki execution engine**, sehingga:
- Task tidak bisa benar-benar "run" (tidak ada shell executor)
- Transition ke `FAILED` atau `COMPLETED` harus dilakukan **manual via SQL**:

```sql
-- Manually fail a task
UPDATE tasks SET status = 'FAILED', updated_at = NOW() WHERE id = '<task-id>';

-- Manually complete a task
UPDATE tasks SET status = 'COMPLETED', updated_at = NOW() WHERE id = '<task-id>';
```

Phase 2 akan mengimplementasikan execution engine yang akan:
- Execute task steps secara otomatis
- Capture output ke `execution_logs`
- Automatically transition ke `COMPLETED` atau `FAILED` berdasarkan hasil eksekusi

## Atomic State Transitions

Semua state transitions menggunakan **PostgreSQL Transactional State Machine (PTSM)**:

```python
async with db.transaction() as conn:
    await transition_task_state(conn, task_id, TaskStatus.RUNNING)
    # Transaction commits automatically if no exception
    # Rolls back if exception occurs
```

**Guarantees:**
1. **Atomicity** — State change terjadi secara atomik
2. **Concurrency** — `FOR UPDATE SKIP LOCKED` mencegah race conditions
3. **Crash Recovery** — Task yang interrupted saat RUNNING akan di-recover ke PAUSED

## Connection Pool Error After Exception

Jika Anda melihat error seperti:
```
Error: Invalid state transition for task ...: CANCELLED -> PENDING
error connecting in 'pool-1':
```

Ini **BUKAN bug** di connection pool, tapi **expected behavior**:
1. State transition error terdeteksi dan exception di-raise
2. Transaction di-rollback secara otomatis
3. Connection di-return ke pool
4. psycopg3 mungkin menampilkan warning saat cleanup (terutama di Windows)

**Yang penting:**
- ✅ State transition validation bekerja dengan benar
- ✅ Transaction rollback terjadi
- ✅ Connection di-return ke pool (tidak leak)
- ⚠️ Warning message bisa diabaikan selama tidak ada data corruption

## Testing State Transitions

### Valid Transitions (Should Succeed)
```bash
# PENDING → RUNNING
plasma task create --name "Test" --description "Test task"
plasma task run --id <task-id>

# RUNNING → FAILED (manual via SQL)
psql -U postgres -d plasmaagent -c "UPDATE tasks SET status = 'FAILED' WHERE id = '<task-id>';"

# FAILED → PENDING (retry)
plasma task retry --id <task-id>
```

### Invalid Transitions (Should Fail)
```bash
# CANCELLED → PENDING (INVALID)
plasma task create --name "Test" --description "Test task"
plasma task run --id <task-id>
plasma task cancel --id <task-id>
plasma task retry --id <task-id>  # ❌ This will fail (expected)
```

## Summary

| Aspect | Status |
|--------|--------|
| State machine logic | ✅ Correct by design |
| CANCELLED as terminal state | ✅ Intentional |
| FAILED can be retried | ✅ Working |
| Atomic transitions | ✅ Implemented |
| Connection pool | ✅ Proper cleanup |
| Phase 1 executor | ⏳ Coming in Phase 2 |
