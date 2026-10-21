"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Run,
  Task,
  Draft,
  News,
  Page,
  useData,
  todayLocal,
  mondayLocal,
  shiftDay,
  put,
  post,
  request,
} from "@/lib/planner";
import {
  PageHeading,
  Notice,
  Empty,
  Loading,
  Field,
  RecordForm,
  AIButton,
  JobPanel,
  Pagination,
} from "./Shared";
import { DraftPanel } from "./Schedule";
const baseFields: Field[] = [
  { name: "date", label: "训练日期", type: "date", required: true },
  {
    name: "status",
    label: "完成情况",
    options: [
      ["done", "完整完成"],
      ["partial", "部分完成"],
      ["skipped", "跳过训练"],
    ],
  },
  {
    name: "distance_km",
    label: "距离（公里）",
    type: "number",
    min: 0,
    max: 250,
    step: "0.01",
    required: true,
  },
  {
    name: "duration_minutes",
    label: "用时（分钟）",
    type: "number",
    min: 0,
    max: 3000,
    step: "0.01",
    required: true,
  },
  {
    name: "effort",
    label: "主观疲劳（1–10）",
    type: "number",
    min: 1,
    max: 10,
    required: true,
  },
  {
    name: "heart_rate",
    label: "平均心率（可选）",
    type: "number",
    min: 30,
    max: 240,
  },
  {
    name: "splits",
    label: "分段数据（可选）",
    type: "textarea",
    placeholder: "例如：第1公里 5:20，第2公里 5:15…",
  },
  { name: "discomfort", label: "身体不适（可选）", type: "textarea" },
  { name: "note", label: "训练感受", type: "textarea" },
];
function pace(run: Run) {
  if (!run.distance_km) return "—";
  const sec = Math.round((run.duration_minutes * 60) / run.distance_km);
  return `${Math.floor(sec / 60)}′${String(sec % 60).padStart(2, "0")}″`;
}
export default function Running() {
  const [editing, setEditing] = useState<Run | "new" | null>(null),
    [offset, setOffset] = useState(0),
    [jobRevision, setJobRevision] = useState(0),
    [error, setError] = useState("");
  const runs = useData<Page<Run>>(`/records/runs?offset=${offset}&limit=50`),
    tasks = useData<{ runs: Run[]; tasks: Task[] }>(
      `/running-summary?start=${mondayLocal()}`,
    ),
    drafts = useData<{ plans: Draft[] }>("/drafts"),
    news = useData<Page<News>>("/news?category=running&limit=6");
  const today = todayLocal(),
    monday = mondayLocal(),
    weekRuns = tasks.data?.runs.filter((r) => r.status !== "skipped") || [],
    training = tasks.data?.tasks || [],
    todayTraining = training.filter((t) => t.date === today);
  function reload() {
    runs.reload();
    tasks.reload();
    drafts.reload();
  }
  const mileage = weekRuns.reduce((sum, r) => sum + r.distance_km, 0);
  return (
    <>
      <PageHeading
        eyebrow="KEEP SHOWING UP"
        title="跑过的每一步。"
        description="按自己的节奏训练，让记录告诉你身体的变化。"
      >
        <button className="button" onClick={() => setEditing("new")}>
          ＋ 记录一次训练
        </button>
      </PageHeading>
      <Notice text={error || runs.error} error />
      <section className="running-banner">
        <div>
          <p className="eyebrow">THIS WEEK · 本周累计</p>
          <h2>
            {mileage.toFixed(1)}
            <small> km</small>
          </h2>
          <p>
            {weekRuns.length} 次训练 ·{" "}
            {weekRuns.reduce((s, r) => s + r.duration_minutes, 0).toFixed(0)}{" "}
            分钟
          </p>
        </div>
        <div className="mileage-chart" role="img" aria-label="本周每天跑步距离">
          {Array.from({ length: 7 }, (_, i) => {
            const day = shiftDay(monday, i),
              km = weekRuns
                .filter((r) => r.date === day)
                .reduce((s, r) => s + r.distance_km, 0);
            return (
              <div key={day}>
                <small>{km ? km.toFixed(1) : ""}</small>
                <div className="bar-track">
                  <span
                    style={{
                      height: `${Math.min(100, (km / Math.max(1, ...weekRuns.map((r) => r.distance_km))) * 100)}%`,
                    }}
                  />
                </div>
                <span>{"一二三四五六日"[i]}</span>
              </div>
            );
          })}
        </div>
      </section>
      <div className="two-columns">
        <section className="paper-panel">
          <div className="section-heading">
            <h2>今天怎么跑</h2>
            <span className="tag">{today}</span>
          </div>
          {todayTraining.length ? (
            todayTraining.map((t) => (
              <div className="training-note" key={t.id}>
                <h3>{t.title}</h3>
                <p className="muted">
                  {t.start_time}–{t.end_time}
                </p>
                <p className="preserve-lines">{t.note}</p>
                <span className="category training">
                  {
                    (
                      {
                        pending: "待训练",
                        done: "已完成",
                        partial: "部分完成",
                        skipped: "已跳过",
                      } as Record<string, string>
                    )[t.status]
                  }
                </span>
              </div>
            ))
          ) : (
            <Empty title="今天没有已确认的训练">
              休息也是训练的一部分。生成计划前，先填写你的训练目标和近期情况。
            </Empty>
          )}
        </section>
        <section className="paper-panel coach-note">
          <p className="eyebrow">YOUR WEEKLY TRAINING</p>
          <h2>有计划地，跑得更远。</h2>
          <p>结合近期跑量、成绩和可训练时间，整理一份可以核对和调整的计划。</p>
          <Link href="/settings" className="text-link">
            完善跑步档案 →
          </Link>
          <AIButton
            kind="training_plan"
            payload={{ week_start: monday }}
            label="✦ 生成本周训练草稿"
            onQueued={() => setJobRevision((x) => x + 1)}
          />
        </section>
      </div>
      {drafts.data?.plans
        .filter((d) => d.kind === "training_plan" && !d.applied)
        .map((d) => (
          <DraftPanel
            key={`${d.id}-${d.version}`}
            draft={d}
            onChanged={reload}
          />
        ))}
      <section className="paper-panel">
        <div className="section-heading">
          <h2>训练记录</h2>
          <span className="muted">{runs.data?.total || 0} 次记录</span>
        </div>
        {runs.loading && !runs.data ? <Loading /> : null}
        {runs.data?.items.length ? (
          <div className="run-records">
            {runs.data.items.map((r) => (
              <article key={r.id} className="run-row">
                <div>
                  <time>{r.date}</time>
                  <small>
                    {
                      (
                        {
                          done: "完整完成",
                          partial: "部分完成",
                          skipped: "已跳过",
                        } as Record<string, string>
                      )[r.status]
                    }
                  </small>
                </div>
                <strong>
                  {r.distance_km}
                  <small> km</small>
                </strong>
                <div>
                  <strong>{pace(r)}</strong>
                  <small>平均配速 / km</small>
                </div>
                <div>
                  <strong>
                    {r.duration_minutes}
                    <small> 分钟</small>
                  </strong>
                  <small>
                    疲劳 {r.effort}/10
                    {r.heart_rate ? ` · 心率 ${r.heart_rate}` : ""}
                  </small>
                </div>
                <button
                  className="button small secondary"
                  onClick={() => setEditing(r)}
                >
                  编辑
                </button>
                <button
                  className="button small quiet"
                  onClick={async () => {
                    if (!confirm("删除这次训练记录？关联待办会恢复为未完成。"))
                      return;
                    try {
                      await request(
                        `/records/runs/${r.id}?version=${r.version}`,
                        { method: "DELETE" },
                      );
                      reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  删除
                </button>
                {r.note ? <p className="run-note">{r.note}</p> : null}
                {r.discomfort ? (
                  <p className="run-note">身体反馈：{r.discomfort}</p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <Empty title="把第一段跑过的路记下来">
            记录距离、用时和感受，慢慢看见自己的进步。
          </Empty>
        )}
        <Pagination
          offset={offset}
          total={runs.data?.total || 0}
          onChange={setOffset}
        />
      </section>
      <section className="paper-panel">
        <div className="section-heading">
          <h2>跑道之外</h2>
          <Link href="/news?category=running">更多中长跑资讯 →</Link>
        </div>
        {news.data?.items.length ? (
          <div className="headline-grid">
            {news.data.items.slice(0, 3).map((n) => (
              <Link href={`/news?day=${n.date}&category=running`} key={n.id}>
                <small>{n.source}</small>
                <h3>{n.title}</h3>
                <p className="muted">{n.summary_zh.slice(0, 100)}</p>
              </Link>
            ))}
          </div>
        ) : (
          <p className="muted">赛事和运动员新闻会随每日新闻一起整理。</p>
        )}
      </section>
      <JobPanel refreshKey={jobRevision} onFinished={reload} />
      {editing ? (
        <RecordForm
          title={editing === "new" ? "记录训练" : "编辑训练记录"}
          fields={[
            ...baseFields,
            {
              name: "task_id",
              label: "关联训练任务",
              options: [
                ["", "不关联任务"],
                ...training.map(
                  (t) => [t.id, `${t.date} ${t.title}`] as [string, string],
                ),
              ],
            },
          ]}
          initial={
            editing === "new"
              ? {
                  date: today,
                  distance_km: 0,
                  duration_minutes: 0,
                  effort: 5,
                  status: "done",
                }
              : { ...editing }
          }
          onClose={() => setEditing(null)}
          onSave={async (value) => {
            const data = { ...value, task_id: value.task_id || null };
            if (editing === "new") await post("/records/runs", data);
            else
              await put(`/records/runs/${editing.id}`, {
                version: editing.version,
                data,
              });
            reload();
          }}
        />
      ) : null}
    </>
  );
}
