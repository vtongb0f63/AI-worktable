"use client";
import { useState } from "react";
import Link from "next/link";
import {
  Course,
  CourseDraft,
  Draft,
  Task,
  useData,
  mondayLocal,
  todayLocal,
  shiftDay,
  dateLabel,
  post,
  put,
  request,
  clean,
  courseKeys,
  categoryName,
} from "@/lib/planner";
import {
  PageHeading,
  RecordForm,
  Field,
  Notice,
  Empty,
  Loading,
  AIButton,
  JobPanel,
} from "./Shared";
import { TaskEditor, taskFields } from "./Tasks";
export const courseFields: Field[] = [
  { name: "title", label: "课程名称", required: true },
  { name: "location", label: "上课地点" },
  {
    name: "weekday",
    label: "星期",
    options: ["一", "二", "三", "四", "五", "六", "日"].map((x, i) => [
      String(i),
      `星期${x}`,
    ]),
  },
  {
    name: "semester_start",
    label: "学期第一周日期",
    type: "date",
    required: true,
  },
  { name: "start_time", label: "上课时间", type: "time", required: true },
  { name: "end_time", label: "下课时间", type: "time", required: true },
  {
    name: "start_week",
    label: "开始周次",
    type: "number",
    min: 1,
    max: 60,
    required: true,
  },
  {
    name: "end_week",
    label: "结束周次",
    type: "number",
    min: 1,
    max: 60,
    required: true,
  },
  {
    name: "parity",
    label: "上课规律",
    options: [
      ["all", "每周"],
      ["odd", "单周"],
      ["even", "双周"],
    ],
  },
  {
    name: "excluded_dates",
    label: "停课或调出日期",
    type: "textarea",
    help: "每行一个日期，如 2026-10-21。临时调课可另加一条日程。",
  },
];
function courseBody(data: Record<string, unknown>) {
  return {
    ...data,
    weekday: Number(data.weekday),
    excluded_dates: String(data.excluded_dates || "")
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean),
  };
}
export function DraftPanel({
  draft,
  onChanged,
}: {
  draft: Draft;
  onChanged: () => void;
}) {
  const [plan, setPlan] = useState(draft.plan),
    [editing, setEditing] = useState<number | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="draft-panel">
      <div className="section-heading">
        <h3>
          {draft.kind === "training_plan" ? "训练计划草稿" : "周日程草稿"} ·{" "}
          {draft.week_start}
        </h3>
        <span className="tag">{draft.applied ? "已采用" : "等待确认"}</span>
      </div>
      <p>{plan.summary}</p>
      <ul className="draft-tasks">
        {plan.tasks.map((t, i) => (
          <li key={i}>
            <div>
              <small>
                {t.date} · {t.start_time}–{t.end_time}
              </small>
              <strong>{t.title}</strong>
              <p>{t.note}</p>
            </div>
            {!draft.applied ? (
              <div className="row-actions">
                <button
                  className="button small secondary"
                  onClick={() => setEditing(i)}
                >
                  编辑
                </button>
                <button
                  className="button small quiet"
                  onClick={() =>
                    setPlan({
                      ...plan,
                      tasks: plan.tasks.filter((_, index) => index !== i),
                    })
                  }
                >
                  移除
                </button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {plan.unscheduled.length ? (
        <p className="notice">暂未安排：{plan.unscheduled.join("；")}</p>
      ) : null}
      <Notice text={error} error />
      {!draft.applied ? (
        <button
          className="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const saved = await put<Draft>(`/drafts/plan/${draft.id}`, {
                version: draft.version,
                data: plan,
              });
              await post(`/drafts/plan/${draft.id}/adoption`, {
                version: saved.version,
                data: {},
              });
              onChanged();
            } catch (e) {
              setError((e as Error).message);
              onChanged();
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "正在保存…" : "确认采用这份计划"}
        </button>
      ) : null}
      {editing !== null ? (
        <RecordForm
          title="调整草稿安排"
          fields={taskFields}
          initial={{ ...plan.tasks[editing] }}
          onClose={() => setEditing(null)}
          onSave={async (data) => {
            setPlan({
              ...plan,
              tasks: plan.tasks.map((t, i) =>
                i === editing
                  ? ({
                      ...t,
                      ...data,
                      start_time: data.start_time || null,
                      end_time: data.end_time || null,
                      due_on: data.due_on || null,
                    } as typeof t)
                  : t,
              ),
            });
          }}
        />
      ) : null}
    </section>
  );
}
function CoursePreview({
  draft,
  onChanged,
}: {
  draft: CourseDraft;
  onChanged: () => void;
}) {
  const [courses, setCourses] = useState(draft.courses),
    [editing, setEditing] = useState<number | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="draft-panel">
      <h3>识别出的课表 · 请核对后导入</h3>
      {draft.warnings?.length ? (
        <Notice text={draft.warnings.join("；")} />
      ) : null}
      <ul className="draft-tasks">
        {courses.map((c, i) => (
          <li key={i}>
            <div>
              <strong>{c.title}</strong>
              <p>
                周{"一二三四五六日"[c.weekday]} {c.start_time}–{c.end_time} · 第
                {c.start_week}–{c.end_week}周 · {c.location}
              </p>
            </div>
            <button
              className="button small secondary"
              onClick={() => setEditing(i)}
            >
              核对 / 编辑
            </button>
            <button
              className="button small quiet"
              onClick={() => setCourses(courses.filter((_, idx) => i !== idx))}
            >
              移除
            </button>
          </li>
        ))}
      </ul>
      <Notice text={error} error />
      <button
        className="button"
        disabled={busy || !courses.length}
        onClick={async () => {
          setBusy(true);
          try {
            const saved = await put<CourseDraft>(`/drafts/course/${draft.id}`, {
              version: draft.version,
              data: { courses },
            });
            await post(`/drafts/course/${draft.id}/adoption`, {
              version: saved.version,
              data: {},
            });
            onChanged();
          } catch (e) {
            setError((e as Error).message);
            onChanged();
          } finally {
            setBusy(false);
          }
        }}
      >
        确认导入 {courses.length} 门课程
      </button>
      {editing !== null ? (
        <RecordForm
          title="核对课程"
          fields={courseFields}
          initial={{
            ...courses[editing],
            excluded_dates: courses[editing].excluded_dates.join("\n"),
          }}
          onClose={() => setEditing(null)}
          onSave={async (data) => {
            setCourses(
              courses.map((c, i) =>
                i === editing ? (courseBody(data) as typeof c) : c,
              ),
            );
          }}
        />
      ) : null}
    </section>
  );
}
export default function Schedule() {
  const [start, setStart] = useState(mondayLocal),
    [selectedDay, setSelectedDay] = useState(todayLocal),
    [editingCourse, setEditingCourse] = useState<Course | "new" | null>(null),
    [task, setTask] = useState<Task | "new" | null>(null),
    [error, setError] = useState(""),
    [jobRevision, setJobRevision] = useState(0),
    [uploading, setUploading] = useState(false);
  const calendar = useData<{ courses: Course[]; tasks: Task[] }>(
      `/calendar?start=${start}&end=${shiftDay(start, 6)}`,
    ),
    courses = useData<{ items: Course[] }>("/records/courses?limit=200"),
    drafts = useData<{ plans: Draft[]; courses: CourseDraft[] }>("/drafts");
  function reload() {
    calendar.reload();
    courses.reload();
    drafts.reload();
  }
  const days = Array.from({ length: 7 }, (_, i) => shiftDay(start, i));
  const activeDay = days.includes(selectedDay) ? selectedDay : days[0];
  return (
    <>
      <PageHeading
        eyebrow="MAKE ROOM FOR WHAT MATTERS"
        title="这一周，好好安排。"
        description="课程是固定坐标，其他时间留给你想完成的事。"
      >
        <button
          className="button secondary"
          onClick={() => setEditingCourse("new")}
        >
          ＋ 添加课程
        </button>
        <button className="button" onClick={() => setTask("new")}>
          ＋ 添加安排
        </button>
      </PageHeading>
      <div className="schedule-toolbar">
        <div className="week-switch">
          <button
            className="icon-button"
            aria-label="上一周"
            onClick={() => setStart(shiftDay(start, -7))}
          >
            ←
          </button>
          <strong>
            {dateLabel(start, { month: "short", day: "numeric" })} —{" "}
            {dateLabel(shiftDay(start, 6), { month: "short", day: "numeric" })}
          </strong>
          <button
            className="icon-button"
            aria-label="下一周"
            onClick={() => setStart(shiftDay(start, 7))}
          >
            →
          </button>
          <button
            className="button small quiet"
            onClick={() => setStart(mondayLocal())}
          >
            本周
          </button>
        </div>
        <AIButton
          kind="week_plan"
          payload={{ week_start: start }}
          label="✦ AI 帮我安排这一周"
          onQueued={() => setJobRevision((x) => x + 1)}
        />
      </div>
      <Notice text={error || calendar.error} error />
      {calendar.loading && !calendar.data ? <Loading /> : null}
      <div className="mobile-day-tabs" role="group" aria-label="选择星期">
        {days.map((day, i) => (
          <button
            className={activeDay === day ? "active" : ""}
            key={day}
            onClick={() => setSelectedDay(day)}
          >
            周{"一二三四五六日"[i]}
          </button>
        ))}
      </div>
      <section className="week-grid">
        {days.map((day) => (
          <div
            key={day}
            className={`week-day ${day === todayLocal() ? "today-column" : ""} ${activeDay === day ? "selected-day" : ""}`}
          >
            <header>
              <small>{dateLabel(day, { weekday: "short" })}</small>
              <strong>{new Date(day + "T12:00:00").getDate()}</strong>
            </header>
            <div className="day-events">
              {(calendar.data?.courses.filter((c) => c.date === day) || []).map(
                (c) => (
                  <button
                    key={c.id}
                    className="calendar-event course"
                    onClick={() => setEditingCourse(c)}
                  >
                    <time>
                      {c.start_time}–{c.end_time}
                    </time>
                    <strong>{c.title}</strong>
                    <small>{c.location}</small>
                  </button>
                ),
              )}
              {(calendar.data?.tasks.filter((t) => t.date === day) || []).map(
                (t) => (
                  <button
                    key={t.id}
                    className={`calendar-event ${t.category} ${t.status === "done" ? "is-done" : ""}`}
                    onClick={() => setTask(t)}
                  >
                    <time>
                      {t.start_time
                        ? `${t.start_time}–${t.end_time}`
                        : "自由安排"}
                    </time>
                    <strong>{t.title}</strong>
                    <small>
                      {categoryName[t.category]}
                      {t.locked ? " · 已锁定" : ""}
                      {t.status === "done" ? " · 已完成" : ""}
                    </small>
                  </button>
                ),
              )}
              <button
                className="add-day"
                aria-label={`在 ${day} 添加安排`}
                onClick={() => {
                  setSelectedDay(day);
                  setTask("new");
                }}
              >
                ＋
              </button>
            </div>
          </div>
        ))}
      </section>
      <section className="paper-panel import-panel">
        <div>
          <h2>把课程表放进来</h2>
          <p className="muted">
            上传截图或 PDF，由 AI 整理，核对后再导入。支持单双周与临时停课。
          </p>
          <Link className="text-link" href="/settings">
            先设置学期与节次时间 →
          </Link>
        </div>
        <label className="button secondary upload-label">
          {uploading ? "正在上传…" : "上传课表截图 / PDF"}
          <input
            aria-label="上传课表"
            type="file"
            accept="image/png,image/jpeg,application/pdf"
            disabled={uploading}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setUploading(true);
              try {
                const body = new FormData();
                body.append("file", file);
                const res = await fetch("/api/v1/course-imports", {
                  method: "POST",
                  body,
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.detail);
                setJobRevision((x) => x + 1);
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setUploading(false);
                e.target.value = "";
              }
            }}
          />
        </label>
      </section>
      {drafts.data?.courses
        .filter((d) => !d.applied)
        .map((d) => (
          <CoursePreview
            key={`${d.id}-${d.version}`}
            draft={d}
            onChanged={reload}
          />
        ))}
      {drafts.data?.plans
        .filter((d) => !d.applied && d.week_start === start)
        .map((d) => (
          <DraftPanel
            key={`${d.id}-${d.version}`}
            draft={d}
            onChanged={reload}
          />
        ))}
      <JobPanel refreshKey={jobRevision} onFinished={reload} />
      <details className="paper-panel">
        <summary>管理课程 · {courses.data?.items.length || 0} 门</summary>
        {courses.data?.items.map((c) => (
          <div className="job-row" key={c.id}>
            <div>
              <strong>{c.title}</strong>
              <p className="muted">
                周{"一二三四五六日"[c.weekday]} · 第{c.start_week}–{c.end_week}
                周
              </p>
            </div>
            <div>
              <button
                className="button small secondary"
                onClick={() => setEditingCourse(c)}
              >
                编辑
              </button>
              <button
                className="button small quiet"
                onClick={async () => {
                  if (!confirm(`删除课程「${c.title}」？`)) return;
                  try {
                    await request(
                      `/records/courses/${c.id}?version=${c.version}`,
                      { method: "DELETE" },
                    );
                    reload();
                  } catch (err) {
                    setError((err as Error).message);
                  }
                }}
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </details>
      {editingCourse ? (
        <RecordForm
          title={editingCourse === "new" ? "添加课程" : "编辑课程"}
          fields={courseFields}
          initial={
            editingCourse === "new"
              ? {
                  semester_start: todayLocal(),
                  start_week: 1,
                  end_week: 20,
                  parity: "all",
                }
              : {
                  ...editingCourse,
                  excluded_dates: editingCourse.excluded_dates.join("\n"),
                }
          }
          onClose={() => setEditingCourse(null)}
          onSave={async (data) => {
            const body = courseBody(data);
            if (editingCourse === "new") await post("/records/courses", body);
            else
              await put(`/records/courses/${editingCourse.id}`, {
                version: editingCourse.version,
                data: body,
              });
            reload();
          }}
        />
      ) : null}
      {task ? (
        <TaskEditor
          task={task === "new" ? undefined : task}
          day={activeDay}
          onClose={() => setTask(null)}
          onSaved={reload}
        />
      ) : null}
    </>
  );
}
