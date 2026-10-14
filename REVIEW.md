# Code review — TaskBoard template

Top issues found in the starter app, ordered by business impact.

---

## 1. SQL injection in task search (critical) — **fixed in Part 2**

- **File / lines (original):** `backend/projects/views.py` (`TaskListCreateView.get`) — raw f-string SQL with `q` and `project_id` interpolated into `cursor.execute(sql)`
- **Category:** Security
- **Severity:** Critical
- **Description:** Task search built SQL with string formatting: `ILIKE '%{q}%'`. An authenticated project member could inject SQL via `?q=`. That can leak or destroy data in Postgres (e.g. `'; drop table…` patterns, or `' OR 1=1 --` to bypass filters).
- **Recommended fix:** Use the ORM with parameterized lookups (`Q(title__icontains=q)`), never interpolate user input into SQL.

### Bug proof (before fix — vulnerable template behavior)

With the original f-string SQL, searching for `' OR 1=1 --` matched **all** tasks in the project (filter bypass). Example against a project with two tasks:

```bash
# AFTER login; TOKEN and PROJECT_ID from seed session
curl -s "http://localhost:8000/api/projects/$PROJECT_ID/tasks?q=%27%20OR%201%3D1%20--" \
  -H "Authorization: Bearer $TOKEN"
```

**Before (vulnerable):** returned every task in the project (injection succeeded).

**After (fixed):** returns `{"tasks":[]}` — the payload is treated as a literal search string.

```bash
curl -s "http://localhost:8000/api/projects/$PROJECT_ID/tasks?q=%27%20OR%201%3D1%20--" \
  -H "Authorization: Bearer $TOKEN"
# {"tasks":[]}
```

---

## 2. Task PATCH missing membership / role checks

- **File / lines (original):** `backend/projects/views.py` — `TaskDetailView.patch` loaded the task and applied updates with **no** `_get_membership` check
- **Category:** Security
- **Severity:** Critical
- **Description:** Any authenticated user who knew a task UUID could change title, status, or assignee on projects they do not belong to. Delete correctly checked membership; patch did not. Broken authorization undermines the admin/member/viewer model.
- **Recommended fix:** Resolve membership for `task.project_id`; reject non-members (403) and viewers (403). Also validate assignees are project members.
- **Status:** Fixed alongside Part 2 hardening.

```bash
# Non-member with a valid JWT attempting to patch someone else's task
curl -s -X PATCH "http://localhost:8000/api/tasks/$TASK_ID" \
  -H "Authorization: Bearer $OUTSIDER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"hacked"}'
# After fix: {"error":"forbidden"}  (HTTP 403)
```

---

## 3. Airtable export was a stub

- **File / lines (original):** `backend/projects/views.py` — `ExportView.post` returned `exported: 0` without calling Airtable
- **Category:** Architecture
- **Severity:** High (blocks Part 3c / ops workflows)
- **Description:** The UI/API promised export, but no `pyairtable` calls ran. Re-exports would also duplicate rows if naively implemented with only `create()`.
- **Recommended fix:** Server-side upsert keyed by `TaskId`, retry transient HTTP errors, continue on per-record permanent failures. Ship `airtable_mock.py` for unit tests; use real credentials for integration demos.
- **Status:** Implemented in Part 3c.

---

## 4. Project list used per-row `tasks.count()` (N+1)

- **File / lines (original):** `backend/projects/views.py` — `ProjectListCreateView.get` called `p.tasks.count()` inside the membership loop
- **Category:** Performance
- **Severity:** Medium
- **Description:** Listing projects issued one `COUNT` query per membership. With many projects this slows the dashboard under load.
- **Recommended fix:** Annotate with `Count('project__tasks')` on the membership queryset (done in current code).

---

## Notes for reviewers

- Seed data was not modified.
- Part 2 fix: parameterized ORM search + tests in `TestTaskSearch`.
- Parts 3a (comments), 3b (activity feed), and 3c (Airtable upsert) are implemented with pytest coverage.
