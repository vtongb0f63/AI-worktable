"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
export { todayLocal, mondayLocal } from "./api";
export type Entity = {
  id: string;
  version: number;
  created_at: string;
  updated_at: string;
};
export type Task = Entity & {
  title: string;
  date: string;
  category: string;
  note: string;
  status: string;
  locked: boolean;
  start_time: string | null;
  end_time: string | null;
  due_on: string | null;
  source_id: string | null;
};
export type Course = Entity & {
  title: string;
  start_time: string;
  end_time: string;
  weekday: number;
  semester_start: string;
  start_week: number;
  end_week: number;
  parity: string;
  location: string;
  excluded_dates: string[];
  date?: string;
};
export type Word = Entity & {
  term: string;
  phonetic_uk: string;
  meaning: string;
  part_of_speech: string;
  example: string;
  source: string;
  tags: string;
  stage: number;
  review_on: string;
  wrong_count: number;
};
export type Run = Entity & {
  date: string;
  training_type: string;
  distance_km: number;
  duration_minutes: number;
  effort: number;
  heart_rate: number | null;
  status: string;
  task_id: string | null;
  note: string;
  discomfort: string;
  splits: string;
};
export type News = Entity & {
  date: string;
  title: string;
  category: string;
  source: string;
  url: string;
  published_at: string;
  summary_zh: string;
  summary_en: string;
  bookmarked: boolean;
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  error: string | null;
  result: { type?: string; record_id?: string } | null;
  created_at: string;
};
export type Plan = {
  summary: string;
  tasks: Omit<Task, keyof Entity>[];
  unscheduled: string[];
};
export type Draft = Entity & {
  plan: Plan;
  week_start: string;
  kind: string;
  applied: boolean;
  rejected?: boolean;
  last_revision?: {
    feedback: string;
    changed_indices: number[];
    changes: { before: Plan["tasks"][number]; after: Plan["tasks"] }[];
  } | null;
};
export type CourseDraft = Entity & {
  courses: (Omit<Course, keyof Entity | "start_time" | "end_time" | "weekday"> & { start_time: string | null; end_time: string | null; weekday: number | null })[];
  warnings: string[];
  applied: boolean;
};
export type Setting = Entity & {
  semester_start: string | null;
  periods: string;
  wake_time: string;
  sleep_time: string;
  fixed_activities: string;
  learning_goals: string;
  weekly_study_hours: number;
  news_time: string;
  weekly_time: string;
  english_level: string;
  training_goal: string;
  recent_performance: string;
  weekly_mileage: string;
  training_days: string;
  injury_notes: string;
};
export type Page<T> = { items: T[]; total: number };
export const request = <T>(path: string, options: RequestInit = {}) =>
  api<T>(`/v1${path}`, options);
export const post = <T>(path: string, value: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(value) });
export const put = <T>(path: string, value: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(value) });
export const categoryName: Record<string, string> = {
  study: "学习",
  life: "生活",
  vocabulary: "词汇",
  training: "跑步",
  domestic: "国内",
  international: "国际",
  ai: "AI 模型",
  running: "中长跑",
};
export const jobNames: Record<string, string> = {
  plan_revision: "计划局部修改",
  week_plan: "周日程",
  training_plan: "训练计划",
  news: "每日新闻",
  quiz: "词汇练习",
  grade: "翻译批改",
  course_import: "课表识别",
  word_enrich: "词义补全",
};
export const jobStates: Record<string, string> = {
  pending: "排队中",
  running: "正在整理",
  blocked: "等待恢复",
  failed: "未完成",
  done: "已完成",
  cancelled: "已取消",
};
export function useData<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    setLoading(true);
    setError("");
    request<T>(path, { signal: abort.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [path, revision]);
  return { data, error, loading, reload };
}
export function clean<T extends object>(value: T, keys: string[]) {
  return Object.fromEntries(
    keys.map((k) => [k, (value as Record<string, unknown>)[k]]),
  );
}
export const taskKeys = [
  "title",
  "date",
  "category",
  "note",
  "status",
  "locked",
  "start_time",
  "end_time",
  "due_on",
  "source_id",
];
export const courseKeys = [
  "title",
  "start_time",
  "end_time",
  "weekday",
  "semester_start",
  "start_week",
  "end_week",
  "parity",
  "location",
  "excluded_dates",
];
export const wordKeys = [
  "term",
  "phonetic_uk",
  "meaning",
  "part_of_speech",
  "example",
  "source",
  "tags",
];
export const runKeys = [
  "date",
  "training_type",
  "distance_km",
  "duration_minutes",
  "effort",
  "heart_rate",
  "status",
  "task_id",
  "note",
  "discomfort",
  "splits",
];
export function shiftDay(day: string, by: number) {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + by);
  return d.toISOString().slice(0, 10);
}
export function dateLabel(
  day: string,
  options: Intl.DateTimeFormatOptions = {
    month: "long",
    day: "numeric",
    weekday: "long",
  },
) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    ...options,
  }).format(new Date(`${day}T12:00:00+08:00`));
}
