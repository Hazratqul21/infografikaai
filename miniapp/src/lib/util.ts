export const fmt = (n: number) => (n ?? 0).toLocaleString("ru-RU").replace(/,/g, " ");
export const initials = (name: string) => (name || "?").trim().charAt(0).toUpperCase();
export const uname = (u: string | null) => (u ? "@" + u : "—");
