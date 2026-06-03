$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "PlasmaAgent - Comprehensive Feature Test"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

function Write-Section {
    param([string]$Title)
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 80) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor Cyan
}

function Write-Test {
    param([string]$Name)
    Write-Host "`n[TEST] " -NoNewline -ForegroundColor Yellow
    Write-Host $Name -ForegroundColor White
}

function Write-Pass {
    param([string]$Message)
    Write-Host "  [PASS] " -NoNewline -ForegroundColor Green
    Write-Host $Message -ForegroundColor Gray
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] " -NoNewline -ForegroundColor Red
    Write-Host $Message -ForegroundColor Gray
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [i]  " -NoNewline -ForegroundColor Blue
    Write-Host $Message -ForegroundColor Gray
}

function Extract-UUID {
    param([string]$Output)
    if ($Output -match '([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})') {
        return $matches[1]
    }
    return $null
}

Write-Host "`n" -NoNewline
Write-Host "PLASMA AGENT - COMPREHENSIVE TEST SUITE" -ForegroundColor Magenta
Write-Host "Testing all phases: Foundation -> Execution -> Intelligence -> Scheduling -> Observability" -ForegroundColor Gray

$global:PassCount = 0
$global:FailCount = 0

Set-Location "C:\Users\Dearly Febriano\Documents\PlasmaAgent"

Write-Section "PHASE 1: FOUNDATION (Database, CLI, State Machine)"

Write-Test "1.1 Check Python installation"
$pythonVersion = uv run python --version 2>&1
if ($pythonVersion -match "Python 3\.") {
    Write-Pass "Python installed: $pythonVersion"
    $global:PassCount++
} else {
    Write-Fail "Python not found"
    $global:FailCount++
}

Write-Test "1.2 Check database connection"
$doctorOutput = uv run plasma doctor 2>&1
if ($doctorOutput -match "Database.*Connected") {
    Write-Pass "Database connected successfully"
    $global:PassCount++
} else {
    Write-Fail "Database connection failed"
    $global:FailCount++
}

Write-Test "1.3 Check database schema"
if ($doctorOutput -match "Schema.*Initialized") {
    Write-Pass "Database schema initialized"
    $global:PassCount++
} else {
    Write-Fail "Database schema not initialized"
    $global:FailCount++
}

Write-Test "1.4 Run unit tests"
$testOutput = uv run pytest tests/unit -q 2>&1
if ($testOutput -match "passed") {
    $passed = ($testOutput | Select-String -Pattern "(\d+) passed").Matches.Groups[1].Value
    Write-Pass "Unit tests passed: $passed tests"
    $global:PassCount++
} else {
    Write-Fail "Unit tests failed"
    $global:FailCount++
}

Write-Section "PHASE 2: EXECUTION ENGINE (Task Lifecycle)"

Write-Test "2.1 Create task with multiple commands"
$createOutput = uv run plasma task create --name "Test Task" --description "Testing execution" --command "echo Hello" --command "echo World" 2>&1 | Out-String
if ($createOutput -match "Task Created") {
    Write-Pass "Task created successfully"
    $global:PassCount++
    $testTaskId = Extract-UUID -Output $createOutput
    if ($testTaskId) {
        Write-Info "Task ID: $testTaskId"
    }
} else {
    Write-Fail "Task creation failed"
    $global:FailCount++
}

Write-Test "2.2 List tasks"
$listOutput = uv run plasma task list 2>&1 | Out-String
if ($listOutput -match "Test Task") {
    Write-Pass "Task listed successfully"
    $global:PassCount++
} else {
    Write-Fail "Task not found in list"
    $global:FailCount++
}

Write-Test "2.3 Show task details"
if ($testTaskId) {
    $showOutput = uv run plasma task show --id $testTaskId 2>&1 | Out-String
    if ($showOutput -match "Test Task") {
        Write-Pass "Task details displayed"
        $global:PassCount++
    } else {
        Write-Fail "Task details not displayed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID available"
    $global:FailCount++
}

Write-Test "2.4 Execute task"
if ($testTaskId) {
    $runOutput = uv run plasma task run --id $testTaskId 2>&1 | Out-String
    if ($runOutput -match "COMPLETED") {
        Write-Pass "Task executed successfully"
        $global:PassCount++
    } else {
        Write-Fail "Task execution failed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID available"
    $global:FailCount++
}

Write-Test "2.5 Check execution logs"
if ($testTaskId) {
    $logsOutput = uv run plasma task show --id $testTaskId --logs 2>&1 | Out-String
    if ($logsOutput -match "Hello") {
        Write-Pass "Execution logs captured"
        $global:PassCount++
    } else {
        Write-Fail "Execution logs not found"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID available"
    $global:FailCount++
}

Write-Test "2.6 Delete task"
if ($testTaskId) {
    $deleteOutput = uv run plasma task delete --id $testTaskId --force 2>&1 | Out-String
    if ($deleteOutput -match "DELETED") {
        Write-Pass "Task deleted successfully"
        $global:PassCount++
    } else {
        Write-Fail "Task deletion failed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID available"
    $global:FailCount++
}

Write-Section "PHASE 3 MVP: INTELLIGENCE ENGINE (Natural Language)"

Write-Test "3.1 Generate task from natural language (backup)"
$genOutput = uv run plasma task generate --input "backup database postgresql plasmaagent" --preview 2>&1 | Out-String
if ($genOutput -match "Confidence.*95%") {
    Write-Pass "Backup pattern matched with 95% confidence"
    $global:PassCount++
} else {
    Write-Fail "Backup pattern failed"
    $global:FailCount++
}

Write-Test "3.2 Generate task from natural language (cleanup)"
$genOutput = uv run plasma task generate --input "cleanup old files in C:\Temp" --preview 2>&1 | Out-String
if ($genOutput -match "Confidence.*90%") {
    Write-Pass "Cleanup pattern matched with 90% confidence"
    $global:PassCount++
} else {
    Write-Fail "Cleanup pattern failed"
    $global:FailCount++
}

Write-Test "3.3 Generate task from natural language (disk check)"
$genOutput = uv run plasma task generate --input "check disk space" --preview 2>&1 | Out-String
if ($genOutput -match "Confidence.*85%") {
    Write-Pass "Disk check pattern matched with 85% confidence"
    $global:PassCount++
} else {
    Write-Fail "Disk check pattern failed"
    $global:FailCount++
}

Write-Test "3.4 Generate task from natural language (git)"
$genOutput = uv run plasma task generate --input "git commit changes" --preview 2>&1 | Out-String
if ($genOutput -match "Confidence.*80%") {
    Write-Pass "Git pattern matched with 80% confidence"
    $global:PassCount++
} else {
    Write-Fail "Git pattern failed"
    $global:FailCount++
}

Write-Test "3.5 Generate and create task (auto-confirm)"
$genCreateOutput = uv run plasma task generate --input "show system info" --yes 2>&1 | Out-String
if ($genCreateOutput -match "Task Created") {
    Write-Pass "Task generated and created successfully"
    $global:PassCount++
    $genTaskId = Extract-UUID -Output $genCreateOutput
    if ($genTaskId) {
        Write-Info "Generated Task ID: $genTaskId"
        uv run plasma task delete --id $genTaskId --force 2>&1 | Out-Null
    }
} else {
    Write-Fail "Task generation/creation failed"
    $global:FailCount++
}

Write-Section "SUB-PHASE 3.4: SELF-IMPROVEMENT (Metrics & Optimization)"

Write-Test "3.4.1 Show template metrics"
$metricsOutput = uv run plasma metrics show 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Metrics command executed successfully"
    $global:PassCount++
} else {
    Write-Fail "Metrics command failed"
    $global:FailCount++
}

Write-Test "3.4.2 Analyze template performance"
$analyzeOutput = uv run plasma metrics analyze 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Analysis command executed successfully"
    $global:PassCount++
} else {
    Write-Fail "Analysis command failed"
    $global:FailCount++
}

Write-Test "3.4.3 Get optimization recommendations"
$optimizeOutput = uv run plasma metrics optimize --dry-run 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Optimization command executed successfully"
    $global:PassCount++
} else {
    Write-Fail "Optimization command failed"
    $global:FailCount++
}

Write-Section "SUB-PHASE 4.1: SCHEDULING (Cron, Dependencies, Triggers)"

Write-Test "4.1.1 Create task for scheduling"
$scheduleTaskOutput = uv run plasma task create --name "Scheduled Test Task" --description "For scheduling" --command "echo Scheduled" 2>&1 | Out-String
$scheduleTaskId = Extract-UUID -Output $scheduleTaskOutput
if ($scheduleTaskId) {
    Write-Pass "Task for scheduling created"
    $global:PassCount++
    Write-Info "Task ID: $scheduleTaskId"
} else {
    Write-Fail "Task for scheduling failed"
    $global:FailCount++
}

Write-Test "4.1.2 Create schedule (cron)"
if ($scheduleTaskId) {
    $scheduleOutput = uv run plasma schedule create $scheduleTaskId --cron "0 * * * *" 2>&1 | Out-String
    if ($scheduleOutput -match "Scheduled task") {
        Write-Pass "Schedule created successfully"
        $global:PassCount++
    } else {
        Write-Fail "Schedule creation failed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID for scheduling"
    $global:FailCount++
}

Write-Test "4.1.3 List schedules"
$scheduleListOutput = uv run plasma schedule list 2>&1 | Out-String
if ($scheduleListOutput -match "Scheduled Test Task") {
    Write-Pass "Schedule listed successfully"
    $global:PassCount++
} else {
    Write-Fail "Schedule not found in list"
    $global:FailCount++
}

Write-Test "4.1.4 Show schedule status"
if ($scheduleTaskId) {
    $statusOutput = uv run plasma schedule status $scheduleTaskId 2>&1 | Out-String
    if ($statusOutput -match "Scheduled Test Task") {
        Write-Pass "Schedule status displayed"
        $global:PassCount++
    } else {
        Write-Fail "Schedule status not displayed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID for status check"
    $global:FailCount++
}

Write-Test "4.1.5 Delete schedule and task"
if ($scheduleTaskId) {
    $deleteScheduleOutput = uv run plasma schedule delete $scheduleTaskId --force 2>&1 | Out-String
    $deleteTaskOutput = uv run plasma task delete --id $scheduleTaskId --force 2>&1 | Out-String
    if ($deleteScheduleOutput -match "Deleted schedule" -and $deleteTaskOutput -match "DELETED") {
        Write-Pass "Schedule and task deleted"
        $global:PassCount++
    } else {
        Write-Fail "Deletion failed"
        $global:FailCount++
    }
} else {
    Write-Fail "No task ID for deletion"
    $global:FailCount++
}

Write-Section "SUB-PHASE 4.2: OBSERVABILITY (Metrics, Dashboard, Alerts)"

Write-Test "4.2.1 Show system metrics"
$sysMetricsOutput = uv run plasma monitor metrics --hours 1 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "System metrics displayed"
    $global:PassCount++
} else {
    Write-Fail "System metrics command failed"
    $global:FailCount++
}

Write-Test "4.2.2 Show top templates"
$topTemplatesOutput = uv run plasma monitor top-templates --limit 5 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Top templates displayed"
    $global:PassCount++
} else {
    Write-Fail "Top templates command failed"
    $global:FailCount++
}

Write-Test "4.2.3 Show failure patterns"
$failuresOutput = uv run plasma monitor failures --limit 5 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Failure patterns displayed"
    $global:PassCount++
} else {
    Write-Fail "Failure patterns command failed"
    $global:FailCount++
}

Write-Test "4.2.4 Create alert rule"
$alertOutput = uv run plasma alerts create --name "Test Alert" --metric success_rate --condition less_than --threshold 0.5 --webhook "https://example.com/webhook" 2>&1 | Out-String
if ($alertOutput -match "Alert Rule Created") {
    Write-Pass "Alert rule created"
    $global:PassCount++
    $alertId = Extract-UUID -Output $alertOutput
    if ($alertId) {
        Write-Info "Alert ID: $alertId"
    }
} else {
    Write-Fail "Alert rule creation failed"
    $global:FailCount++
}

Write-Test "4.2.5 List alert rules"
$alertListOutput = uv run plasma alerts list 2>&1 | Out-String
if ($alertListOutput -match "Test Alert") {
    Write-Pass "Alert rules listed"
    $global:PassCount++
} else {
    Write-Fail "Alert rules not listed"
    $global:FailCount++
}

Write-Test "4.2.6 Test alert trigger"
$alertTestOutput = uv run plasma alerts test --metric success_rate --value 0.3 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Alert test executed"
    $global:PassCount++
} else {
    Write-Fail "Alert test failed"
    $global:FailCount++
}

Write-Test "4.2.7 Delete alert rule"
if ($alertId) {
    $deleteAlertOutput = uv run plasma alerts delete $alertId 2>&1 | Out-String
    if ($deleteAlertOutput -match "Alert Rule Deleted" -or $deleteAlertOutput -match "deleted") {
        Write-Pass "Alert rule deleted"
        $global:PassCount++
    } else {
        Write-Fail "Alert rule deletion failed"
        $global:FailCount++
    }
} else {
    Write-Fail "No alert ID available"
    $global:FailCount++
}

Write-Section "EDGE CASES & STRESS TESTS"

Write-Test "Edge Case 1: Empty input handling"
$emptyOutput = uv run plasma task generate --input "" --preview 2>&1 | Out-String
if ($emptyOutput -match "Input cannot be empty" -or $emptyOutput -match "Error") {
    Write-Pass "Empty input handled correctly"
    $global:PassCount++
} else {
    Write-Fail "Empty input not handled"
    $global:FailCount++
}

Write-Test "Edge Case 2: SQL injection attempt"
$injectionOutput = uv run plasma task generate --input "backup database'; DROP TABLE tasks;--" --preview 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
    Write-Pass "SQL injection attempt handled safely"
    $global:PassCount++
} else {
    Write-Fail "SQL injection not handled"
    $global:FailCount++
}

Write-Test "Edge Case 3: Unicode input (Japanese)"
$unicodeOutput = uv run plasma task generate --input "backup database" --preview 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Unicode input handled correctly"
    $global:PassCount++
} else {
    Write-Fail "Unicode input not handled"
    $global:FailCount++
}

Write-Test "Edge Case 4: Very long input"
$longInput = "backup database " + ("x" * 500)
$longOutput = uv run plasma task generate --input $longInput --preview 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Long input handled correctly"
    $global:PassCount++
} else {
    Write-Fail "Long input not handled"
    $global:FailCount++
}

Write-Test "Edge Case 5: Invalid task ID"
$invalidOutput = uv run plasma task show --id "invalid-uuid" 2>&1 | Out-String
if ($invalidOutput -match "Invalid task ID" -or $invalidOutput -match "not found" -or $invalidOutput -match "Error") {
    Write-Pass "Invalid task ID handled correctly"
    $global:PassCount++
} else {
    Write-Fail "Invalid task ID not handled"
    $global:FailCount++
}

Write-Section "FINAL SUMMARY"

$totalTests = $global:PassCount + $global:FailCount
$passRate = if ($totalTests -gt 0) { [math]::Round(($global:PassCount / $totalTests) * 100, 2) } else { 0 }

Write-Host "`n  Total Tests:    " -NoNewline -ForegroundColor White
Write-Host $totalTests -ForegroundColor Cyan
Write-Host "  Passed:         " -NoNewline -ForegroundColor White
Write-Host "$global:PassCount" -ForegroundColor Green
Write-Host "  Failed:         " -NoNewline -ForegroundColor White
Write-Host "$global:FailCount" -ForegroundColor Red
Write-Host "  Pass Rate:      " -NoNewline -ForegroundColor White
Write-Host "$passRate%" -ForegroundColor $(if ($passRate -ge 90) { "Green" } elseif ($passRate -ge 70) { "Yellow" } else { "Red" })

Write-Host "`n" -NoNewline
if ($global:FailCount -eq 0) {
    Write-Host "  ALL TESTS PASSED! PlasmaAgent is production-ready!" -ForegroundColor Green
} elseif ($passRate -ge 90) {
    Write-Host "  Most tests passed. Review failed tests above." -ForegroundColor Yellow
} else {
    Write-Host "  Significant failures detected. Review and fix before deployment." -ForegroundColor Red
}

Write-Host "`n" -NoNewline
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "`n"
