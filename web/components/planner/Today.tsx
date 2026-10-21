"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Task,
  Course,
  Run,
  News,
  useData,
  todayLocal,
  dateLabel,
} from "@/lib/planner";
import { PageHeading, Notice, Empty, Loading, JobPanel } from "./Shared";
import { TaskList, TaskEditor } from "./Tasks";
type Overview = {
  date: string;
  tasks: Task[];
  courses: Course[];
  due_words: number;
  runs: Run[];
  news: News[];
};
export default function Today() {
  const [day, setDay] = useState(todayLocal),
    [adding, setAdding] = useState(false);
  const { data, error, loading, reload } = useData<Overview>(
    `/overview?day=${day}`,
  );
  const pending = data?.tasks.filter((t) => t.status !== "done") || [],
    done = data?.tasks.filter((t) => t.status === "done") || [];
  return (
    <>
      <PageHeading
        eyebrow="MY DAILY NOTEBOOK"
        title={day === todayLocal() ? "今天，慢慢来。" : dateLabel(day)}
        description="看清安排，专注一件，再完成一件。"
      >
        <label className="date-control">
          <span className="sr-only">查看日期</span>
          <input
            type="date"
            name="day"
            value={day}
            onChange={(e) => e.target.value && setDay(e.target.value)}
          />
        </label>
        <button className="button" onClick={() => setAdding(true)}>
          ＋ 添加待办
        </button>
      </PageHeading>
      <Notice text={error} error />
      {loading && !data ? <Loading /> : null}
      <section className="day-banner">
        <div>
          <p className="eyebrow">{dateLabel(day)}</p>
          <h2>给今天留一张清晰的清单。</h2>
          <p>
            {pending.length
              ? `还有 ${pending.length} 件事等你完成。`
              : "从一件小事开始，也很好。"}{" "}
            已完成的努力都会记下来。
          </p>
        </div>
        <div className="daily-progress">
          <strong>
            {done.length}
            <span> / {data?.tasks.length || 0}</span>
          </strong>
          <small>今日完成</small>
          <progress
            aria-label="今日任务完成进度"
            value={done.length}
            max={Math.max(1, data?.tasks.length || 0)}
          />
        </div>
      </section>
      <div className="today-grid">
        <section className="paper-panel">
          <div className="section-heading">
            <h2>今日待办</h2>
            <span className="muted">{pending.length} 件待完成</span>
          </div>
          {pending.length ? (
            <TaskList tasks={pending} onChanged={reload} />
          ) : (
            <Empty title="这页还有空白">
              添加学习、阅读或跑步安排，也可以到周日程让 AI 帮你规划。
            </Empty>
          )}
          {done.length ? (
            <details className="completed-list">
              <summary>已完成 · {done.length}</summary>
              <TaskList tasks={done} onChanged={reload} />
            </details>
          ) : null}
          <Link className="text-link" href={`/journal?day=${day}`}>
            看看今天留下的记录 →
          </Link>
        </section>
        <aside className="right-rail">
          <section className="paper-panel">
            <div className="section-heading">
              <h2>今天的课程</h2>
              <Link href="/schedule">课表 →</Link>
            </div>
            {data?.courses.length ? (
              <ol className="class-timeline">
                {data.courses
                  .sort((a, b) => a.start_time.localeCompare(b.start_time))
                  .map((c) => (
                    <li key={`${c.id}-${c.date}`}>
                      <time>{c.start_time}</time>
                      <div>
                        <strong>{c.title}</strong>
                        <small>
                          {c.end_time} 下课 · {c.location || "未填写教室"}
                        </small>
                      </div>
                    </li>
                  ))}
              </ol>
            ) : (
              <p className="muted">
                今天没有已录入的课程。
                <Link href="/schedule">查看或导入课表</Link>
              </p>
            )}
          </section>
          <Link className="feature-card vocabulary-card" href="/words">
            <div>
              <p className="eyebrow">WORDS TO KEEP</p>
              <h2>今天记住一点。</h2>
              <p>{data?.due_words || 0} 个单词等待复习</p>
            </div>
            <span className="feature-symbol" aria-hidden="true">
              Aa
            </span>
          </Link>
          <Link className="feature-card running-card" href="/running">
            <div>
              <p className="eyebrow">ONE STEP FURTHER</p>
              <h2>跑过的路，都算数。</h2>
              <p>
                {data?.tasks.find((t) => t.category === "training")?.title ||
                  "查看训练计划与运动记录"}{" "}
                →
              </p>
            </div>
            <span className="feature-symbol" aria-hidden="true">
              ↗
            </span>
          </Link>
        </aside>
      </div>
      <section className="paper-panel news-preview">
        <div className="section-heading">
          <h2>今天，世界发生了什么</h2>
          <Link href="/news">读一读日报 →</Link>
        </div>
        {data?.news.length ? (
          <div className="headline-grid">
            {data.news.slice(0, 3).map((n) => (
              <Link key={n.id} href={`/news?day=${day}`}>
                <small>{n.source}</small>
                <h3>{n.title}</h3>
              </Link>
            ))}
          </div>
        ) : (
          <p className="muted">
            日报每天 7 点整理，生成后会出现在这里。也可以去新闻页手动更新。
          </p>
        )}
      </section>
      <JobPanel onFinished={reload} />
      {adding ? (
        <TaskEditor
          day={day}
          onClose={() => setAdding(false)}
          onSaved={reload}
        />
      ) : null}
    </>
  );
}
