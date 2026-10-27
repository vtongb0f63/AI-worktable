"use client";
import { useState } from "react";
import {
  Task,
  clean,
  taskKeys,
  put,
  post,
  request,
  categoryName,
} from "@/lib/planner";
import { Field, RecordForm, Notice } from "./Shared";
export const taskFields: Field[] = [
  {
    name: "title",
    label: "要做什么",
    required: true,
    placeholder: "例如：完成数学分析第三节习题…",
  },
  { name: "date", label: "安排日期", type: "date", required: true },
  {
    name: "category",
    label: "分类",
    options: [
      ["study", "学习"],
      ["life", "生活"],
      ["vocabulary", "词汇"],
      ["training", "跑步"],
    ],
  },
  { name: "due_on", label: "截止日期（可选）", type: "date" },
  { name: "start_time", label: "开始时间（可选）", type: "time" },
  { name: "end_time", label: "结束时间（可选）", type: "time" },
  { name: "note", label: "内容与备注", type: "textarea" },
  { name: "locked", label: "锁定这个安排", type: "checkbox" },
];
export function TaskEditor({
  task,
  day,
  onClose,
  onSaved,
}: {
  task?: Task;
  day: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  return (
    <RecordForm
      title={task ? "编辑待办" : "添一件要做的事"}
      fields={taskFields}
      initial={task ? { ...task } : { date: day, category: "study" }}
      onClose={onClose}
      onSave={async (data) => {
        const body = {
          ...data,
          start_time: data.start_time || null,
          end_time: data.end_time || null,
          due_on: data.due_on || null,
          status: task?.status || "pending",
          source_id: task?.source_id || null,
        };
        if (task)
          await put(`/records/tasks/${task.id}`, {
            version: task.version,
            data: body,
          });
        else await post("/records/tasks", body);
        onSaved();
      }}
    />
  );
}
export function TaskList({
  tasks,
  onChanged,
}: {
  tasks: Task[];
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState<Task | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState("");
  async function toggle(task: Task) {
    setBusy(task.id);
    setError("");
    try {
      await put(`/records/tasks/${task.id}`, {
        version: task.version,
        data: {
          ...clean(task, taskKeys),
          status: task.status === "done" ? "pending" : "done",
        },
      });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <Notice text={error} error />
      <ul className="task-list">
        {tasks.map((task) => (
          <li
            key={task.id}
            className={`task-row ${task.status === "done" ? "is-done" : ""}`}
          >
            <label className="task-check">
              <input
                type="checkbox"
                checked={task.status === "done"}
                disabled={busy === task.id}
                onChange={() => toggle(task)}
                aria-label={`${task.status === "done" ? "撤销完成" : "完成"}：${task.title}`}
              />
              <span className="check-visual" aria-hidden="true">
                ✓
              </span>
            </label>
            <div className="task-content">
              <div className="task-meta">
                <span className={`category ${task.category}`}>
                  {categoryName[task.category]}
                </span>
                <span>
                  {task.start_time
                    ? `${task.start_time}–${task.end_time}`
                    : "时间自由安排"}
                </span>
                {task.locked ? <span>已锁定</span> : null}
              </div>
              <strong>{task.title}</strong>
              {task.note ? <p>{task.note}</p> : null}
              {["partial", "skipped"].includes(task.status) ? (
                <small>
                  {task.status === "partial" ? "部分完成" : "已跳过"}
                </small>
              ) : null}
            </div>
            <button
              className="icon-button"
              aria-label={`编辑：${task.title}`}
              onClick={() => setEditing(task)}
            >
              ✎
            </button>
            <button
              className="icon-button delete-button"
              aria-label={`删除：${task.title}`}
              onClick={async () => {
                if (!confirm(`删除「${task.title}」？日志记录会保留。`)) return;
                try {
                  await request(
                    `/records/tasks/${task.id}?version=${task.version}`,
                    { method: "DELETE" },
                  );
                  onChanged();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      {editing ? (
        <TaskEditor
          task={editing}
          day={editing.date}
          onClose={() => setEditing(null)}
          onSaved={onChanged}
        />
      ) : null}
    </>
  );
}
