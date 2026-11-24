# SENTINEL-X AI Assistant Upgrade

## What changed

- `POST /api/assistant` now uses the existing `current_user` JWT dependency.
- `GET /api/assistant/status` also requires an authenticated session.
- Assistant turns are stored with `tenant_id`, `username`, `session_id`, and lab context.
- Persisted context queries are scoped to the same tenant, username, session, and lab.
- Database-backed answers, normal model replies, and registered experiment outcomes are stored as conversation turns.
- The enterprise assistant includes a **New chat** action. Browser history and session IDs are separated by signed-in username and lab.
- Existing Ollama configuration, deterministic threat-data query tools, and registered experiment confirmation flow are retained.

## Apply the package safely on Windows

1. Stop the running API container or application.
2. Make a backup copy of your current project folder.
3. Extract this ZIP to a new folder first and compare it with your current project.
4. Preserve your existing `.env` file. This package intentionally omits `.env` so credentials and local secrets are not redistributed. Keep the existing values for `OLLAMA_URL`, `OLLAMA_MODEL`, `EMBED_MODEL`, MongoDB, and JWT configuration.
5. Copy the upgraded `backend/main.py` and `frontend/enterprise.html` into your project, or use the complete extracted project after restoring your own `.env`.
6. Rebuild and restart only the API service using your normal Compose workflow, for example:

   ```powershell
   docker compose up -d --build api
   ```

7. Sign in again, open the Assistant page, and confirm the Ollama status badge reports the configured model as ready.
8. Test a normal question, start a **New chat**, and verify that the new conversation begins independently.

## Verification performed

- Python syntax compilation passed for the backend modules.
- JavaScript syntax check passed for the enterprise frontend script.
- Source inspection confirmed the authenticated dependency and per-user/per-tenant/session history filter.
- A live Docker/MongoDB/Ollama integration test was not run in this build environment. Verify the rebuilt API in your local environment before relying on it.

## Notes

- Existing assistant history documents created before this upgrade do not contain the new ownership/session fields. They are intentionally not loaded into authenticated conversations.
- Threat and source collections remain shared workspace data; no tenant ownership filter was added to those collections.
- Lab 15's separate `/api/chat` workflow was not replaced.
