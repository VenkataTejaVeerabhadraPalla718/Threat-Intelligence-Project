# SENTINEL-X — Visible Upgrade Installation (Windows PowerShell)

This update makes the AI timing and sync-worker state visible in the primary enterprise console and gives the sync container a stable name. It also records partial feed failures separately from complete success.

## 1. Back up and replace the project files

Close the application tab. Back up `B:\Projects\SENTINEL-X-FINAL\threat_intelligence_platform`. Extract this ZIP into `B:\Projects\SENTINEL-X-FINAL` and allow files to be overwritten. **Do not delete or replace your existing `.env` file.**

## 2. Open PowerShell in the existing project folder

```powershell
cd B:\Projects\SENTINEL-X-FINAL\threat_intelligence_platform
Test-Path .env
docker compose config --services
```

`Test-Path .env` must return `True`. The services should include `api` and `threat-sync`.

## 3. Rebuild only the API and threat-sync worker

```powershell
docker compose up -d --build api threat-sync
```

Do not run `docker compose down -v`, `docker volume prune`, or `docker system prune`. The MongoDB named volumes contain your threat and lab data.

## 4. Confirm both containers

```powershell
docker compose ps -a
docker logs --tail 80 sentinelx-local-api
docker logs --tail 80 sentinelx-threat-sync
```

The sync worker should log feed checks and its next selected interval. The fixed container name is `sentinelx-threat-sync`.

## 5. Confirm the UI build was refreshed

```powershell
(Invoke-WebRequest http://localhost:8000/ -UseBasicParsing).Content | Select-String '20261115-final2'
```

Then open `http://localhost:8000`, sign in, and press `Ctrl+F5`.

## 6. What should now be visible

- Overview: **Automatic intelligence sync** panel shows worker state/heartbeat, last completion time, feed items, successful sources, failed sources and sync duration.
- Overview: choose 7/30/90/365 days and Daily/Weekly to change the threat timeline. The timeline is grouped by each threat's `published_at` date.
- AI Assistant: badge reads **ADVANCED AI READY** when Ollama/model are reachable; the assistant context identifies general chat and Labs 7–18. Every answer displays elapsed milliseconds or seconds, including fast database-tool answers.
- Threat records are incrementally upserted by URL and retained in MongoDB named volumes.

## 7. Verify actual synchronization

```powershell
docker compose logs --tail 120 threat-sync
Invoke-RestMethod http://localhost:8000/health
```

In the application, open Overview and refresh after a sync. If all sources cannot be reached, the status now reports partial failure rather than incorrectly reporting complete success.

## Important

The assistant uses your configured local Ollama model. The interface reports actual elapsed time; model-generated answers are typically seconds, not guaranteed milliseconds. The worker only runs while Docker is running. Existing threat data survives API/worker rebuilds as long as the MongoDB volumes are retained.


## Background sync website monitor
See `BACKGROUND_SYNC_WEBSITE_MONITOR.md`. Use `docker compose up -d --build --no-deps api threat-sync` when MongoDB containers are already running. Monitor scheduled syncs from Intelligence Sources; no terminal log-follow window is required.
