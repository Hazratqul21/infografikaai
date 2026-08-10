import { useState } from "react";
import { Wallet, ArrowRight, Info } from "lucide-react";
import { api, type Me } from "../lib/api";
import { WalletSkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { haptic } from "../lib/telegram";

const fmt = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");

export default function WalletScreen({
  me, refresh,
}: {
  me: Me | null;
  refresh: () => Promise<void>;
}) {
  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  if (!me) return <WalletSkeleton />;
  const w = me.wallet;
  const max = Math.max(1, w.credits);
  const value = Math.min(qty, max);

  // Tez tanlov: 1 / 3 / 5 / hammasi — slayderni surish shart emas
  const quick = [1, 3, 5].filter((n) => n <= max);

  async function convert() {
    setBusy(true);
    haptic.tap("medium");
    try {
      const r = await api.convert(value);
      toast("success", `${r.added} ball qo'shildi · balans ${r.balls} ball`);
      await refresh();
      setQty(1);
    } catch (e: any) {
      toast("error", e?.message || "Almashtirib bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen">
      <div className="anim">
        <div className="page-title"><Wallet size={20} color="var(--primary)" /> Hamyon</div>
        <div className="page-sub">Kredit va generatsiya ballari</div>
      </div>

      <div className="wallet anim d1">
        <div>
          <div className="wallet-num">
            {fmt(w.balls)}<span className="wallet-unit">ball</span>
          </div>
          <div className="wallet-label">Generatsiya uchun</div>
        </div>
        <div className="wallet-split">
          <div className="wallet-cell">
            <div className="n">{fmt(w.credits)}</div>
            <div className="l">Kredit</div>
          </div>
          <div className="wallet-cell">
            <div className="n">1 : {w.balls_per_credit}</div>
            <div className="l">Almashuv kursi</div>
          </div>
        </div>
      </div>

      {/* Almashtirish */}
      <div className="card pad anim d2" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Kreditni ballga almashtirish</div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, opacity: .55, marginBottom: 6 }}>Kredit</div>
            <div className="mini-num">{value}</div>
          </div>
          <ArrowRight size={20} className="icon-muted" />
          <div style={{ flex: 1, textAlign: "right" }}>
            <div style={{ fontSize: 12, opacity: .55, marginBottom: 6 }}>Ball</div>
            <div className="mini-num" style={{ color: "var(--primary)" }}>
              {value * w.balls_per_credit}
            </div>
          </div>
        </div>

        {w.credits > 1 && (
          <div className="quick">
            {quick.map((n) => (
              <button key={n} className={value === n ? "on" : ""}
                      onClick={() => { haptic.select(); setQty(n); }}>
                {n}
              </button>
            ))}
            <button className={value === max ? "on" : ""}
                    onClick={() => { haptic.select(); setQty(max); }}>
              Hammasi
            </button>
          </div>
        )}

        <input type="range" min={1} max={max} value={value}
               aria-label="Almashtiriladigan kredit soni"
               onChange={(e) => setQty(Number(e.target.value))}
               style={{ width: "100%", accentColor: "var(--primary)" }} />

        <button className={"btn btn-primary" + (w.credits >= 1 ? " shine" : "")}
                disabled={busy || w.credits < 1}
                style={{ opacity: (busy || w.credits < 1) ? .5 : 1 }}
                onClick={convert}>
          {busy ? "Almashtirilmoqda…" : `${value} kreditni almashtirish`}
        </button>

        {w.credits < 1 && (
          <div className="note warn">
            <div>
              Kreditingiz yo'q. Botdagi <b>«💎 Kredit sotib olish»</b> bo'limidan
              to'ldiring.
            </div>
          </div>
        )}
      </div>

      <div className="note anim d3">
        <Info size={18} className="icon-muted" style={{ flex: "none" }} />
        <div>
          <b>Muhim:</b> almashtirilgan ball qaytarib kreditga aylantirilmaydi.
          Generatsiya muvaffaqiyatsiz tugasa — ball avtomatik qaytariladi.
        </div>
      </div>
    </div>
  );
}
