import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "@/pages/LoginPage";
import { clearSession } from "@/lib/api-client";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

describe("<LoginPage />", () => {
  beforeEach(() => {
    clearSession();
    navigate.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        text: async () =>
          JSON.stringify({
            token: "jwt-token",
            user: { id: "u1", email: "meera@taskboard.dev", name: "Meera Iyer" },
          }),
      })),
    );
  });

  it("signs in and stores the session", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/dashboard"));
    expect(window.localStorage.getItem("taskboard_token")).toBe("jwt-token");
  });
});
