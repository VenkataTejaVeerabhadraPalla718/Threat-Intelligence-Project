$ErrorActionPreference = "Stop"
$Root = (Get-Location).Path
$LabsRoot = Join-Path $Root "Labs"
$SentinelRoot = Join-Path $Root "SENTINEL-X"
if (!(Test-Path $LabsRoot)) { throw "Run this script from github-upload; Labs folder not found." }

function Rel($base,$path) { $path.Substring($base.Length).TrimStart('\','/') }
function Tech($files) {
  $e = @($files.Extension | ForEach-Object { $_.ToLower() } | Sort-Object -Unique)
  $n = @($files.Name | ForEach-Object { $_.ToLower() })
  $t = @()
  if ($e -contains ".py") {$t += "Python"}
  if ($e -contains ".ipynb") {$t += "Jupyter Notebook"}
  if ($e -contains ".js") {$t += "JavaScript"}
  if ($e -contains ".ts" -or $e -contains ".tsx") {$t += "TypeScript"}
  if ($e -contains ".html") {$t += "HTML"}
  if ($e -contains ".css") {$t += "CSS"}
  if ($e -contains ".java") {$t += "Java"}
  if ($e -contains ".c") {$t += "C"}
  if ($e -contains ".cpp") {$t += "C++"}
  if ($e -contains ".sql") {$t += "SQL"}
  if ($n -contains "dockerfile" -or $n -contains "docker-compose.yml" -or $n -contains "compose.yaml") {$t += "Docker / Docker Compose"}
  if ($n -contains "package.json") {$t += "Node.js"}
  if ($n -contains "requirements.txt" -or $n -contains "pyproject.toml") {$t += "Python dependency management"}
  if ($n -match "mongo") {$t += "MongoDB-related files detected"}
  return @($t | Sort-Object -Unique)
}
function MakeLab($d) {
  $readme = Join-Path $d.FullName "README.md"
  $old = if (Test-Path $readme) { Get-Content $readme -Raw } else { "" }
  $files = @(Get-ChildItem $d.FullName -Recurse -File | Where-Object {$_.Name -ne "README.md" -and $_.FullName -notmatch '\\(node_modules|\.venv|venv|__pycache__|\.git)\\'})
  $lines = [System.Collections.Generic.List[string]]::new()
  $lines.Add("# $($d.Name) — Detailed Lab Guide"); $lines.Add("")
  $lines.Add("> Generated from the files present in this lab folder. Verify the exact aim, dataset, entry point and expected output against the official lab sheet."); $lines.Add("")
  $lines.Add("## 1. Aim and objectives"); $lines.Add("")
  $lines.Add("**Aim:** Replace this line with the exact aim from the official exercise sheet."); $lines.Add("")
  $lines.Add("- Understand the concepts implemented in this exercise.")
  $lines.Add("- Configure and execute the required tools.")
  $lines.Add("- Verify the result against the official expected output."); $lines.Add("")
  if ($old.Trim()) {$lines.Add("## 2. Previous README notes"); $lines.Add(""); $lines.Add($old.Trim()); $lines.Add("")}
  $lines.Add("## 3. Technologies detected"); $lines.Add("")
  $tech = @(Tech $files); if ($tech.Count) {$tech | ForEach-Object {$lines.Add("- $_")}} else {$lines.Add("- No technology could be inferred from file extensions; inspect the source manually." )}; $lines.Add("")
  $lines.Add("## 4. File inventory"); $lines.Add("")
  foreach ($f in ($files | Sort-Object FullName)) {$lines.Add("- ``$(Rel $d.FullName $f.FullName)``")}; $lines.Add("")
  $lines.Add("## 5. Prerequisites and setup"); $lines.Add("")
  $lines.Add("- Windows PowerShell.")
  $lines.Add("- Install the runtime indicated by the detected source files (Python, Java, Node.js, Docker, etc.).")
  $lines.Add("- For Python, use a virtual environment and install the dependencies listed in this lab.")
  $lines.Add("- For MongoDB exercises, start the MongoDB service/container and use the URI configured by the lab.")
  $lines.Add("- Never put passwords, tokens, private keys or `.env` contents in this README."); $lines.Add("")
  $lines.Add("## 6. Execution commands"); $lines.Add("")
  $lines.Add("Run from PowerShell. These are safe starting commands inferred from files; select the correct application entry point from the lab source/instructions."); $lines.Add("")
  $lines.Add('```powershell')
  $lines.Add("Set-Location `"$($d.FullName)`"")
  if (Test-Path (Join-Path $d.FullName "requirements.txt")) {$lines.Add("py -m venv .venv");$lines.Add(".\.venv\Scripts\Activate.ps1");$lines.Add("py -m pip install -r requirements.txt")}
  if (Test-Path (Join-Path $d.FullName "package.json")) {$lines.Add("npm install");$lines.Add("# See package.json scripts, then run the appropriate command, e.g. npm run dev")}
  if ((Test-Path (Join-Path $d.FullName "docker-compose.yml")) -or (Test-Path (Join-Path $d.FullName "compose.yaml"))) {$lines.Add("docker compose config");$lines.Add("docker compose up -d --build");$lines.Add("docker compose ps");$lines.Add("docker compose logs --tail 100")}
  $py = @($files | Where-Object {$_.Extension -eq ".py" -and $_.Name -notmatch "test|config|setup|__init__"})
  if ($py.Count -eq 1) {$lines.Add("py `"$($py[0].Name)`"")}
  elseif ($py.Count -gt 1) {$lines.Add("# Python files detected: " + (($py.Name) -join ", "));$lines.Add("# Check the lab instructions/source to choose the intended entry point; do not run every file.")}
  if (@($files | Where-Object {$_.Extension -eq ".ipynb"}).Count -gt 0) {$lines.Add("py -m pip install notebook");$lines.Add("jupyter notebook");$lines.Add("# Open the notebook and run cells in order.")}
  if ($lines.Count -lt 20) {$lines.Add("# No standard run command inferred. Follow the official lab instructions and inspect the source files.")}
  if ((Test-Path (Join-Path $d.FullName "docker-compose.yml")) -or (Test-Path (Join-Path $d.FullName "compose.yaml"))) {$lines.Add("docker compose down");$lines.Add("# Do not use -v for routine shutdown; it deletes named volumes.")}
  $lines.Add('```');$lines.Add("")
  $lines.Add("## 7. Expected output and verification");$lines.Add("")
  $lines.Add("- Record the actual terminal/notebook/database output produced by this lab.")
  $lines.Add("- Compare output with the official lab sheet; this README generator does not invent results.")
  $lines.Add("- Add screenshots and explain what each output demonstrates.");$lines.Add("")
  $lines.Add("## 8. Troubleshooting");$lines.Add("")
  $lines.Add("| Issue | Check |");$lines.Add("|---|---|")
  $lines.Add("| Command not found | Confirm runtime installation and PATH. |")
  $lines.Add("| Python module missing | Activate the correct venv and install requirements. |")
  $lines.Add("| MongoDB connection refused | Check service/container, host, port and URI. |")
  $lines.Add("| Docker unavailable | Start Docker Desktop and wait for engine readiness. |")
  $lines.Add("| Port conflict | Identify the process using the port before changing configuration. |")
  $lines.Add("| Authentication failure | Check local credentials; never publish them. |");$lines.Add("")
  $lines.Add("## 9. Cleanup and data safety");$lines.Add("")
  $lines.Add("- Stop only the processes/containers started for this lab.")
  $lines.Add("- Preserve database volumes and datasets unless a reset is explicitly required.")
  $lines.Add("- Avoid `docker compose down -v`, `docker volume prune` and destructive database commands for routine cleanup.");$lines.Add("")
  $lines.Add("## 10. Completion checklist");$lines.Add("")
  $lines.Add("- [ ] Aim/objectives match the official lab sheet.")
  $lines.Add("- [ ] Tool versions and prerequisites are recorded.")
  $lines.Add("- [ ] Commands have been tested.")
  $lines.Add("- [ ] Actual outputs/screenshots are included.")
  $lines.Add("- [ ] No credentials or private data are committed.")
  $lines | Set-Content $readme -Encoding UTF8
  Write-Host "Updated $readme"
}
$labs = @(Get-ChildItem $LabsRoot -Directory | Where-Object {$_.Name -match '^Lab[-_ ]?\d+'} | Sort-Object Name)
if (!$labs.Count) {throw "No Lab-XX folders found."}
foreach ($d in $labs) {MakeLab $d}

if (Test-Path $SentinelRoot) {
  $files = @(Get-ChildItem $SentinelRoot -Recurse -File | Where-Object {$_.FullName -notmatch '\\(node_modules|\.venv|venv|__pycache__|\.git|data|mongodb|backups)\\'})
  $lines = [System.Collections.Generic.List[string]]::new()
  $lines.Add("# SENTINEL-X — Complete Technical and Execution Guide");$lines.Add("")
  $lines.Add("## 1. Project overview");$lines.Add("")
  $lines.Add("Integrated threat-intelligence platform. Confirm each feature against the actual backend routes, frontend and Compose configuration.");$lines.Add("")
  $lines.Add("## 2. Technologies detected");$lines.Add("")
  foreach ($t in (Tech $files)) {$lines.Add("- $t")};$lines.Add("")
  $lines.Add("## 3. Component map");$lines.Add("")
  foreach ($folder in @("backend","frontend","docker","k8s","scripts","docs")) {if (Test-Path (Join-Path $SentinelRoot $folder)) {$lines.Add("- ``$folder/`` — inspect its source/configuration for the implemented responsibilities.")}};$lines.Add("")
  $lines.Add("## 4. Prerequisites");$lines.Add("")
  $lines.Add("- Windows 10/11 and PowerShell.")
  $lines.Add("- Docker Desktop with Linux containers enabled.")
  $lines.Add("- Git for cloning/updating.")
  $lines.Add("- Python if running backend outside Docker.")
  $lines.Add("- Ollama and the configured model(s), if local LLM functionality is enabled.")
  $lines.Add("- Credentials only for integrations explicitly enabled in configuration.");$lines.Add("")
  $lines.Add("## 5. Environment setup");$lines.Add("")
  $lines.Add("1. Inspect `.env.example`, `docker-compose.yml` and backend settings.")
  $lines.Add("2. Create a local `.env` using the variable names required by the application.")
  $lines.Add("3. Never commit `.env`, tokens, passwords, database keyfiles, certificates or backups.")
  $lines.Add("4. Confirm host ports, service names, database URIs and model names from the Compose file.");$lines.Add("")
  $lines.Add("## 6. Start the core stack");$lines.Add("")
  $lines.Add('```powershell')
  $lines.Add("Set-Location `"$SentinelRoot`"")
  $lines.Add("docker compose config")
  $lines.Add("docker compose up -d --build")
  $lines.Add("docker compose ps")
  $lines.Add("docker compose logs --tail 100")
  $lines.Add('```');$lines.Add("")
  $lines.Add("## 7. Verify API and database");$lines.Add("")
  $lines.Add('```powershell')
  $lines.Add("docker compose ps")
  $lines.Add("docker compose logs --tail 100 api")
  $lines.Add("Invoke-RestMethod http://localhost:8000/health")
  $lines.Add("Invoke-RestMethod http://localhost:8000/openapi.json")
  $lines.Add('```');$lines.Add("")
  $lines.Add("Run endpoint checks only when those routes exist in the current backend. Check MongoDB container health and replica-set status using the connection details configured in Compose.");$lines.Add("")
  $lines.Add("## 8. LLM, embeddings, vector search and RAG");$lines.Add("")
  $lines.Add("Document the exact LLM provider/model, embedding model, chunking logic, MongoDB database/collection, vector index, chat route, request schema and history storage after confirming them in source. A model name or dependency alone does not prove that a feature is wired and operational.");$lines.Add("")
  $lines.Add("## 9. Frontend and deployment");$lines.Add("")
  $lines.Add("- Check frontend API base URL and backend CORS configuration.")
  $lines.Add("- Static hosting alone cannot run FastAPI, MongoDB, Docker Compose or a local Ollama server.")
  $lines.Add("- A public frontend needs a separately deployed, reachable and secured backend.")
  $lines.Add("- Do not expose unauthenticated MongoDB ports publicly.");$lines.Add("")
  $lines.Add("## 10. Monitoring and troubleshooting");$lines.Add("")
  $lines.Add('```powershell')
  $lines.Add("docker compose ps")
  $lines.Add("docker compose logs -f api")
  $lines.Add("docker compose logs --tail 200")
  $lines.Add("docker stats")
  $lines.Add("Test-NetConnection localhost -Port 8000")
  $lines.Add('```');$lines.Add("")
  $lines.Add("Check Docker engine, environment variables, port conflicts, container health, MongoDB initialization, LLM availability and API logs.");$lines.Add("")
  $lines.Add("## 11. Safe shutdown");$lines.Add("")
  $lines.Add('```powershell')
  $lines.Add("docker compose stop")
  $lines.Add("# Or remove containers/network while preserving named volumes:")
  $lines.Add("docker compose down")
  $lines.Add("# Do not append -v for routine shutdown.")
  $lines.Add('```');$lines.Add("")
  $lines.Add("## 12. Source inventory");$lines.Add("")
  foreach ($f in ($files | Sort-Object FullName)) {$lines.Add("- ``$(Rel $SentinelRoot $f.FullName)``")};$lines.Add("")
  $lines.Add("## 13. Security checklist");$lines.Add("")
  $lines.Add("- [ ] Revoke and rotate any credential previously exposed.")
  $lines.Add("- [ ] `.env` and private keys are excluded from Git.")
  $lines.Add("- [ ] MongoDB is not publicly exposed without authentication/TLS.")
  $lines.Add("- [ ] Production API uses authentication, rate limits and HTTPS.")
  $lines.Add("- [ ] Logs do not disclose credentials.")
  $lines | Set-Content (Join-Path $SentinelRoot "README.md") -Encoding UTF8
  Write-Host "Updated $SentinelRoot\README.md"
}

$root = [System.Collections.Generic.List[string]]::new()
$root.Add("# Threat Intelligence Project — Documentation");$root.Add("")
$root.Add("## Repository contents");$root.Add("")
$root.Add("This repository contains the NoSQL lab exercises and integrated SENTINEL-X project. Each lab has a dedicated guide.");$root.Add("")
$root.Add("## Lab index");$root.Add("")
foreach ($d in $labs) {$root.Add("- [$($d.Name)](Labs/$($d.Name)/README.md)")}
$root.Add("");$root.Add("## Integrated project");$root.Add("")
$root.Add("- [SENTINEL-X guide](SENTINEL-X/README.md)")
$root.Add("");$root.Add("## Clone");$root.Add("")
$root.Add('```powershell')
$root.Add("git clone https://github.com/VenkataTejaVeerabhadraPalla718/Threat-Intelligence-Project.git")
$root.Add("Set-Location .\Threat-Intelligence-Project")
$root.Add('```');$root.Add("")
$root.Add("## Important notes");$root.Add("")
$root.Add("- Verify inferred commands and entry points against each exercise's official lab sheet.")
$root.Add("- Add actual expected outputs and screenshots; no results are fabricated.")
$root.Add("- Never commit secrets, `.env`, private keys, backups or database files.")
$root.Add("- Use `docker compose down` for routine shutdown; avoid `-v` to preserve volumes.")
$root | Set-Content (Join-Path $Root "README.md") -Encoding UTF8

Write-Host "Completed. Lab folders documented: $($labs.Count)" -ForegroundColor Green
Write-Host "Review all generated READMEs before committing."
