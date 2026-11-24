# SENTINEL-X — fresh setup (Windows 11 + Docker Desktop)

This bundle combines the integrated Labs 7–18 workspace, the enterprise console, local Ollama assistant, MongoDB threat analytics, lab execution registry, and the multi-user/admin API upgrade.

## 1. Extract
Extract the ZIP so the folder is:

`B:\Projects\SENTINEL-X-FINAL\threat_intelligence_platform`

If replacing an existing folder, copy your `.env` and any custom certificates/data files aside first. **Do not delete Docker volumes.** The Compose project is named `sentinelx`; existing `mongo1_data`, `mongo2_data`, and `mongo3_data` volumes are reused when you run it from the same project directory.

## 2. Start
Open PowerShell in `threat_intelligence_platform` and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\START_SENTINELX_FRESH.ps1
```

The script creates `.env` only when absent, generates a unique JWT secret, preserves an existing `.env`, validates Compose, builds services, and waits for `/health`.

## 3. Create your administrator
After the API becomes healthy, run:

```powershell
docker exec -it sentinelx-local-api python /app/backend/bootstrap_admin.py
```

Enter a username and a password of at least 12 characters. Password input is hidden. If the username already exists, the script promotes that account without changing its password. If it does not exist, it creates the first administrator in the selected tenant.

## 4. Sign in / create normal users
- API docs: http://localhost:8000/docs
- Login: `POST /api/auth/login` with `{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}`
- Current account: `GET /api/auth/me`
- Admin user list: `GET /api/admin/users`
- Admin create user: `POST /api/admin/users` with `{"username":"student2","password":"Use-A-Long-Unique-Password","role":"user"}`
- Admin update role/active: `PATCH /api/admin/users/student2` with `{"role":"user","active":true}`
- Admin delete: `DELETE /api/admin/users/student2`

Use the returned access token as `Bearer <token>` in Swagger's Authorize dialog.

## 5. Correct MongoDB shell command
Each MongoDB node listens on a non-default port. The first node listens on **27117**, not 27017. Always include the port:

```powershell
docker exec -it sentinelx-local-mongo1 mongosh --port 27117 --quiet
```

List databases:

```powershell
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "db.adminCommand({listDatabases:1}).databases.map(x=>x.name)"
```

Inspect users in the platform database (`cti`):

```powershell
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "db.getSiblingDB('cti').users.find({}, {_id:0,username:1,role:1,tenant_id:1,active:1}).toArray()"
```

## 6. Local assistant
The assistant runs through Ollama on the Windows host. Ensure Ollama is running and the configured model exists:

```powershell
ollama list
ollama pull gemma4:12b
```

If you use a different installed model, edit `OLLAMA_MODEL` in `.env`, then run:

```powershell
docker compose up -d --force-recreate api
```

Assistant page: http://localhost:8000/console?page=assistant

It can answer ordinary questions and explain/diagnose Labs 7–18. MongoDB threat count, severity, category, source and threat-search questions use deterministic database queries. General questions use the local Ollama model. It only executes registered lab scripts; destructive experiments require an explicit confirmation.

## 7. Diagnostics

```powershell
.\CHECK_SENTINELX.ps1
```

Useful logs:

```powershell
docker compose logs --tail=100 api
docker compose logs --tail=100 mongo-init
docker compose ps -a
```

## Safety and scope notes
- Never run `docker compose down -v` unless you intentionally want to delete the database volumes.
- Lab 15's seed script in this bundle is non-destructive: it uses upserts and does not drop the `users` or `tasks` collections.
- Synthetic threat records are explicitly labeled as demo data, not verified real-world incidents.
- The API includes admin-only user-management endpoints. The existing enterprise console does not yet provide a complete graphical login/admin-user-management screen, and not every lab/sync/export route is protected by JWT. Keep this deployment on localhost/trusted LAN for coursework; do not expose it publicly as a production SaaS service.
- Labs 11–13 and 16–18 may require optional dedicated sharding, TLS/keyfile, Cassandra, Neo4j or Atlas Local services. Their workspaces and integration notes are included; optional stacks are not automatically started by the base profile.
- No one can guarantee zero errors across different Windows/Docker/Ollama environments. This package has been syntax-checked and its setup/diagnostic commands are included to make any remaining environment issue identifiable without wiping data.
