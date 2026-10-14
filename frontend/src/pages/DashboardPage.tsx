import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, getToken } from "@/lib/api-client";
import { Header } from "@/components/Header";

type ProjectSummary = {
  id: string;
  name: string;
  description: string | null;
  role: "admin" | "member" | "viewer";
  owner: { id: string; name: string; email: string };
  taskCount: number;
  createdAt: string;
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    if (!getToken()) navigate("/login", { replace: true });
  }, [navigate]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<{ projects: ProjectSummary[] }>("/api/projects"),
    enabled: Boolean(getToken()),
  });

  const createProject = useMutation({
    mutationFn: (input: { name: string; description?: string }) =>
      apiFetch<{ project: { id: string; name: string } }>("/api/projects", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (result) => {
      setName("");
      setDescription("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${result.project.id}`);
    },
    onError: (err) => setFormError(err instanceof Error ? err.message : "create failed"),
  });

  return (
    <div className="min-h-screen">
      <Header />

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold">your projects</h1>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="bg-accent hover:bg-indigo-500 text-white text-sm font-medium rounded-md px-4 py-2"
          >
            {showForm ? "cancel" : "new project"}
          </button>
        </div>

        {showForm && (
          <form
            className="bg-surface border border-border rounded-lg p-5 mb-8 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              setFormError(null);
              if (!name.trim()) {
                setFormError("name is required");
                return;
              }
              createProject.mutate({
                name: name.trim(),
                description: description.trim() || undefined,
              });
            }}
          >
            <label className="block">
              <span className="text-xs text-muted">name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                placeholder="project name"
                required
              />
            </label>
            <label className="block">
              <span className="text-xs text-muted">description</span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="mt-1 block w-full rounded-md bg-bg border border-border px-3 py-2 text-sm focus:border-accent focus:outline-none"
                placeholder="optional"
              />
            </label>
            {formError && (
              <p className="text-sm text-red-400" role="alert">
                {formError}
              </p>
            )}
            <button
              type="submit"
              disabled={createProject.isPending}
              className="bg-accent hover:bg-indigo-500 text-white text-sm font-medium rounded-md px-4 py-2 disabled:opacity-50"
            >
              {createProject.isPending ? "creating…" : "create project"}
            </button>
          </form>
        )}

        {isLoading && <p className="text-muted text-sm">loading…</p>}
        {error && (
          <p className="text-sm text-red-400">
            {error instanceof Error ? error.message : "failed to load projects"}
          </p>
        )}

        {data && data.projects.length === 0 && (
          <p className="text-muted text-sm">no projects yet.</p>
        )}

        {data && data.projects.length > 0 && (
          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.projects.map((p) => (
              <li
                key={p.id}
                className="bg-surface border border-border rounded-lg p-5 hover:border-accent transition"
              >
                <Link to={`/projects/${p.id}`} className="block">
                  <div className="flex items-center justify-between mb-2">
                    <h2 className="font-medium">{p.name}</h2>
                    <span className="text-xs uppercase tracking-wide text-muted">
                      {p.role}
                    </span>
                  </div>
                  {p.description && (
                    <p className="text-sm text-muted mb-3 line-clamp-2">
                      {p.description}
                    </p>
                  )}
                  <p className="text-xs text-muted">
                    {p.taskCount} {p.taskCount === 1 ? "task" : "tasks"} · owner: {p.owner.name}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
