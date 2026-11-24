# SENTINEL-X Login, Registration and Admin Audit UI Upgrade

This bundle is a complete updated project ZIP. It includes the full existing Labs 7–18 project plus these changes:

- `/` and `/console` show the sign-in screen when no valid session token is present.
- `/login` provides sign-in; `/register` allows self-registration as a normal `user` only.
- New users must use a password of at least 12 characters.
- Successful and failed login attempts, plus self-registration events, are stored in MongoDB collection `login_activity`.
- Administrators can review login activity and manage accounts at `/console?page=admin`.
- Sidebar order is Executive overview → AI assistant → Threat intelligence → Experiments.
- Labs 7–18 are grouped under an expandable Experiments folder.
- Frontend API requests automatically attach the stored bearer token.
- Legacy `/threats`, `/chat`, and `/dashboard` UI routes now serve the authenticated enterprise shell.

## Install

1. Back up your current project folder and `.env`.
2. Stop containers without deleting volumes: `docker compose stop`.
3. Extract this ZIP over the project parent folder, preserving `.env` and all Docker volumes.
4. Rebuild the API: `docker compose up -d --build api`.
5. Check: `Invoke-RestMethod http://localhost:8000/health`.
6. Open `http://localhost:8000/login` and sign in.
7. For the administrator account, open `http://localhost:8000/console?page=admin` to see users and login activity.

## Important

- Self-registration always creates role `user`. A current administrator must assign admin privileges.
- Existing users and passwords are preserved; this upgrade does not reset MongoDB volumes.
- Login activity stores username, success/failure, reason, client IP, user-agent and timestamp. Avoid exposing this app publicly without TLS, stronger rate limiting, CSRF protections and a review of all state-changing API routes.
- The browser stores the bearer token in localStorage. Use this only on a trusted local machine; for internet-facing deployment, move to secure HttpOnly cookies and HTTPS.
- Existing non-authenticated data and lab API routes have not all been converted to strict per-user authorization by this UI upgrade. This adds the requested login experience and audit view, but it is not a complete public-production security certification.
