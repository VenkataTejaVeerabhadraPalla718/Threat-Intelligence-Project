$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "`n[SENTINEL-X] Building updated local API image..." -ForegroundColor Cyan
docker compose build api
if ($LASTEXITCODE -ne 0) { throw "Docker image build failed." }

Write-Host "`n[SENTINEL-X] Confirming Kubernetes is available..." -ForegroundColor Cyan
kubectl get nodes
if ($LASTEXITCODE -ne 0) { throw "kubectl cannot reach Docker Desktop Kubernetes." }

Write-Host "`n[SENTINEL-X] Applying Lab16 Job..." -ForegroundColor Cyan
kubectl apply -f .\k8s\lab16-job.yaml
if ($LASTEXITCODE -ne 0) { throw "Could not apply Lab16 Job." }

Write-Host "`n[SENTINEL-X] Waiting for Lab16 to complete (up to 3 hours)..." -ForegroundColor Cyan
kubectl wait --for=condition=complete job/sentinelx-lab16 --timeout=10800s
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nLab16 did not complete. Recent logs:" -ForegroundColor Red
    kubectl logs job/sentinelx-lab16 --all-containers=true
    throw "Lab18 was NOT started because Lab16 did not succeed."
}

Write-Host "`n[SENTINEL-X] Lab16 completed. Applying Lab18..." -ForegroundColor Green
kubectl apply -f .\k8s\lab18-job.yaml
if ($LASTEXITCODE -ne 0) { throw "Could not apply Lab18 Job." }

Write-Host "`n[SENTINEL-X] Waiting for Lab18 benchmark (up to 1 hour)..." -ForegroundColor Cyan
kubectl wait --for=condition=complete job/sentinelx-lab18 --timeout=3600s
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nLab18 logs:" -ForegroundColor Red
    kubectl logs job/sentinelx-lab18 --all-containers=true
    throw "Lab18 failed. Lab16 remains completed."
}

Write-Host "`n[SENTINEL-X] Both Kubernetes jobs completed." -ForegroundColor Green
Write-Host "`n--- Lab16 logs ---"
kubectl logs job/sentinelx-lab16 --all-containers=true
Write-Host "`n--- Lab18 logs ---"
kubectl logs job/sentinelx-lab18 --all-containers=true
