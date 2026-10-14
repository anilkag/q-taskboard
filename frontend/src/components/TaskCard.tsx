import type { ApiTask } from "@/types";

type Props = {
  task: ApiTask;
  onClick?: (task: ApiTask) => void;
  draggable?: boolean;
};

export function TaskCard({ task, onClick, draggable }: Props) {
  return (
    <button
      type="button"
      draggable={draggable}
      onDragStart={(e) => {
        if (!draggable) return;
        e.dataTransfer.setData("text/task-id", task.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={() => onClick?.(task)}
      className="w-full text-left bg-bg border border-border rounded-md p-3 hover:border-accent transition"
    >
      <p className="text-sm font-medium leading-snug mb-2">{task.title}</p>
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{task.assignee ? task.assignee.name : "unassigned"}</span>
      </div>
    </button>
  );
}
