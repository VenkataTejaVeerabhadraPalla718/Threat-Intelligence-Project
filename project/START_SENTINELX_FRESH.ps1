$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host '=== SENTINEL-X | Fresh setup and safe rebuild ===' -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI was not found. Install/start Docker Desktop, then rerun this script.' }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running. Start Docker Desktop and rerun this script.' }

if (-not (Test-Path '.env')) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    @(
        "JWT_SECRET=$secret"
        'MONGO_URI=mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0'
        'OLLAMA_URL=http://host.docker.internal:11434'
        'OLLAMA_MODEL=gemma4:12b'
        'EMBED_MODEL=nomic-embed-text'
        'SYNC_INTERVAL_MINUTES=15'
    ) | Set-Content -Path '.env' -Encoding ascii
    Write-Host 'Created .env with a unique JWT secret.' -ForegroundColor Green
} else {
    Write-Host 'Existing .env preserved.' -ForegroundColor Yellow
    $envText = Get-Content '.env' -Raw
    if ($envText -match '(?m)^JWT_SECRET=CHANGE_ME\s*$' -or $envText -notmatch '(?m)^JWT_SECRET=.{32,}') {
        throw 'Your existing .env has a missing/weak JWT_SECRET. Back up .env, then replace JWT_SECRET with a unique random value of at least 32 characters.'
    }
}

Write-Host 'Validating Compose configuration...'
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'docker compose config failed. Review the error above.' }

Write-Host 'Building and starting the integrated platform. Existing named volumes are preserved...'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Run: docker compose logs --tail=100 mongo-init api' }

Write-Host 'Waiting for API health (up to 90 seconds)...'
$healthy = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $r = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 3
        if ($r.status -eq 'ok') { $healthy = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    docker compose ps -a
    throw 'API did not become healthy. Run CHECK_SENTINELX.ps1 and share its output; do not delete volumes.'
}

Write-Host ''
Write-Host 'SENTINEL-X is responding at http://localhost:8000/console' -ForegroundColor Green
Write-Host 'Swagger: http://localhost:8000/docs'
Write-Host ''
Write-Host 'NEXT: Create/promote your administrator account (password input is hidden):' -ForegroundColor Cyan
Write-Host 'docker exec -it sentinelx-local-api python /app/backend/bootstrap_admin.py'
Write-Host ''
Write-Host 'MongoDB shell uses port 27117. Do not omit --port:' -ForegroundColor Yellow
Write-Host 'docker exec -it sentinelx-local-mongo1 mongosh --port 27117 --quiet'
