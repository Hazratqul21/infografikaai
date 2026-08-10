import { useEffect, useState } from "react";
import { api, type Settings as S } from "../lib/api";

export default function Settings() {
  const [s, setS] = useState<S | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [bText, setBText] = useState("");
  const [bTarget, setBTarget] = useState("all");
  const [bResult, setBResult] = useState("");

  useEffect(() => { api.settings().then(setS); }, []);
  if (!s) return <div className="screen" />;

  const set = (k: keyof S, v: any) => setS({ ...s, [k]: v });

  const save = async () => {
    setBusy(true); setMsg("");
    const r = await api.saveSettings({
      credit_price: s.credit_price, free_credits: s.free_credits,
      card_number: s.card_number, card_holder: s.card_holder,
      excluded_ids: s.excluded_ids,
    });
    setS(r); setBusy(false); setMsg("✅ Saqlandi");
    setTimeout(() => setMsg(""), 2000);
  };

  const send = async () => {
    if (!bText.trim() || busy) return;
    if (!confirm(`Xabar yuborilsinmi?\n\n"${bText.slice(0, 80)}..."`)) return;
    setBusy(true); setBResult("");
    const r = await api.broadcast(bText, bTarget);
    setBusy(false); setBResult(`✅ ${r.sent}/${r.total} ga yuborildi`); setBText("");
  };

  return (
    <div className="screen">
      <div className="page-title">⚙️ Sozlamalar</div>

      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontWeight: 700 }}>💰 Narx & Kredit</div>
        <label style={{ fontSize: 13, opacity: 0.6 }}>1 kredit narxi (so'm)</label>
        <input className="field" type="number" value={s.credit_price} onChange={(e) => set("credit_price", +e.target.value)} />
        <label style={{ fontSize: 13, opacity: 0.6 }}>Bepul kredit (yangi user)</label>
        <input className="field" type="number" value={s.free_credits} onChange={(e) => set("free_credits", +e.target.value)} />
      </div>

      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontWeight: 700 }}>💳 To'lov kartasi</div>
        <input className="field" placeholder="Karta raqami" value={s.card_number} onChange={(e) => set("card_number", e.target.value)} />
        <input className="field" placeholder="Karta egasi" value={s.card_holder} onChange={(e) => set("card_holder", e.target.value)} />
      </div>

      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontWeight: 700 }}>🚫 Daromaddan chiqarilgan ID lar</div>
        <div style={{ fontSize: 12, opacity: 0.55 }}>Vergul bilan (siz + sheriklar). Bularning to'lovi daromadga kirmaydi.</div>
        <input className="field" value={s.excluded_ids} onChange={(e) => set("excluded_ids", e.target.value)} />
      </div>

      <button className="btn btn-primary" disabled={busy} onClick={save}>💾 Saqlash {msg}</button>

      {/* Uzum sessiya */}
      <div className="status-bar-row">
        {s.session_ok ? "🟢 Uzum sessiya faol (OK)" : "🔴 Uzum sessiya XATO — botni tekshiring"}
      </div>

      {/* Broadcast */}
      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontWeight: 700 }}>📢 Broadcast (barchaga xabar)</div>
        <div className="seg">
          {[["all", "Hammaga"], ["credits", "Krediti bor"], ["connected", "Do'koni bor"]].map(([k, l]) => (
            <button key={k} className={bTarget === k ? "on" : ""} onClick={() => setBTarget(k)}>{l}</button>
          ))}
        </div>
        <textarea className="field" placeholder="Xabar matni (HTML mumkin)..." value={bText} onChange={(e) => setBText(e.target.value)} />
        <button className="btn btn-primary" disabled={busy || !bText.trim()} onClick={send}>📤 Yuborish</button>
        {bResult && <div style={{ textAlign: "center", color: "var(--green)", fontWeight: 700 }}>{bResult}</div>}
      </div>
    </div>
  );
}
