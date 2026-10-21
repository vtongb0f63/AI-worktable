"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Job, jobNames, jobStates, post, useData } from "@/lib/planner";
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </header>
  );
}
export function Notice({
  text,
  error = false,
}: {
  text: string;
  error?: boolean;
}) {
  return text ? (
    <p
      className={error ? "notice error" : "notice"}
      role={error ? "alert" : "status"}
    >
      {text}
    </p>
  ) : null;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span aria-hidden="true" className="empty-mark">
        ＋
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Loading() {
  return (
    <p className="loading" role="status">
      正在翻开这一页…
    </p>
  );
}
export type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
  options?: [string, string][];
  min?: number;
  max?: number;
  step?: string;
  help?: string;
};
export function RecordForm({
  title,
  fields,
  initial = {},
  onSave,
  onClose,
}: {
  title: string;
  fields: Field[];
  initial?: Record<string, unknown>;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  function close() {
    if (!busy && (!dirty || confirm("放弃尚未保存的修改？"))) onClose();
  }
  return (
    <dialog
      ref={ref}
      className="editor"
      aria-labelledby="editor-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <form
        onChange={() => setDirty(true)}
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          setBusy(true);
          setError("");
          try {
            const data: Record<string, unknown> = {};
            const values = new FormData(form);
            for (const field of fields) {
              const raw = values.get(field.name);
              data[field.name] =
                field.type === "checkbox"
                  ? raw === "on"
                  : field.type === "number"
                    ? raw === ""
                      ? null
                      : Number(raw)
                    : raw;
            }
            await onSave(data);
            onClose();
          } catch (err) {
            setError((err as Error).message);
            setTimeout(
              () => form.querySelector<HTMLElement>('[role="alert"]')?.focus(),
              0,
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="dialog-heading">
          <h2 id="editor-title">{title}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="关闭编辑"
            onClick={close}
          >
            ×
          </button>
        </div>
        <div className="form-grid">
          {fields.map((field) => (
            <label
              key={field.name}
              className={field.type === "textarea" ? "wide" : ""}
            >
              <span>{field.label}</span>
              {field.options ? (
                <select
                  name={field.name}
                  defaultValue={String(
                    initial[field.name] ?? field.options[0][0],
                  )}
                >
                  {field.options.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              ) : field.type === "textarea" ? (
                <textarea
                  name={field.name}
                  rows={4}
                  required={field.required}
                  defaultValue={String(initial[field.name] ?? "")}
                  placeholder={field.placeholder}
                  autoComplete="off"
                />
              ) : (
                <input
                  name={field.name}
                  type={field.type || "text"}
                  required={field.required}
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  defaultChecked={
                    field.type === "checkbox"
                      ? Boolean(initial[field.name])
                      : undefined
                  }
                  defaultValue={
                    field.type === "checkbox"
                      ? undefined
                      : String(initial[field.name] ?? "")
                  }
                  placeholder={field.placeholder}
                  autoComplete="off"
                />
              )}
              {field.help ? (
                <small className="muted">{field.help}</small>
              ) : null}
            </label>
          ))}
        </div>
        {error ? (
          <p role="alert" tabIndex={-1} className="notice error">
            {error}
          </p>
        ) : null}
        <div className="form-actions">
          <button
            type="button"
            className="button secondary"
            onClick={close}
            disabled={busy}
          >
            取消
          </button>
          <button className="button" disabled={busy}>
            {busy ? "正在保存…" : "保存"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
export function Pagination({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (n: number) => void;
}) {
  return total > 50 ? (
    <nav className="pagination" aria-label="分页">
      <button
        className="button secondary"
        disabled={!offset}
        onClick={() => onChange(offset - 50)}
      >
        上一页
      </button>
      <span>
        {offset + 1}–{Math.min(offset + 50, total)} / {total}
      </span>
      <button
        className="button secondary"
        disabled={offset + 50 >= total}
        onClick={() => onChange(offset + 50)}
      >
        下一页
      </button>
    </nav>
  ) : null;
}
export function JobPanel({
  onFinished,
  refreshKey = 0,
}: {
  onFinished?: () => void;
  refreshKey?: number;
}) {
  const { data, reload } = useData<Job[]>(`/jobs?refresh=${refreshKey}`);
  const previous = useRef<string>("");
  const callback = useRef(onFinished);
  callback.current = onFinished;
  const [error, setError] = useState("");
  useEffect(() => {
    const active = data?.some((j) => ["pending", "running"].includes(j.status));
    if (!active) return;
    const timer = setInterval(reload, 4000);
    return () => clearInterval(timer);
  }, [data, reload]);
  useEffect(() => {
    const key =
      data
        ?.filter((j) => j.status === "done")
        .map((j) => j.id)
        .join(",") || "";
    if (previous.current && key !== previous.current) callback.current?.();
    previous.current = key || "none";
  }, [data]);
  const visible =
    data?.filter((j) => j.status !== "cancelled").slice(0, 5) || [];
  if (!visible.length) return null;
  async function action(id: string, verb: string) {
    try {
      await post(`/jobs/${id}/${verb}`, {});
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <details className="job-panel">
      <summary>
        AI 整理进度{" "}
        <span className="muted">
          {visible.filter((j) => j.status !== "done").length} 项待处理
        </span>
      </summary>
      <Notice text={error} error />
      <div aria-live="polite">
        {visible.map((job) => (
          <div className="job-row" key={job.id}>
            <div>
              <strong>{jobNames[job.kind]}</strong>
              <span className="tag">{jobStates[job.status]}</span>
              {job.error ? <p className="muted">{job.error}</p> : null}
              {job.status === "done" && job.kind === "quiz" ? (
                <Link href={`/words?quiz=${job.id}`} className="text-link">
                  开始这组练习 →
                </Link>
              ) : null}
            </div>
            <div>
              {["blocked", "failed"].includes(job.status) ? (
                <button
                  className="button small secondary"
                  onClick={() => action(job.id, "retry")}
                >
                  重试
                </button>
              ) : null}
              {["pending", "running", "blocked"].includes(job.status) ? (
                <button
                  className="button small quiet"
                  onClick={() => action(job.id, "cancel")}
                >
                  取消
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
export function AIButton({
  kind,
  payload = {},
  label,
  onQueued,
}: {
  kind: string;
  payload?: object;
  label: string;
  onQueued?: (job: Job) => void;
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <div>
      <button
        className="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setMessage("");
          try {
            const job = await post<Job>("/jobs", { kind, payload });
            setMessage("已加入整理队列，可继续使用其他功能");
            onQueued?.(job);
          } catch (e) {
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "正在提交…" : label}
      </button>
      <span className="action-message" role="status">
        {message}
      </span>
    </div>
  );
}
