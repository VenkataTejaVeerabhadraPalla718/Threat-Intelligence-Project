$ErrorActionPreference = 'Continue'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host '=== SENTINEL-X diagnostics ===' -ForegroundColor Cyan
docker compose ps -a
Write-Host "`n--- API health ---"
try { Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 5 | ConvertTo-Json -Depth 5 } catch { Write-Host $_.Exception.Message -ForegroundColor Red }
Write-Host "`n--- Replica-set status (correct port: 27117) ---"
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "try { printjson(rs.status().members.map(m=>({host:m.name,state:m.stateStr,health:m.health}))); } catch(e) { print(e); quit(2); }"
Write-Host "`n--- Database and user counts ---"
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "const d=db.getSiblingDB('cti'); print('database=cti'); print('users='+d.users.countDocuments({})); print('threats='+d.threats.countDocuments({})); print('sources='+d.sources.countDocuments({})); print('lab_runs='+d.experiment_runs.countDocuments({}));"
Write-Host "`n--- API and Mongo logs ---"
docker compose logs --tail=35 api mongo-init
