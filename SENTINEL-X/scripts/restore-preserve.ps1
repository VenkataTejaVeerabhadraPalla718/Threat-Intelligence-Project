param(
 [Parameter(Mandatory=$true)][string]$Archive,
 [string]$Container="sentinelx-local-mongo1"
)
$ErrorActionPreference="Stop"
if (!(Test-Path -LiteralPath $Archive)) { throw "Archive not found: $Archive" }
Write-Host "WARNING: restore writes into MongoDB and can overwrite matching documents."
$confirm=Read-Host "Type RESTORE to continue"
if ($confirm -cne "RESTORE") { Write-Host "Cancelled. No changes made."; exit 0 }
Get-Content -LiteralPath $Archive -Encoding Byte | docker exec -i $Container mongorestore --port 27117 --archive --gzip --drop
if ($LASTEXITCODE -ne 0) { throw "Restore failed. Inspect logs and validate data." }
