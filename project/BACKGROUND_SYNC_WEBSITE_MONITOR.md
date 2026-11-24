# SENTINEL-X Background Threat Sync — Website Monitor

The `threat-sync` service is a long-running Docker worker. It performs scheduled incremental feed synchronization in the background. You do not need to keep `docker compose logs -f threat-sync` open.

## Website monitoring
1. Sign in to SENTINEL-X.
2. Open **Intelligence Sources**.
3. Select the schedule: 10 seconds, 30 seconds, 1 minute, 5 minutes, 10 minutes, or 30 minutes.
4. Select **Save schedule**.
5. The page automatically refreshes worker health, last sync, next scheduled run, interval, and recent sync events every five seconds.
6. Use **Run sync now** for an immediate manual run.

Recent activity is written to MongoDB collection `sync_events` and bounded to the latest 500 events. Worker heartbeat and next run time are stored in `platform_settings`. Threat data remains in the existing MongoDB collections and named volumes.

## Deploy on Windows PowerShell

Run from `B:\Projects\SENTINEL-X-FINAL\threat_intelligence_platform` after extracting this ZIP over the existing project and preserving `.env`:

```powershell
docker compose config --services
docker compose up -d --build --no-deps api threat-sync
docker compose ps -a
```

`--no-deps` is important when your MongoDB containers are already running under the same fixed names. It prevents Compose from attempting to recreate them.

Check once, if required:

```powershell
docker compose logs --tail 80 threat-sync
```

Routine monitoring should now be performed in the website, not by keeping a terminal log-follow session open.

## Important
- The worker runs only while Docker Desktop and its container are running.
- Changing the schedule in the website is persisted in MongoDB and picked up by the worker without a container restart.
- Do not use `docker compose down -v`, `docker volume prune`, or delete the MongoDB containers/volumes.
- The timeline selector on Overview controls the publication-date range used for threat analytics; the sync interval controls how often new feed items are collected. These are separate settings.
\n\n## Worker status heartbeat correction\nThe worker now refreshes its MongoDB heartbeat every 15 seconds while waiting for the next scheduled run. This prevents the website from showing WORKER NOT CONFIRMED merely because the worker is sleeping between scheduled synchronizations.\n