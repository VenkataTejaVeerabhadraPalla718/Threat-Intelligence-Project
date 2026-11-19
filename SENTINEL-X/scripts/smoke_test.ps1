# SENTINEL-X live API smoke test (Windows PowerShell 5.1 or PowerShell 7).
# Creates a throw-away user, exercises auth/RBAC/audit endpoints, then optionally verifies admin features.
# Usage:  .\scripts\smoke_test.ps1            (admin checks are skipped if you press Enter at the prompt)
param([string]$Base = 'http://localhost:8000')
$ErrorActionPreference = 'Stop'
$script:pass = 0; $script:fail = 0
function Check($name, [scriptblock]$test) {
  try { if (& $test) { Write-Host "PASS  $name" -ForegroundColor Green; $script:pass++ } else { Write-Host "FAIL  $name" -ForegroundColor Red; $script:fail++ } }
  catch { Write-Host "FAIL  $name :: $($_.Exception.Message)" -ForegroundColor Red; $script:fail++ }
}
function Status([scriptblock]$call) { try { & $call | Out-Null; return 200 } catch { if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } else { throw } } }
function Json($body) { $body | ConvertTo-Json -Compress }
function Hdr($t) { @{ Authorization = "Bearer $t" } }

$user = 'smoke_' + (Get-Random -Maximum 99999999); $pw = 'Smk-' + [guid]::NewGuid().ToString('N')
Check 'health endpoint reports ok' { (Invoke-RestMethod "$Base/health").status -eq 'ok' }
# Safety guard: abort if the running API is not the upgraded build (an old build would run experiments for any user).
$ver = Status { Invoke-RestMethod "$Base/api/overview" }
if ($ver -ne 401) {
  Write-Host "ABORTED: /api/overview returned $ver (expected 401). The running API is an OLD build. Rebuild with:" -ForegroundColor Red
  Write-Host "  docker compose build --no-cache api ; docker compose up -d api" -ForegroundColor Yellow
  exit 2
}
Check 'assistant streaming endpoint requires sign-in (401)' { (Status { Invoke-RestMethod "$Base/api/assistant/stream" -Method Post -ContentType 'application/json' -Body (Json @{ message = 'hi' }) }) -eq 401 }
Check 'unauthenticated /api/threats is rejected (401)' { (Status { Invoke-RestMethod "$Base/api/threats" }) -eq 401 }
Check 'unauthenticated /api/export/threats.csv is rejected (401)' { (Status { Invoke-RestMethod "$Base/api/export/threats.csv" }) -eq 401 }
Check 'registration with a short password is rejected (400)' { (Status { Invoke-RestMethod "$Base/api/auth/register" -Method Post -ContentType 'application/json' -Body (Json @{ username = $user; password = 'short' }) }) -eq 400 }
Check 'registration succeeds (201)' { (Invoke-RestMethod "$Base/api/auth/register" -Method Post -ContentType 'application/json' -Body (Json @{ username = $user; password = $pw })).role -eq 'user' }
Check 'duplicate registration is rejected (409)' { (Status { Invoke-RestMethod "$Base/api/auth/register" -Method Post -ContentType 'application/json' -Body (Json @{ username = $user; password = $pw }) }) -eq 409 }
Check 'wrong password is rejected (401)' { (Status { Invoke-RestMethod "$Base/api/auth/login" -Method Post -ContentType 'application/json' -Body (Json @{ username = $user; password = 'wrong-password-123' }) }) -eq 401 }
$login = Invoke-RestMethod "$Base/api/auth/login" -Method Post -ContentType 'application/json' -Body (Json @{ username = $user; password = $pw })
$h = Hdr $login.access_token
Check 'login returns a token and role=user' { $login.access_token -and $login.role -eq 'user' }
Check '/api/auth/me works' { (Invoke-RestMethod "$Base/api/auth/me" -Headers $h).username -eq $user }
Check 'normal user cannot reach /api/admin/users (403)' { (Status { Invoke-RestMethod "$Base/api/admin/users" -Headers $h }) -eq 403 }
Check 'normal user cannot run experiments (403)' { (Status { Invoke-RestMethod "$Base/api/dashboard/run/l8-repl" -Method Post -Headers $h }) -eq 403 }
Check '/api/threats works for a signed-in user' { $null -ne (Invoke-RestMethod "$Base/api/threats?limit=1" -Headers $h).total }
Check '/api/overview returns KPIs' { $null -ne (Invoke-RestMethod "$Base/api/overview" -Headers $h).kpis.total }
Check '/api/labs lists 12 labs' { (Invoke-RestMethod "$Base/api/labs" -Headers $h).labs.Count -eq 12 }
Check '/api/assistant/status responds' { $null -ne (Invoke-RestMethod "$Base/api/assistant/status" -Headers $h).ok }
Check 'logout invalidates the token (401 afterwards)' { Invoke-RestMethod "$Base/api/auth/logout" -Method Post -Headers $h | Out-Null; (Status { Invoke-RestMethod "$Base/api/auth/me" -Headers $h }) -eq 401 }

$adminUser = Read-Host 'Administrator username for admin checks (Enter to skip)'
if ($adminUser) {
  $sec = Read-Host 'Administrator password' -AsSecureString
  $adminPw = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
  $a = Invoke-RestMethod "$Base/api/auth/login" -Method Post -ContentType 'application/json' -Body (Json @{ username = $adminUser; password = $adminPw })
  $ah = Hdr $a.access_token
  Check 'admin summary is available' { $null -ne (Invoke-RestMethod "$Base/api/admin/summary" -Headers $ah).users_total }
  Check 'audit log recorded the smoke user events' { (Invoke-RestMethod "$Base/api/admin/login-activity?username=$user" -Headers $ah).total -ge 3 }
  Check 'audit log recorded the failed login with a reason' { (Invoke-RestMethod "$Base/api/admin/login-activity?username=$user&success=false" -Headers $ah).results[0].reason -eq 'wrong_password' }
  Check 'audit CSV export has a header row' { (Invoke-WebRequest "$Base/api/admin/login-activity.csv" -Headers $ah -UseBasicParsing).Content -match 'created_at,event_type,username' }
  Check 'security monitoring endpoint responds' { $null -ne (Invoke-RestMethod "$Base/api/admin/security" -Headers $ah).thresholds }
  Check 'admin cannot disable their own account (400)' { (Status { Invoke-RestMethod "$Base/api/admin/users/$adminUser" -Method Patch -Headers $ah -ContentType 'application/json' -Body (Json @{ role = 'admin'; active = $false }) }) -eq 400 }
  Check 'smoke user can be removed by the admin' { (Invoke-RestMethod "$Base/api/admin/users/$user" -Method Delete -Headers $ah).ok }
}
Write-Host ("`nResult: {0} passed, {1} failed" -f $script:pass, $script:fail) -ForegroundColor $(if ($script:fail) { 'Red' } else { 'Green' })
if ($script:fail) { exit 1 }
