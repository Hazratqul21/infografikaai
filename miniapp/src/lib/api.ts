import { initData } from "./telegram";

const BASE = "/api";

async function call<T>(path: string, opts?: RequestInit, fallback?: T): Promise<T> {
  try {
    const res = await fetch(BASE + path, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData(),
        ...(opts?.headers || {}),
      },
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return (await res.json()) as T;
  } catch (e) {
    if (fallback !== undefined) return fallback;
    throw e;
  }
}
const post = <T>(p: string, body?: any, fb?: T) =>
  call<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }, fb);

// ── Turlar ──
export type Dashboard = {
  users: number; active_tasks: number; booked: number; total_credits: number;
  revenue: number; test_amount: number; pending_count: number; errors: number;
  session_ok: boolean; chart: number[];
};
export type UserRow = { id: number; name: string; username: string | null; credits: number; active: boolean; connected: boolean; created: string };
export type UsersResp = { total: number; page: number; pages: number; users: UserRow[] };
export type UserDetail = {
  id: number; name: string; username: string | null; active: boolean; credits: number;
  free_taken: boolean; created: string;
  shops: { shop_id: string; name: string | null }[];
  pay: { count: number; amount: number; credits: number; pending: number };
  stats: { active: number; booked: number; attempts: number; cancelled: number };
};
export type Payment = { order_id: string; uid: number; name: string; username: string | null; amount: number; credits: number; status: string; created: string; is_test: boolean };
export type Report = {
  total_users: number; with_credits: number; total_credits: number;
  d0: number; d1_5: number; d6_10: number; d11: number;
  paid_count: number; paid_amount: number; paid_credits: number; payers: number;
  pending_count: number; pending_amount: number; test_amount: number;
  top_holders: { telegram_id: number; username: string | null; full_name: string | null; credits: number }[];
  top_payers: { telegram_id: number; username: string | null; cnt: number; amt: number }[];
};
export type ActiveTask = { id: number; uid: number; shop_id: string; nakladnoy: string; attempts: number; target: string | null; pref: string; created: string };
export type ErrorTask = { id: number; uid: number; shop_id: string; reason: string; attempts: number; created: string };
export type Booked = { id: number; uid: number; name: string; username: string | null; shop_id: string; nakladnoy: string; when: string; booked_at: string };
export type Settings = { credit_price: number; free_credits: number; card_number: string; card_holder: string; excluded_ids: string; session_ok: boolean };

const D0: Dashboard = { users: 0, active_tasks: 0, booked: 0, total_credits: 0, revenue: 0, test_amount: 0, pending_count: 0, errors: 0, session_ok: false, chart: [0, 0, 0, 0, 0, 0, 0] };

export const api = {
  dashboard: () => call<Dashboard>("/dashboard", undefined, D0),
  users: (page = 0, q = "") => call<UsersResp>(`/users?page=${page}&q=${encodeURIComponent(q)}`, undefined, { total: 0, page: 0, pages: 1, users: [] }),
  user: (id: number) => call<UserDetail>(`/user/${id}`),
  ban: (id: number) => post<{ ok: boolean; active: boolean }>(`/user/${id}/ban`),
  addCredits: (id: number, amount: number) => post<{ ok: boolean; credits: number }>(`/user/${id}/credits`, { amount }),
  message: (id: number, text: string) => post<{ ok: boolean }>(`/user/${id}/message`, { text }),
  payments: (status = "") => call<Payment[]>(`/payments?status=${status}`, undefined, []),
  confirmPay: (oid: string) => post<{ ok: boolean }>(`/payment/${oid}/confirm`),
  rejectPay: (oid: string) => post<{ ok: boolean }>(`/payment/${oid}/reject`),
  report: () => call<Report>("/report"),
  tasks: (status: "active" | "error") => call<any[]>(`/tasks?status=${status}`, undefined, []),
  booked: () => call<Booked[]>("/booked", undefined, []),
  settings: () => call<Settings>("/settings"),
  saveSettings: (s: Partial<Settings>) => post<Settings>("/settings", s),
  broadcast: (text: string, target: string) => post<{ ok: boolean; sent: number; total: number }>("/broadcast", { text, target }),
};
