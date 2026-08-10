// Telegram WebApp SDK yordamchilari
type TG = any;

export function tg(): TG | null {
  return (window as any).Telegram?.WebApp ?? null;
}

export function initTelegram() {
  const w = tg();
  if (!w) return;
  try {
    w.ready();
    w.expand();
    // Header/fon rangini dizaynga moslash
    w.setHeaderColor?.("#f1ece0");
    w.setBackgroundColor?.("#f1ece0");
  } catch {
    /* dev brauzerда Telegram yo'q — e'tibor bermaymiz */
  }
}

// Backendга yuboriladigan autentifikatsiya (admin tekshiruvi shu orqali)
export function initData(): string {
  return tg()?.initData ?? "";
}
