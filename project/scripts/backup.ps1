# SENTINEL-X backup: dumps the 'cti' database from the running replica set to .\backups\
# Safe: read-only on MongoDB, never touches Docker volumes.   Usage:  .\scripts\backup.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$name  = "sentinelx-cti-$stamp.archive.gz"
New-Item -ItemType Directory -Force -Path backups | Out-Null
docker exec sentinelx-local-mongo1 mongodump --host "rs0/mongo1:27117,mongo2:27118,mongo3:27119" --db cti --gzip --archive="/tmp/$name"
if ($LASTEXITCODE -ne 0) { throw 'mongodump failed. Is the stack running? (docker compose ps)' }
docker cp "sentinelx-local-mongo1:/tmp/$name" "backups\$name"
docker exec sentinelx-local-mongo1 rm -f "/tmp/$name"
Write-Host "Backup written: backups\$name" -ForegroundColor Green
Write-Host "Restore (OVERWRITES collections in 'cti'; only run when you mean it):"
Write-Host "  docker cp backups\$name sentinelx-local-mongo1:/tmp/$name"
Write-Host "  docker exec sentinelx-local-mongo1 mongorestore --host rs0/mongo1:27117 --gzip --archive=/tmp/$name --drop"
