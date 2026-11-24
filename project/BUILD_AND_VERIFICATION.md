# SENTINEL-X build and verification notes

## Included
- Integrated Labs 07–18 and their existing experiment scripts/reports.
- FastAPI backend, MongoDB replica-set Compose stack, threat dashboard, threat intelligence views, local Ollama assistant, and lab runner.
- Multi-user registration and login endpoints, hashed passwords, JWT authentication, admin-only user management, and login-activity audit endpoints.
- Updated authentication screen: full-screen dark background with a centered credentials card only. No project branding, descriptive copy, left panel, or API-help link is shown on the login/register screens.
- Sidebar workspace navigation, expandable Labs 07–18 section, source/sync view, and administrator audit view.

## Static checks performed for this package
- Python syntax compilation: `backend/`, `docker/`, and `labs/` passed `python -m compileall`.
- Inline JavaScript syntax: passed `node --check`.
- Lab directory presence: all twelve directories `lab07` through `lab18` are present.

## Not claimed as verified
This package was not started against your Windows Docker installation or your existing MongoDB data. Live login, MongoDB replica-set elections, Ollama model inference, external feed synchronization, and lab execution still need to be verified in your environment.

## Windows startup
1. Extract this ZIP to a new folder.
2. Open PowerShell in the extracted `threat_intelligence_platform` folder.
3. If `.env` does not exist, run `Copy-Item .env.example .env` and set `JWT_SECRET` to a unique random value of at least 32 characters.
4. Start with `docker compose up --build -d`.
5. Check `docker compose ps -a`, then open `http://localhost:8000/login`.
6. Register a normal user at `http://localhost:8000/register`.
7. Bootstrap or promote the administrator using the included scripts and instructions in `UPGRADE_README.md` / `AUTH_UI_UPGRADE_README.md`.

## Important data safety
- Do not run `docker compose down -v`, `docker volume prune`, or `docker system prune` if you need existing MongoDB data.
- If you already have containers named `sentinelx-local-api`, `sentinelx-local-mongo1`, `sentinelx-local-mongo2`, or `sentinelx-local-mongo3`, do not launch a second copy from another folder. First decide which project folder should own the existing Compose stack.
- Keep your real `.env` private; it is intentionally excluded from the ZIP.


## Final package verification update

The final submission build additionally includes the overview dashboard assistant, session-scoped assistant conversations (tenant + username + session + lab), conversation switching/New chat, and a consistent 5-minute default sync interval. Final checks: Python compileall passed; Node syntax check passed; 11 frontend logic tests passed; 24 Python unit tests passed. Live Docker/lab execution remains an environment-side acceptance step; see `FINAL_SUBMISSION_GUIDE.md`.
