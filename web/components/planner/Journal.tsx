"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Entity, useData, todayLocal, dateLabel, post } from "@/lib/planner";
import { PageHeading, Notice, Empty, Loading, Pagination } from "./Shared";
type Event = Entity & {
  kind: string;
  date: string;
  detail: { title?: string; correct?: boolean; resource?: string };
};
export default function Journal() {
  const router = useRouter(),
    params = useSearchParams(),
    day = params.get("day") || todayLocal();
  const [offset, setOffset] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useData<{
    items: Event[];
    total: number;
    notes: (Entity & { text: string })[];
  }>(`/journal?day=${day}&offset=${offset}`);
  return (
    <>
      <PageHeading
        eyebrow="SMALL STEPS, REAL PROGRESS"
        title="今天，留下了什么。"
        description="记录已经发生的努力，也留一点空间给自己的感受。"
      >
        <label>
          <span className="sr-only">日志日期</span>
          <input
            type="date"
            name="journal_date"
            value={day}
            onChange={(e) => {
              if (e.target.value) {
                setOffset(0);
                router.replace(`/journal?day=${e.target.value}`);
              }
            }}
          />
        </label>
      </PageHeading>
      <Notice text={error || loadError} error />
      <div className="journal-grid">
        <section className="paper-panel">
          <div className="section-heading">
            <h2>{dateLabel(day)}</h2>
            <span className="tag">{data?.total || 0} 条记录</span>
          </div>
          {loading && !data ? <Loading /> : null}
          {data?.items.length ? (
            <ol className="journal-timeline">
              {data.items.map((event) => (
                <li key={event.id}>
                  <time>
                    {new Intl.DateTimeFormat("zh-CN", {
                      timeZone: "Asia/Shanghai",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    }).format(new Date(event.created_at))}
                  </time>
                  <div>
                    <span className="category study">{event.kind}</span>
                    <h3>{event.detail.title}</h3>
                    {event.detail.correct !== undefined ? (
                      <p className="muted">
                        {event.detail.correct ? "回答正确" : "已加入后续复习"}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <Empty title="这一天的记录还在等你写下">
              勾选待办、练习词汇和记录训练后，足迹会自动留在这里。
            </Empty>
          )}
          <Pagination
            offset={offset}
            total={data?.total || 0}
            onChange={setOffset}
          />
        </section>
        <aside>
          <section className="paper-panel journal-note">
            <p className="eyebrow">A NOTE TO YOURSELF</p>
            <h2>写给今天的自己</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const form = e.currentTarget;
                setBusy(true);
                try {
                  await post("/journal", {
                    date: day,
                    text: new FormData(form).get("text"),
                  });
                  form.reset();
                  reload();
                } catch (err) {
                  setError((err as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                <span className="sr-only">今日复盘</span>
                <textarea
                  rows={8}
                  name="text"
                  autoComplete="off"
                  required
                  placeholder="今天做得不错的事、遇到的困难，或想记住的一瞬间…"
                />
              </label>
              <button className="button" disabled={busy}>
                {busy ? "正在保存…" : "留在这一页"}
              </button>
            </form>
          </section>
          {data?.notes.map((note) => (
            <article className="paper-panel saved-note" key={note.id}>
              <small>我的复盘</small>
              <p className="preserve-lines">{note.text}</p>
            </article>
          ))}
        </aside>
      </div>
    </>
  );
}
