param(
  [string]$OutputRoot = ".\backups\manual",
  [string]$Container = "sentinelx-local-mongo1"
)
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dest = Join-Path $OutputRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Write-Host "Creating a logical MongoDB backup in $dest"
docker exec $Container mongodump --port 27117 --archive --gzip |
  Set-Content -Encoding Byte -Path (Join-Path $dest "mongo1.archive.gz")
if ($LASTEXITCODE -ne 0) { throw "mongodump failed; original volumes were not changed." }
Write-Host "Backup created. No volumes or containers were removed."
