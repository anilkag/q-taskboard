import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "@/pages/DashboardPage";
import { setSession } from "@/lib/api-client";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => vi.fn() };
});

function renderDashboard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<DashboardPage />", () => {
  beforeEach(() => {
    setSession("tok", { id: "u1", email: "meera@taskboard.dev", name: "Meera Iyer" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        text: async () =>
          JSON.stringify({
            projects: [
              {
                id: "p1",
                name: "Q3 Launch",
                description: "Ship it",
                role: "admin",
                owner: { id: "u1", name: "Meera Iyer", email: "meera@taskboard.dev" },
                taskCount: 2,
                createdAt: new Date().toISOString(),
              },
            ],
          }),
      })),
    );
  });

  it("renders projects and a create control", async () => {
    renderDashboard();
    expect(await screen.findByText("Q3 Launch")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new project/i })).toBeInTheDocument();
  });
});
