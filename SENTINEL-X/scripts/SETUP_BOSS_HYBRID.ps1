$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root '.env'
$examplePath = Join-Path $root '.env.example'

if (-not (Test-Path $envPath)) {
    if (Test-Path $examplePath) { Copy-Item $examplePath $envPath }
    else { New-Item -ItemType File -Path $envPath -Force | Out-Null }
}

$backupPath = "$envPath.boss-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $envPath $backupPath -Force
$lines = @(Get-Content $envPath -ErrorAction SilentlyContinue)

function Set-EnvLine([string]$Name, [string]$Value) {
    $script:lines = @($script:lines | Where-Object { $_ -notmatch ('^\s*' + [regex]::Escape($Name) + '\s*=') })
    $script:lines += "$Name=$Value"
}

$secure = Read-Host 'Paste your NEWLY ROTATED Ollama API key (input is hidden)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'API key cannot be empty.' }
    Set-EnvLine 'OLLAMA_API_KEY' $plain
}
finally {
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $plain = $null
}

Set-EnvLine 'ASSISTANT_CLOUD_ENABLED' 'true'
Set-EnvLine 'OLLAMA_URL' 'http://host.docker.internal:11434'
Set-EnvLine 'OLLAMA_LOCAL_MODEL' 'qwen3.5:4b'
Set-EnvLine 'OLLAMA_CLOUD_URL' 'https://ollama.com/api'
Set-EnvLine 'OLLAMA_CLOUD_MODEL' 'gemma4:31b'
Set-EnvLine 'OLLAMA_KEEP_ALIVE' '30m'
Set-EnvLine 'OLLAMA_NUM_CTX' '4096'
Set-EnvLine 'OLLAMA_NUM_PREDICT' '900'

[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host 'Hybrid Boss settings saved to .env. The API key was not printed.' -ForegroundColor Green
Write-Host "Previous .env backup: $backupPath" -ForegroundColor DarkGray
Write-Host 'Next: ollama pull qwen3.5:4b; then docker compose config --quiet; then docker compose up -d --build api.' -ForegroundColor Cyan
