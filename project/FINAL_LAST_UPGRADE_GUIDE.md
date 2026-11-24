# SENTINEL-X — Final Submission Upgrade

## What this final upgrade adds

- **Assistant response timing:** the chat displays the measured end-to-end response time. The Ollama request keeps the selected local model warm for 30 minutes, uses a focused 4,096-token context, and caps generation at 512 tokens to reduce avoidable latency. Lab-specific assistant sessions also receive concise Markdown reference material from the corresponding `labs/labN` folder when present.
- **Broader assistant behavior:** handles ordinary conversation, study questions, writing, programming, troubleshooting and Labs 7–18. Database facts are still answered through deterministic MongoDB queries when recognized; model-generated answers are instructed to state uncertainty instead of inventing facts.
- **Automatic threat synchronization:** the `threat-sync` service runs in the background, uses the saved interval (10s, 30s, 1m, 5m, 10m or 30m), and restarts automatically with Docker. Each completed run records its status, start/end time, elapsed milliseconds, sources checked, items checked and total stored threat count in MongoDB.
- **Dashboard timeline:** synced threat records retain their source publication timestamp. The overview's 7/30/90/365-day range and daily/weekly selector determine which published threats appear in the trend chart. The dashboard also shows the last sync status and duration. Threat records remain available in the Threat Intelligence page and dashboard metrics.
- **Data persistence:** MongoDB uses named Docker volumes (`mongo1_data`, `mongo2_data`, `mongo3_data`). Rebuilding/recreating the API and sync containers does not delete these volumes. Do not use `docker compose down -v` or remove the named volumes.
- **Previous safeguards retained:** JWT-protected assistant/history, per-user conversation scope, allow-listed lab execution and explicit confirmation for destructive registered experiments remain in place. The older Lab 15 chatbot is not replaced.

## Windows PowerShell installation

> Run these commands from the extracted project folder. Back up your existing folder first. Keep your existing `.env` file; it is intentionally not included in the ZIP.

1. Extract `SENTINEL_X_FINAL_SUBMISSION_LAST_UPGRADE.zip` to a new folder, for example `B:\Projects\SENTINEL-X-FINAL-LAST`.
2. Copy the `.env` file from your current working project into the newly extracted `threat_intelligence_platform` folder. Do not overwrite it with `.env.example`.
3. Open PowerShell in the new `threat_intelligence_platform` folder:

   ```powershell
   cd B:\Projects\SENTINEL-X-FINAL-LAST\threat_intelligence_platform
   ```

4. Confirm the environment file exists:

   ```powershell
   Test-Path .env
   ```

   It must return `True`.

5. Check the compose configuration and rebuild the API and background sync service:

   ```powershell
   docker compose config --quiet
   docker compose up -d --build api threat-sync
   ```

   Compose will start required dependencies if they are not already running. It reuses the named MongoDB volumes associated with this Compose project. Do not add `-v`.

6. Check container health:

   ```powershell
   docker compose ps
   docker logs --tail 80 sentinelx-local-api
   docker logs --tail 80 sentinelx-threat-sync
   ```

   The API should become healthy. The sync worker should log a sync attempt and then its next scheduled interval.

7. Check the API and Ollama status:

   ```powershell
   Invoke-RestMethod http://localhost:8000/health
   ```

   Sign in to SENTINEL-X and open the AI Assistant. The model badge should show Ollama/model readiness. Ask a question and check the elapsed-time label under the answer.

8. Open **Intelligence Sources**. Select the desired automatic sync interval and click **Save interval**. Use **Sync now** for an immediate manual sync. The last-sync status should show the completion time, sources, feed items and duration.

9. Open **Overview**. Select 7, 30, 90 or 365 days and Daily or Weekly. The threat trend is grouped by each record's published timestamp. Refresh the page after a background sync to load the latest stored counts.

10. Verify persistence safely: restart/rebuild only the application services and check the threat total again:

   ```powershell
   docker compose up -d --build api threat-sync
   Invoke-RestMethod http://localhost:8000/health
   ```

   Sign in and confirm the same threat records remain. The named MongoDB volumes must remain present.

## Important data-preservation rules

- Safe: `docker compose up -d --build api threat-sync`
- Safe: `docker compose restart api threat-sync`
- Safe: `docker compose down` (containers/network removed; named volumes remain)
- **Never run for this submission:** `docker compose down -v`, `docker volume rm ...`, `docker volume prune`, or `docker system prune`.
- Keep the existing `.env`, MongoDB named volumes and Ollama model files. The ZIP intentionally excludes secrets and local model files.
- Feed records are intelligence leads, not independently verified malware verdicts. The UI retains the feed-unverified provenance label; analysts should validate IOCs before acting on them.

## Realistic response-time expectations

The response-time label measures the complete browser request. Deterministic database lookups may finish quickly. Generative answers are produced by the local Ollama model and can take seconds or longer depending on CPU/GPU acceleration, available RAM, prompt length, model loading and answer length. A cold first request can be slower. No software-only change can guarantee millisecond generation from a 12B model on every computer, and model correctness still depends on the prompt and available evidence.

## Build checks performed for this package

- Python backend compilation: passed.
- Frontend JavaScript syntax check: passed.
- Automated project tests: 24 passed.
- These are static/unit checks in the packaging environment; a live Windows/Docker/Ollama run on the target laptop must still be confirmed after installation.
