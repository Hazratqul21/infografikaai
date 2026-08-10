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
    // Tasodifan yopib yubormasin — generatsiya ketayotgan bo'lishi mumkin
    w.enableClosingConfirmation?.();
  } catch {
    /* dev brauzerда Telegram yo'q — e'tibor bermaymiz */
  }
}

// Backendга yuboriladigan autentifikatsiya
export function initData(): string {
  return tg()?.initData ?? "";
}

/**
 * Haptika — tugma bosilganda telefon tebranadi.
 * Mini App'ni "sayt" emas, "ilova" qilib ko'rsatadigan eng arzon vosita.
 * Telegram tashqarisida jimgina o'tkazib yuboriladi.
 */
export const haptic = {
  tap(style: "light" | "medium" | "heavy" = "light") {
    try { tg()?.HapticFeedback?.impactOccurred?.(style); } catch { /* yo'q */ }
  },
  success() {
    try { tg()?.HapticFeedback?.notificationOccurred?.("success"); } catch { /* yo'q */ }
  },
  error() {
    try { tg()?.HapticFeedback?.notificationOccurred?.("error"); } catch { /* yo'q */ }
  },
  select() {
    try { tg()?.HapticFeedback?.selectionChanged?.(); } catch { /* yo'q */ }
  },
};

/**
 * Telegram'ning tepadagi «Orqaga» tugmasi.
 * Bo'lmasa foydalanuvchi ichki ekrandan chiqolmay, ilovani butunlay yopadi.
 * Qaytaradigan funksiya — tozalash (useEffect uchun).
 */
export function setBackButton(handler: (() => void) | null): () => void {
  const bb = tg()?.BackButton;
  if (!bb) return () => {};

  const wrapped = () => handler?.();
  try {
    if (handler) {
      bb.onClick(wrapped);
      bb.show();
    } else {
      bb.hide();
    }
  } catch { /* eski Telegram versiyasi */ }

  return () => {
    try { bb.offClick(wrapped); } catch { /* yo'q */ }
  };
}
