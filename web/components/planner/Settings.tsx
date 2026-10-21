"use client";
import { useState, useEffect } from "react";
import { Setting, useData, put } from "@/lib/planner";
import { PageHeading, Notice, Loading, JobPanel } from "./Shared";
export default function Settings() {
  const { data, error, loading, reload } = useData<Setting>("/settings");
  const [message, setMessage] = useState(""),
    [saveError, setSaveError] = useState(""),
    [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  if (loading && !data) return <Loading />;
  return (
    <>
      <PageHeading
        eyebrow="MAKE IT YOUR OWN"
        title="按你的节奏来。"
        description="这些信息会成为 AI 安排学习与训练的依据。"
      />
      <Notice text={error || saveError} error />
      <Notice text={message} />
      {data ? (
        <form
          key={data.version}
          className="settings-form"
          onChange={() => setDirty(true)}
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setSaveError("");
            const raw = Object.fromEntries(new FormData(e.currentTarget));
            try {
              await put("/settings", {
                version: Math.max(1, data.version),
                data: {
                  ...raw,
                  semester_start: raw.semester_start || null,
                  weekly_study_hours: Number(raw.weekly_study_hours),
                },
              });
              setDirty(false);
              setMessage("偏好已保存，下一次生成计划时生效");
              reload();
            } catch (err) {
              setSaveError((err as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <section className="paper-panel">
            <h2>学习与作息</h2>
            <p className="muted">先留出上课、睡眠和生活的时间，再安排学习。</p>
            <div className="form-grid">
              <label>
                学期第一周日期
                <input
                  name="semester_start"
                  type="date"
                  defaultValue={data.semester_start || ""}
                />
              </label>
              <label>
                每周自主学习时间（小时）
                <input
                  name="weekly_study_hours"
                  type="number"
                  min="1"
                  max="80"
                  defaultValue={data.weekly_study_hours}
                  required
                />
              </label>
              <label>
                起床时间
                <input
                  type="time"
                  name="wake_time"
                  defaultValue={data.wake_time}
                  required
                />
              </label>
              <label>
                休息时间
                <input
                  type="time"
                  name="sleep_time"
                  defaultValue={data.sleep_time}
                  required
                />
              </label>
              <label className="wide">
                本阶段学习目标
                <textarea
                  name="learning_goals"
                  rows={4}
                  defaultValue={data.learning_goals}
                  placeholder="例如：数学分析每周复习两章；C++ 每天练习30分钟；周五前完成作业…"
                />
              </label>
              <label className="wide">
                固定活动与时间限制
                <textarea
                  name="fixed_activities"
                  rows={3}
                  defaultValue={data.fixed_activities}
                  placeholder="例如：每天12:00–13:00午饭；周三晚社团；课间预留20分钟…"
                />
              </label>
              <label className="wide">
                学校节次时间
                <textarea name="periods" rows={5} defaultValue={data.periods} />
              </label>
            </div>
          </section>
          <section className="paper-panel">
            <h2>跑步档案</h2>
            <p className="muted">
              填写真实近况，生成的计划仍需要你核对后采用。
            </p>
            <div className="form-grid">
              <label className="wide">
                目标项目、成绩与日期
                <textarea
                  name="training_goal"
                  rows={2}
                  defaultValue={data.training_goal}
                  placeholder="例如：12月校运会1500米，希望跑进5分钟…"
                />
              </label>
              <label>
                近期成绩
                <textarea
                  name="recent_performance"
                  rows={3}
                  defaultValue={data.recent_performance}
                  placeholder="最近的1500米、5公里成绩或轻松跑配速…"
                />
              </label>
              <label>
                近四周每周跑量
                <textarea
                  name="weekly_mileage"
                  rows={3}
                  defaultValue={data.weekly_mileage}
                  placeholder="例如：15、18、16、20公里…"
                />
              </label>
              <label>
                可训练日与单次时长
                <textarea
                  name="training_days"
                  rows={3}
                  defaultValue={data.training_days}
                  placeholder="例如：周二、四、六傍晚，每次45分钟…"
                />
              </label>
              <label>
                伤病与当前身体状况
                <textarea
                  name="injury_notes"
                  rows={3}
                  defaultValue={data.injury_notes}
                  placeholder="没有不适可填“无”，有疲劳或伤痛请具体说明…"
                />
              </label>
            </div>
          </section>
          <section className="paper-panel">
            <h2>每天自动整理</h2>
            <p className="muted">
              统一使用北京时间。周计划生成草稿，确认后才进入日程。
            </p>
            <div className="form-grid">
              <label>
                日报时间
                <input
                  type="time"
                  name="news_time"
                  defaultValue={data.news_time}
                  required
                />
              </label>
              <label>
                周日生成下周草稿的时间
                <input
                  type="time"
                  name="weekly_time"
                  defaultValue={data.weekly_time}
                  required
                />
              </label>
              <label>
                英文摘要难度
                <select name="english_level" defaultValue={data.english_level}>
                  <option value="B1">B1 · 简明易读</option>
                  <option value="B2">B2 · 适度挑战</option>
                  <option value="C1">C1 · 进阶阅读</option>
                </select>
              </label>
            </div>
            <p className="subscription-note">
              AI 使用已连接的 ChatGPT
              订阅。额度不足时等待恢复，已有记录和手动功能仍可使用。
            </p>
          </section>
          <div className="sticky-save">
            <span className="muted">
              {dirty ? "有尚未保存的修改" : "你的安排，由你决定。"}
            </span>
            <button className="button" disabled={busy}>
              {busy ? "正在保存…" : "保存偏好与目标"}
            </button>
          </div>
        </form>
      ) : null}
      <JobPanel />
    </>
  );
}
