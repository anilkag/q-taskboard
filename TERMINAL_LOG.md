# TERMINAL_LOG

Session log for the Senior Software Assignment (Django + React TaskBoard).

## 1. Setup

```text
docker compose up --build
# db healthy → backend Watching for file changes
# frontend VITE ready at http://localhost:3000/

docker compose exec backend python manage.py migrate
# Applying projects.0002_comment_activity... OK

docker compose exec backend python manage.py seed
# seed complete (passwords: password123)
```

App: http://localhost:3000 · API: http://localhost:8000

## 2. Initial / final test runs

```text
docker compose exec backend python -m pytest -q
# 45 passed

cd frontend && npm test
# Test Files  5 passed (5)
# Tests  13 passed (13)
```

## 3. Part 2 — SQL injection fix (curl before / after)

**Vulnerable pattern (template, before fix):** f-string SQL in `TaskListCreateView.get`:

```python
sql = f"... AND (title ILIKE '%{q}%' OR description ILIKE '%{q}%') ..."
cursor.execute(sql)
```

**Before:** `?q=' OR 1=1 --` returned all project tasks (filter bypass).

**After fix** (ORM `icontains`), same curl on Q3 Launch (`PROJECT=1a822b63-d7c6-475a-a81f-e3c3b8225299`):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"meera@taskboard.dev","password":"password123"}' | jq -r .token)

curl -s "http://localhost:8000/api/projects/$PROJECT/tasks?q=%27%20OR%201%3D1%20--" \
  -H "Authorization: Bearer $TOKEN"
# {"tasks":[]}

curl -s "http://localhost:8000/api/projects/$PROJECT/tasks?q=analytics" \
  -H "Authorization: Bearer $TOKEN"
# one task: "Set up analytics dashboards"
```

Captured this session: `INJECTION_TASKS=0`, `ANALYTICS=1 Set up analytics dashboards`.

Authz follow-up (task PATCH without membership):

```text
PATCH_OUTSIDER=403 {"error":"forbidden"}
```

## 4. Part 3a — Comments demo

```bash
curl -s -X POST "http://localhost:8000/api/tasks/$TASK_ID/comments" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"body":"Looks good for launch"}'
# comment body returned; chronological list via GET .../comments
```

Captured: `COMMENT=Looks good for launch`. Viewers get 403 on POST (covered by pytest).

## 5. Part 3b — Activity feed demo

```bash
curl -s "http://localhost:8000/api/projects/$PROJECT/activity" \
  -H "Authorization: Bearer $TOKEN"
# newest first; includes comment_added / task_status_changed / task_created
```

Captured: `ACTIVITY0=comment_added`. Non-member: `ACTIVITY_OUTSIDER=403`.

Rollback policy: see `DESIGN_NOTES.md` (activity write shares `transaction.atomic()` with the mutation).

## 6. Part 3c — Airtable export

Unit tests (mock): create → second run updates same `TaskId` (no duplicates); per-record permanent failure continues; transient 429 retries.

Live export this session (credentials not set in `.env`):

```text
EXPORT_ERR={"error":"Airtable is not configured"}
```

**To complete the live demo before submit:**

1. Create an Airtable base/table with fields: `TaskId`, `Title`, `Description`, `Status`, `Assignee`, `Project` (all single-line/long text as appropriate).
2. Put into `.env`:

```env
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE_NAME=Tasks
```

3. Restart backend, click **export to Airtable** on a project (or POST `/api/projects/:id/export`).
4. Confirm rows in Airtable; run export again — counts should show `updated` not duplicate creates.
5. Paste screenshot / share link here:

```text
Airtable share / screenshot: _TODO_
Second-run result JSON: _TODO_
```

## 7. Recording

See `RECORDING.md` — Loom link required for evaluation.
