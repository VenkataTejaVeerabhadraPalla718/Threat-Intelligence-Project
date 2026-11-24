$ErrorActionPreference = "Stop"
$path = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $path)) {
    throw ".env was not found. Copy .env.example to .env first."
}
$text = Get-Content $path -Raw
if ($text -match '(?m)^OLLAMA_MODEL=.*$') {
    $text = [regex]::Replace($text, '(?m)^OLLAMA_MODEL=.*$', 'OLLAMA_MODEL=gemma4:12b')
} else {
    $text = $text.TrimEnd() + "`r`nOLLAMA_MODEL=gemma4:12b`r`n"
}
[System.IO.File]::WriteAllText((Resolve-Path $path), $text)
Write-Host "OLLAMA_MODEL set to gemma4:12b. JWT_SECRET and all other .env values were preserved."
