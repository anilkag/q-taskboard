import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, getStoredUser, getToken } from "@/lib/api-client";
import { Header } from "@/components/Header";
import { StatusColumn } from "@/components/StatusColumn";
import { TaskDetail } from "@/components/TaskDetail";
import type { ApiActivity, ApiProjectDetail, ApiTask, Role, TaskStatus } from "@/types";
import { STATUS_ORDER } from "@/types";

function activityLabel(a: ApiActivity): string {
  const title = a.metadata?.title ?? "a task";
  switch (a.action) {
    case "task_created":
      return `created “${title}”`;
    case "task_status_changed":
      return `moved “${title}” from ${a.metadata?.from ?? "?"} to ${a.metadata?.to ?? "?"}`;
    case "task_assignee_changed":
      return `changed assignee on “${title}”`;
    case "comment_added":
      return `commented on “${title}”`;
    default:
      return a.action;
  }
}

export default function ProjectPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const me = getStoredUser();

  const [activeTask, setActiveTask] = useState<ApiTask | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newColumn, setNewColumn] = useState<TaskStatus>("todo");
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [memberEmail, setMemberEmail] = useState("");
  const [memberRole, setMemberRole] = useState<Role>("member");
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) navigate("/login", { replace: true });
  }, [navigate]);

  const { data, isLoading, error: queryError } = useQuery({
    queryKey: ["project", id],
    queryFn: () => apiFetch<{ project: ApiProjectDetail }>(`/api/projects/${id}`),
    enabled: Boolean(id) && Boolean(getToken()),
  });

  const { data: searchData } = useQuery({
    queryKey: ["project-tasks", id, search],
    queryFn: () => apiFetch<{ tasks: ApiTask[] }>(`/api/projects/${id}/tasks?q=${encodeURIComponent(search)}`),
    enabled: Boolean(id) && Boolean(search),
  });

  const { data: activityData } = useQuery({
    queryKey: ["activity", id],
    queryFn: () => apiFetch<{ activities: ApiActivity[] }>(`/api/projects/${id}/activity`),
    enabled: Boolean(id) && Boolean(getToken()),
  });

  const createTask = useMutation({
    mutationFn: (input: { title: string; status: TaskStatus }) =>
      apiFetch<{ task: ApiTask }>(`/api/projects/${id}/tasks`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      setNewTitle("");
      queryClient.invalidateQueries({ queryKey: ["project", id] });
      queryClient.invalidateQueries({ queryKey: ["activity", id] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "create failed"),
  });

  const moveTask = useMutation({
    mutationFn: (input: { taskId: string; status: TaskStatus }) =>
      apiFetch<{ task: ApiTask }>(`/api/tasks/${input.taskId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: input.status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", id] });
      queryClient.invalidateQueries({ queryKey: ["activity", id] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "move failed"),
  });

  const addMember = useMutation({
    mutationFn: (input: { email: string; role: Role }) =>
      apiFetch<{ ok: true; role: Role }>(`/api/projects/${id}/members`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      setMemberEmail("");
      queryClient.invalidateQueries({ queryKey: ["project", id] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "add member failed"),
  });

  const exportProject = useMutation({
    mutationFn: () =>
      apiFetch<{ exported: number; created: number; updated: number; failed: number }>(
        `/api/projects/${id}/export`,
        { method: "POST" },
      ),
    onSuccess: (result) =>
      setExportMessage(
        `exported ${result.exported} tasks to Airtable (${result.created} created, ${result.updated} updated, ${result.failed} failed)`,
      ),
    onError: (err) => setError(err instanceof Error ? err.message : "export failed"),
  });

  const project = data?.project;
  const myRole: Role | null = useMemo(() => {
    if (!project || !me) return null;
    return project.memberships.find((m) => m.user.id === me.id)?.role ?? null;
  }, [project, me]);
  const canEdit = myRole === "admin" || myRole === "member";
  const isAdmin = myRole === "admin";

  const visibleTasks = search && searchData ? searchData.tasks : project?.tasks ?? [];
  const tasksByStatus: Record<TaskStatus, ApiTask[]> = {
    todo: [],
    in_progress: [],
    review: [],
    done: [],
  };
  for (const t of visibleTasks) {
    tasksByStatus[t.status].push(t);
  }

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-7xl mx-auto px-6 py-8">
        <Link to="/dashboard" className="text-sm text-muted hover:text-white">
          ← all projects
        </Link>

        {isLoading && <p className="text-muted text-sm mt-6">loading…</p>}
        {queryError && (
          <p className="text-sm text-red-400 mt-6">
            {queryError instanceof Error ? queryError.message : "failed to load"}
          </p>
        )}

        {project && (
          <>
            <div className="flex items-start justify-between mt-4 mb-8 gap-4">
              <div>
                <h1 className="text-2xl font-semibold">{project.name}</h1>
                {project.description && (
                  <p className="text-sm text-muted mt-1 max-w-2xl">{project.description}</p>
                )}
                <p className="text-xs text-muted mt-2">
                  owner: {project.owner.name} · {project.memberships.length} members
                  {myRole ? ` · you: ${myRole}` : ""}
                </p>
              </div>
              {canEdit && (
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setExportMessage(null);
                    exportProject.mutate();
                  }}
                  disabled={exportProject.isPending}
                  className="text-sm border border-border hover:border-accent rounded-md px-3 py-2 disabled:opacity-50"
                >
                  {exportProject.isPending ? "exporting…" : "export to Airtable"}
                </button>
              )}
            </div>

            {exportMessage && <p className="text-sm text-emerald-400 mb-4">{exportMessage}</p>}

            <form
              className="mb-6"
              onSubmit={(e) => {
                e.preventDefault();
                setSearch(q.trim());
              }}
            >
              <label className="block">
                <span className="text-xs text-muted">search tasks</span>
                <div className="mt-1 flex gap-2">
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="title or description"
                    className="flex-1 rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                  />
                  <button type="submit" className="text-sm border border-border rounded-md px-3">
                    search
                  </button>
                  {search && (
                    <button
                      type="button"
                      onClick={() => {
                        setQ("");
                        setSearch("");
                      }}
                      className="text-sm text-muted"
                    >
                      clear
                    </button>
                  )}
                </div>
              </label>
            </form>

            {canEdit && (
              <section className="bg-surface border border-border rounded-lg p-4 mb-6">
                <h2 className="text-sm font-medium mb-3">add a task</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!newTitle.trim()) return;
                    setError(null);
                    createTask.mutate({ title: newTitle.trim(), status: newColumn });
                  }}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="task title"
                    className="flex-1 rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                  />
                  <select
                    value={newColumn}
                    onChange={(e) => setNewColumn(e.target.value as TaskStatus)}
                    className="rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                  >
                    {STATUS_ORDER.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={createTask.isPending}
                    className="bg-accent hover:bg-indigo-500 text-white text-sm font-medium rounded-md px-4 disabled:opacity-50"
                  >
                    add
                  </button>
                </form>
              </section>
            )}

            {error && (
              <p className="text-sm text-red-400 mb-4" role="alert">
                {error}
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {STATUS_ORDER.map((s) => (
                <StatusColumn
                  key={s}
                  status={s}
                  tasks={tasksByStatus[s]}
                  onTaskClick={setActiveTask}
                  onDropTask={
                    canEdit
                      ? (taskId) => moveTask.mutate({ taskId, status: s })
                      : undefined
                  }
                />
              ))}
            </div>

            <section className="mt-10">
              <h2 className="text-sm font-medium mb-3">recent activity</h2>
              <ul className="bg-surface border border-border rounded-lg divide-y divide-border mb-10">
                {(activityData?.activities ?? []).length === 0 && (
                  <li className="px-4 py-3 text-sm text-muted italic">no activity yet</li>
                )}
                {(activityData?.activities ?? []).map((a) => (
                  <li key={a.id} className="px-4 py-3 text-sm flex items-start justify-between gap-4">
                    <span>
                      <span className="font-medium">{a.actor.name}</span> {activityLabel(a)}
                    </span>
                    <span className="text-xs text-muted whitespace-nowrap">
                      {new Date(a.createdAt).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="mt-10">
              <h2 className="text-sm font-medium mb-3">members</h2>
              {isAdmin && (
                <form
                  className="flex gap-2 mb-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!memberEmail.trim()) return;
                    setError(null);
                    addMember.mutate({ email: memberEmail.trim(), role: memberRole });
                  }}
                >
                  <input
                    type="email"
                    value={memberEmail}
                    onChange={(e) => setMemberEmail(e.target.value)}
                    placeholder="member email"
                    className="flex-1 rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                  />
                  <select
                    value={memberRole}
                    onChange={(e) => setMemberRole(e.target.value as Role)}
                    className="rounded-md bg-bg border border-border px-3 py-2 text-sm"
                  >
                    <option value="admin">admin</option>
                    <option value="member">member</option>
                    <option value="viewer">viewer</option>
                  </select>
                  <button
                    type="submit"
                    disabled={addMember.isPending}
                    className="text-sm bg-accent text-white rounded-md px-3 disabled:opacity-50"
                  >
                    add
                  </button>
                </form>
              )}
              <ul className="bg-surface border border-border rounded-lg divide-y divide-border">
                {project.memberships.map((m) => (
                  <li key={m.id} className="px-4 py-3 flex items-center justify-between text-sm">
                    <span>{m.user.name}</span>
                    <span className="text-xs text-muted">
                      {m.user.email} · {m.role}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </main>

      {activeTask && project && (
        <TaskDetail
          task={activeTask}
          projectId={id!}
          members={project.memberships}
          canEdit={canEdit}
          onClose={() => setActiveTask(null)}
        />
      )}
    </div>
  );
}
