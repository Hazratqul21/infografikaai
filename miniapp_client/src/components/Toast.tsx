import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";
import { haptic } from "../lib/telegram";

/**
 * Toast — qisqa xabarlar (muvaffaqiyat/xato) uchun.
 *
 * Nega kerak: xato xabarini forma ichida ko'rsatsak, foydalanuvchi
 * ekranning boshqa joyida bo'lsa uni umuman ko'rmaydi. Toast doim
 * ko'rinadigan joyda chiqadi va o'zi yo'qoladi.
 */

type Kind = "success" | "error" | "info";
type Item = { id: number; kind: Kind; text: string };

const Ctx = createContext<(kind: Kind, text: string) => void>(() => {});

export const useToast = () => useContext(Ctx);

let seq = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);

  const push = useCallback((kind: Kind, text: string) => {
    if (!text) return;
    const id = seq++;
    setItems((prev) => [...prev.slice(-2), { id, kind, text }]);
    if (kind === "success") haptic.success();
    if (kind === "error") haptic.error();
    setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, kind === "error" ? 5000 : 3000);
  }, []);

  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toast-wrap">
        {items.map((t) => (
          <Toast key={t.id} item={t}
                 onClose={() => setItems((p) => p.filter((x) => x.id !== t.id))} />
        ))}
      </div>
    </Ctx.Provider>
  );
}

function Toast({ item, onClose }: { item: Item; onClose: () => void }) {
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setLeaving(true), item.kind === "error" ? 4700 : 2700);
    return () => clearTimeout(t);
  }, [item.kind]);

  const Icon = item.kind === "success" ? CheckCircle2
    : item.kind === "error" ? AlertTriangle : Info;

  return (
    <div className={`toast toast-${item.kind}` + (leaving ? " leaving" : "")}>
      <Icon size={18} style={{ flex: "none" }} />
      <div style={{ flex: 1 }}>{item.text}</div>
      <button className="toast-x" onClick={onClose} aria-label="Yopish">
        <X size={15} />
      </button>
    </div>
  );
}
