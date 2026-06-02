# ============================================
# PHASE 1 COMPLETE VERIFICATION SCRIPT (CORRECTED)
# ============================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "PHASE 1 VERIFICATION - STARTING" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Run all pytest tests
Write-Host "`n[1/7] Running pytest tests..." -ForegroundColor Yellow
uv run pytest -v --tb=short

# 2. Check CLI help
Write-Host "`n[2/7] Checking CLI commands..." -ForegroundColor Yellow
uv run plasma --help

# 3. Check task subcommands
Write-Host "`n[3/7] Checking task subcommands..." -ForegroundColor Yellow
uv run plasma task --help

# 4. Verify database schema
Write-Host "`n[4/7] Verifying database schema..." -ForegroundColor Yellow
$env:PGPASSWORD = "090208"
psql -U postgres -d plasmaagent -c "\dt"

# 5. Check alembic migrations
Write-Host "`n[5/7] Checking alembic migrations..." -ForegroundColor Yellow
uv run alembic current
uv run alembic history

# 6. End-to-end task lifecycle test (CORRECTED FLOW)
Write-Host "`n[6/7] Running end-to-end task lifecycle test..." -ForegroundColor Yellow
Write-Host "  (Flow: create → run → [manual:fail] → retry → delete)" -ForegroundColor Gray

# Create task
Write-Host "  → Creating test task..." -ForegroundColor Gray
$createOutput = uv run plasma task create --name "E2E Verification Task" --description "Complete lifecycle test"
Write-Host $createOutput

# Extract task ID from output
$taskId = ($createOutput | Select-String -Pattern "Task created: ([a-f0-9\-]+)").Matches.Groups[1].Value

if ($taskId) {
    # List tasks
    Write-Host "  → Listing tasks..." -ForegroundColor Gray
    uv run plasma task list
    
    # Show task
    Write-Host "  → Showing task details..." -ForegroundColor Gray
    uv run plasma task show --id $taskId
    
    # Run task (transition to RUNNING)
    Write-Host "  → Running task (PENDING → RUNNING)..." -ForegroundColor Gray
    uv run plasma task run --id $taskId
    
    # MANUALLY set to FAILED via psql (because Phase 1 has no executor)
    Write-Host "  → Manually setting task to FAILED via psql (RUNNING → FAILED)..." -ForegroundColor Gray
    psql -U postgres -d plasmaagent -c "UPDATE tasks SET status = 'FAILED', updated_at = NOW() WHERE id = '$taskId';"
    
    # Show task after manual fail
    Write-Host "  → Showing task after manual fail..." -ForegroundColor Gray
    uv run plasma task show --id $taskId
    
    # Retry task (transition FAILED → PENDING) - THIS IS VALID
    Write-Host "  → Retrying task (FAILED → PENDING)..." -ForegroundColor Gray
    uv run plasma task retry --id $taskId
    
    # Show task after retry
    Write-Host "  → Showing task after retry..." -ForegroundColor Gray
    uv run plasma task show --id $taskId
    
    # Delete task
    Write-Host "  → Deleting task..." -ForegroundColor Gray
    uv run plasma task delete --id $taskId --force
    
    # Verify deletion
    Write-Host "  → Verifying deletion..." -ForegroundColor Gray
    uv run plasma task list
} else {
    Write-Host "  ⚠️  Could not extract task ID, skipping lifecycle test" -ForegroundColor Red
}

# 7. Check for warnings or errors
Write-Host "`n[7/7] Final health check..." -ForegroundColor Yellow
uv run plasma doctor

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "PHASE 1 VERIFICATION - COMPLETE" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Expected Results:" -ForegroundColor Cyan
Write-Host "  ✓ 11/11 pytest tests passed" -ForegroundColor White
Write-Host "  ✓ 0 deprecation warnings" -ForegroundColor White
Write-Host "  ✓ All CLI commands functional" -ForegroundColor White
Write-Host "  ✓ Database schema intact" -ForegroundColor White
Write-Host "  ✓ Task lifecycle completed: PENDING → RUNNING → FAILED → PENDING → DELETED" -ForegroundColor White
Write-Host "`nNote: CANCELLED tasks cannot be retried (by design - terminal state)" -ForegroundColor Yellow
Write-Host "`n"

# Clean up environment variable
Remove-Item Env:PGPASSWORD
