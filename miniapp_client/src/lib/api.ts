import { initData } from "./telegram";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
      ...(opts?.headers || {}),
    },
  });
  if (!res.ok) {
    // Backend xatoni {detail: "..."} shaklida qaytaradi — mijozga o'shani
    // ko'rsatamiz (u o'zbekcha va tushunarli qilib yozilgan).
    let msg = "Xatolik yuz berdi";
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch { /* json emas — umumiy xabar qoladi */ }
    throw new ApiError(msg, res.status);
  }
  return (await res.json()) as T;
}

const post = <T>(p: string, body?: any) =>
  call<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });

// ── Turlar ──
export type Wallet = {
  credits: number;
  balls: number;
  balls_per_credit: number;
  convertible_balls: number;
};

export type Generation = {
  id: number;
  action_id: string | null;
  kind: string;
  status: "pending" | "running" | "completed" | "failed";
  product_name: string | null;
  result_url: string | null;
  error: string | null;
  created_at: number;
};

export type Me = {
  wallet: Wallet;
  free_retries: number;
  recent: Generation[];
  open_jobs: number;
};

export type Style = {
  id: number;
  name: string | null;
  source_url: string;
  creativity: number;
  is_default: number;
};

export type ImageInput = { url: string } | { data: string; media_type: string };

export const api = {
  me: () => call<Me>("/me"),
  convert: (credits: number) =>
    post<{ ok: boolean; balls: number; added: number }>("/convert", { credits }),
  generateCard: (body: {
    images: ImageInput[];
    product_name?: string;
    use_style?: boolean;
    wishes?: string;
    description?: string;
    parent_id?: number;
    retry?: boolean;
  }) => post<{ id: number; action_id: string; status: string }>("/generate/card", body),
  enhance: (id: number, instruction: string) =>
    post<{ id: number; action_id: string; status: string }>(
      `/generation/${id}/enhance`, { instruction }),
  suggest: (product_name: string) =>
    post<{ product_name?: string; description?: string; wishes?: string }>(
      "/suggest", { product_name }),
  generation: (id: number) => call<Generation>(`/generation/${id}`),
  generations: (limit = 30) =>
    call<{ items: Generation[] }>(`/generations?limit=${limit}`),
  styles: () => call<{ items: Style[] }>("/styles"),
  addStyle: (source_url: string, name?: string, creativity = 0.3) =>
    post<{ ok: boolean; id: number }>("/styles", { source_url, name, creativity }),
};
