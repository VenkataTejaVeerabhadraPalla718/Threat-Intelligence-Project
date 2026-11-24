# Boss upgrade — saved conversations + assistant name

## What was added
- **Name:** the assistant is now **Boss**. Say "Boss", "Hey Boss", or "Boss, latest 5 threats" — the name is
  stripped before the instant tools / knowledge base run, so every existing command still works.
  Asking "who are you?" / "what's your name?" answers instantly.
- **Saved conversations (ChatGPT-style):** every chat is stored in MongoDB per user, listed in a sidebar
  (Pinned / Today / Yesterday / Previous 7 days / Older), and can be reopened and continued later
  (history is sent back to the model, so follow-ups and `confirm <experiment>` work in an old chat).
- **Manage chats:** New chat, rename, pin/unpin, delete one, delete all, search (titles + message text),
  export a chat as Markdown, auto-generated titles.
- **Message tools:** Copy, Regenerate (last answer), Edit (last question), Stop generating (already existed),
  suggested starter prompts, voice input (🎤, browsers with Web Speech API, e.g. Chrome/Edge).
- Works on the **Boss page and on every Lab page** (lab pages show only that lab's chats).
- Chats written before this upgrade are automatically grouped into "Earlier chat" entries — nothing is lost.

## What was NOT changed
Ollama settings, tool allow-list, knowledge base, streaming, response cache, auth/roles, lab runner, threat
data, dashboards. Only identity wording in the system prompt ("You are Boss…") changed.

## Files
- NEW `backend/conversations.py` — `/api/conversations` API (list/get/rename/pin/delete/export/regenerate support)
- `backend/agent.py`, `backend/assistant_stream.py`, `backend/main.py` — conversation id plumbing + Boss name
- `frontend/js/app.js`, `frontend/css/app.css` — new chat UI
- NEW `tests/test_conversations.py` — 5 API tests (in-memory MongoDB)

## Apply
```powershell
docker compose up -d --build api
```
Then hard-refresh the browser (Ctrl+F5) and sign in. Keep your existing `.env`.

## Security
Each chat belongs to one user + tenant; other users get 404 for it. All endpoints require the JWT.
