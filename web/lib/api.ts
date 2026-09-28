export type Kind = 'vision' | 'year' | 'semester' | 'month' | 'week' | 'task';
export type Node = {
  id: string; parent_id: string | null; kind: Kind; title: string; note: string;
  starts_on: string | null; ends_on: string | null; due_on: string | null;
  weight: number; is_public: number; is_done: number; is_main: number;
  is_week_focus: number; position: number; hidden_at: string | null;
  created_at: string; updated_at: string; progress: number;
};
export type Me = { id: string; email: string; username: string; start_date: string | null; timezone: string; is_admin: number };
export type Event = { id: string; node_id: string | null; kind: string; detail: Record<string, unknown>; occurred_at: string };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(typeof data.detail === 'string' ? data.detail : `请求失败 (${response.status})`, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const kindLabel: Record<Kind, string> = {
  vision: '四年愿景', year: '学年目标', semester: '学期目标', month: '月里程碑', week: '周重点', task: '每日任务',
};

export function todayLocal(timezone = 'Asia/Shanghai') {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (type: string) => parts.find(x => x.type === type)?.value || '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function mondayLocal(timezone = 'Asia/Shanghai') {
  const date = new Date(`${todayLocal(timezone)}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}
