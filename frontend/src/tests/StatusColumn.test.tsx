import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusColumn } from "@/components/StatusColumn";
import type { ApiTask } from "@/types";

const task: ApiTask = {
  id: "t_1",
  projectId: "p_1",
  title: "Set up analytics",
  description: null,
  status: "todo",
  assigneeId: null,
  createdById: "u_1",
  position: 0,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  assignee: null,
};

describe("<StatusColumn />", () => {
  it("renders the column label and task", () => {
    render(<StatusColumn status="todo" tasks={[task]} onTaskClick={vi.fn()} />);
    expect(screen.getByText("To do")).toBeInTheDocument();
    expect(screen.getByText("Set up analytics")).toBeInTheDocument();
  });

  it("invokes onDropTask when a task id is dropped", () => {
    const onDropTask = vi.fn();
    render(
      <StatusColumn status="done" tasks={[]} onTaskClick={vi.fn()} onDropTask={onDropTask} />,
    );
    const column = screen.getByText("Done").closest("section");
    expect(column).toBeTruthy();
    fireEvent.drop(column!, {
      dataTransfer: { getData: () => "t_1" },
    });
    expect(onDropTask).toHaveBeenCalledWith("t_1");
  });
});
