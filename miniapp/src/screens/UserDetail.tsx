import { useEffect, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { api, type UserDetail as UD } from "../lib/api";
import { fmt, initials, uname } from "../lib/util";

export default function UserDetail({ id, back }: { id: number; back: () => void }) {
  const [u, setU] = useState<UD | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgStatus, setMsgStatus] = useState("");
  const [credit, setCredit] = useState("5");
  const load = () => api.user(id).then(setU);
  useEffect(() => { load(); }, [id]);

  if (!u) return <div className="screen" />;

  const ban = async () => {
    if (busy) return;
    setBusy(true);
    const r = await api.ban(id);
    setU({ ...u, active: r.active });
    setBusy(false);
  };
  // prompt()/alert() Telegram Mini App webview'da BLOKLANGAN -> inline UI
  const sendMsg = async () => {
    if (!msg.trim() || busy) return;
    setBusy(true); setMsgStatus("");
    const r = await api.message(id, msg.trim());
    setBusy(false);
    if (r.ok) { setMsg(""); setMsgStatus("✅ Yuborildi"); }
    else setMsgStatus("❌ Yuborilmadi (user botni bloklagan bo'lishi mumkin)");
    setTimeout(() => setMsgStatus(""), 4000);
  };
  const addCredits = async () => {
    const n = parseInt(credit, 10);
    if (!n || busy) return;
    setBusy(true);
    const r = await api.addCredits(id, n);
    setU({ ...u, credits: r.credits });
    setBusy(false);
  };

  return (
    <div className="screen">
      <div className="topbar">
        <button className="back-btn" onClick={back}><ChevronLeft size={20} /></button>
        <div className="page-title">Foydalanuvchi</div>
      </div>

      {/* Profil */}
      <div className="card pad" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div className="avatar" style={{ width: 52, height: 52, fontSize: 20 }}>{initials(u.name)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{u.name}</div>
          <div style={{ opacity: 0.55, fontSize: 13 }}>{uname(u.username)} · <code>{u.id}</code></div>
        </div>
        <span className={"schip " + (u.active ? "green" : "red")}>{u.active ? "🟢 Faol" : "🔴 Bloklangan"}</span>
      </div>

      {/* Kredit + bepul */}
      <div className="card pad">
        <div className="info"><span className="k">💰 Kreditlar</span><span className="v mini-num">{u.credits}</span></div>
        <div className="info"><span className="k">🎁 Bepul olgan</span><span className="v">{u.free_taken ? "✅ ha" : "❌ yo'q"}</span></div>
        <div className="info"><span className="k">📅 Ro'yxatdan</span><span className="v">{(u.created || "").slice(0, 10)}</span></div>
      </div>

      {/* Do'konlar */}
      <div className="card pad">
        <div style={{ fontWeight: 700, marginBottom: 6 }}>🏪 Do'konlar ({u.shops.length})</div>
        {u.shops.length === 0 && <div style={{ opacity: 0.5, fontSize: 13 }}>Yo'q</div>}
        {u.shops.map((s) => (
          <div key={s.shop_id} className="info">
            <span className="k"><code>{s.shop_id}</code></span>
            <span className="v" style={{ fontWeight: 500, opacity: 0.6 }}>{s.name || ""}</span>
          </div>
        ))}
      </div>

      {/* To'lovlar */}
      <div className="card pad">
        <div className="info"><span className="k">💳 To'lovlar</span><span className="v">{u.pay.count} ta · {fmt(u.pay.amount)} so'm</span></div>
        <div className="info"><span className="k">🧾 Sotib olgan kredit</span><span className="v">+{u.pay.credits}</span></div>
        <div className="info"><span className="k">⏳ Kutilayotgan</span><span className="v">{u.pay.pending}</span></div>
      </div>

      {/* Vazifalar */}
      <div className="card pad">
        <div className="info"><span className="k">📋 Faol vazifalar</span><span className="v">{u.stats.active}</span></div>
        <div className="info"><span className="k">✅ Olingan slot</span><span className="v">{u.stats.booked}</span></div>
        <div className="info"><span className="k">🔄 Jami urinish</span><span className="v">{fmt(u.stats.attempts)}</span></div>
        <div className="info"><span className="k">❌ Bekor qilingan</span><span className="v">{u.stats.cancelled}</span></div>
      </div>

      {/* 💬 Xabar yuborish (inline — bot orqali, username kerak emas) */}
      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontWeight: 700 }}>💬 Xabar yuborish (bot orqali)</div>
        <textarea
          className="field"
          placeholder="Xabar matni..."
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
        />
        <button className="btn btn-primary" disabled={busy || !msg.trim()} onClick={sendMsg}>
          📤 Yuborish
        </button>
        {msgStatus && (
          <div style={{ textAlign: "center", fontWeight: 700, color: msgStatus.startsWith("✅") ? "var(--green)" : "var(--red)" }}>
            {msgStatus}
          </div>
        )}
      </div>

      {/* 💰 Kredit boshqaruvi (inline) */}
      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontWeight: 700 }}>💰 Kredit qo'shish / ayirish</div>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="field"
            type="number"
            value={credit}
            onChange={(e) => setCredit(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="btn btn-lav" disabled={busy} onClick={addCredits} style={{ width: "auto", padding: "13px 20px" }}>
            ➕ Qo'shish
          </button>
        </div>
        <div style={{ fontSize: 12, opacity: 0.5 }}>Manfiy son (masalan -2) = ayirish</div>
      </div>

      <button className={"btn " + (u.active ? "btn-red" : "btn-green")} disabled={busy} onClick={ban}>
        {u.active ? "🚫 Ban qilish" : "✅ Unban qilish"}
      </button>
    </div>
  );
}
