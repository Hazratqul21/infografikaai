import { useEffect, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { api, type Payment } from "../lib/api";
import { fmt, initials, uname } from "../lib/util";

const TABS = [
  { key: "pending", label: "Kutilayotgan" },
  { key: "confirmed", label: "Tasdiqlangan" },
  { key: "cancelled", label: "Rad etilgan" },
] as const;

const statusChip = (s: string, isTest: boolean) => {
  if (s === "pending") return <span className="schip amber">⏳ Kutilmoqda</span>;
  if (s === "confirmed") return <span className={"schip " + (isTest ? "gray" : "green")}>{isTest ? "🧪 Test" : "✅ Tasdiqlangan"}</span>;
  return <span className="schip red">❌ Rad</span>;
};

export default function Payments() {
  const [tab, setTab] = useState<string>("pending");
  const [list, setList] = useState<Payment[] | null>(null);
  const [sel, setSel] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.payments(tab).then(setList);
  useEffect(() => { setList(null); load(); }, [tab]);

  const doConfirm = async () => {
    if (!sel || busy) return;
    setBusy(true);
    await api.confirmPay(sel.order_id);
    setBusy(false); setSel(null); load();
  };
  const doReject = async () => {
    if (!sel || busy) return;
    setBusy(true);
    await api.rejectPay(sel.order_id);
    setBusy(false); setSel(null); load();
  };

  // ── Tafsilot (bir bosishda tasdiqlamaydi) ──
  if (sel) {
    return (
      <div className="screen">
        <div className="topbar">
          <button className="back-btn" onClick={() => setSel(null)}><ChevronLeft size={20} /></button>
          <div className="page-title">To'lov tafsiloti</div>
        </div>
        <div className="card pad" style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div className="avatar" style={{ width: 48, height: 48 }}>{initials(sel.name)}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700 }}>{sel.name}</div>
            <div style={{ opacity: 0.55, fontSize: 13 }}>{uname(sel.username)} · <code>{sel.uid}</code></div>
          </div>
        </div>
        <div className="card pad">
          <div className="info"><span className="k">🧾 So'ralgan</span><span className="v mini-num">{sel.credits} kredit</span></div>
          <div className="info"><span className="k">💰 Summa</span><span className="v">{fmt(sel.amount)} so'm</span></div>
          <div className="info"><span className="k">📊 Holat</span><span className="v">{statusChip(sel.status, sel.is_test)}</span></div>
          <div className="info"><span className="k">📅 Sana</span><span className="v" style={{ fontWeight: 500 }}>{sel.created}</span></div>
          <div className="info"><span className="k">📋 Buyurtma</span><span className="v" style={{ fontSize: 11 }}><code>{sel.order_id}</code></span></div>
        </div>
        {sel.status === "pending" && (
          <>
            <div style={{ textAlign: "center", opacity: 0.6, fontSize: 13 }}>
              ⬇️ Tasdiqlasangiz <b>{sel.credits} kredit</b> qo'shiladi
            </div>
            <div className="btn-row">
              <button className="btn btn-green" disabled={busy} onClick={doConfirm}>✅ Tasdiqlash</button>
              <button className="btn btn-red" disabled={busy} onClick={doReject}>❌ Rad etish</button>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="screen">
      <div className="page-title">💳 To'lovlar</div>
      <div className="seg">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "on" : ""} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>
      <div className="list">
        {list?.map((p) => (
          <button key={p.order_id} className="row" onClick={() => setSel(p)}>
            <div className="avatar">{initials(p.name)}</div>
            <div className="row-main">
              <div className="row-title">{fmt(p.amount)} so'm · {p.credits} kr</div>
              <div className="row-sub">{p.name} · {uname(p.username)} · {p.created}</div>
            </div>
            <div className="row-trail">{statusChip(p.status, p.is_test)}</div>
          </button>
        ))}
        {list && list.length === 0 && <div className="empty">To'lov yo'q</div>}
      </div>
    </div>
  );
}
