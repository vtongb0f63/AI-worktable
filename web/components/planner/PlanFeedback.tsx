"use client";
import { useEffect, useRef, useState } from "react";
import { Plan } from "@/lib/planner";
import { Notice } from "./Shared";

export default function PlanFeedback({ plan, onClose, onReject, onRevise }: {
  plan: Plan;
  onClose: () => void;
  onReject: () => Promise<void>;
  onRevise: (indices: number[], feedback: string, allowRemoval: boolean) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [mode, setMode] = useState<"choice" | "revise">("choice");
  const [selected, setSelected] = useState<number[]>([]);
  const [feedback, setFeedback] = useState("");
  const [allowRemoval, setAllowRemoval] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function submit(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try { await action(); onClose(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return (
    <dialog ref={dialog} className="editor plan-feedback" aria-labelledby="plan-feedback-title"
      onCancel={(e) => { e.preventDefault(); if (!busy) onClose(); }}>
      <div className="dialog-heading">
        <h2 id="plan-feedback-title">{mode === "choice" ? "如何处理这份计划？" : "告诉AI如何做得不同"}</h2>
        <button type="button" className="icon-button" aria-label="关闭计划反馈" disabled={busy} onClick={onClose}>×</button>
      </div>
      {mode === "choice" ? (
        <>
          <p className="muted">可以直接否决整份草稿，也可以只让 AI 调整部分安排。</p>
          <Notice text={error} error />
          <div className="form-actions feedback-actions">
            <button className="button secondary" disabled={busy} onClick={() => submit(onReject)}>直接否决</button>
            <button className="button secondary" disabled={busy} onClick={onClose}>取消</button>
            <button className="button" disabled={busy || !plan.tasks.length} onClick={() => setMode("revise")}>告诉AI如何做得不同</button>
          </div>
        </>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); if (selected.length && feedback.trim()) void submit(() => onRevise(selected, feedback.trim(), allowRemoval)); }}>
          <fieldset disabled={busy} className="revision-selection">
            <legend>勾选需要修改的安排（至少一项）</legend>
            {plan.tasks.map((task, index) => (
              <label key={index} className="revision-option">
                <input type="checkbox" checked={selected.includes(index)} onChange={(e) => setSelected(e.target.checked ? [...selected, index] : selected.filter(i => i !== index))} />
                <span><strong>{task.title}</strong><small>{task.date} · {task.start_time || "未定时"}{task.end_time ? `–${task.end_time}` : ""}</small></span>
              </label>
            ))}
          </fieldset>
          <p className="muted">未勾选的安排保持原样。修改完成后，仍需你确认采用。</p>
          <label className="revision-feedback">
            <span>希望如何调整</span>
            <textarea required maxLength={3000} rows={4} value={feedback} disabled={busy} onChange={(e) => setFeedback(e.target.value)} placeholder="例如：把选中的跑步安排改到周四晚，时长缩短到30分钟。" />
          </label>
          <label className="revision-option">
            <input type="checkbox" checked={allowRemoval} disabled={busy} onChange={(e) => setAllowRemoval(e.target.checked)} />
            <span>允许 AI 按我的说明删除选中的安排</span>
          </label>
          <Notice text={error} error />
          <div className="form-actions feedback-actions">
            <button type="button" className="button secondary" disabled={busy} onClick={onClose}>取消</button>
            <button className="button" disabled={busy || !selected.length || !feedback.trim()}>{busy ? "正在提交…" : "提交局部修改"}</button>
          </div>
        </form>
      )}
    </dialog>
  );
}
