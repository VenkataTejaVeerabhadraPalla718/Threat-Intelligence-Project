$ErrorActionPreference = "Stop"
Write-Host "SENTINEL-X startup check" -ForegroundColor Cyan
docker --version
docker compose version
if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from template. Review it before continuing." -ForegroundColor Yellow }
docker compose up --build -d
Write-Host "Waiting 15 seconds for services..."
Start-Sleep -Seconds 15
docker compose ps -a
Write-Host "Dashboard: http://localhost:8000/" -ForegroundColor Green
Write-Host "Labs:      http://localhost:8000/dashboard" -ForegroundColor Green
Write-Host "Health:    http://localhost:8000/health" -ForegroundColor Green
