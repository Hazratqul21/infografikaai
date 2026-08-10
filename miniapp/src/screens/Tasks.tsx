import { useEffect, useState } from "react";
import { api, type ActiveTask, type ErrorTask, type Booked } from "../lib/api";
import { fmt, initials, uname } from "../lib/util";

const TABS = [
  { key: "active", label: "Faol" },
  { key: "booked", label: "Band qilingan" },
  { key: "error", label: "Xatoliklar" },
] as const;

const prefLabel: Record<string, string> = { any: "🔄 Istalgan", morning: "🌅 Ertalab", evening: "🌆 Kechqurun" };

export default function Tasks({ initial = "active" }: { initial?: string }) {
  const [tab, setTab] = useState<string>(initial);
  const [rows, setRows] = useState<any[] | null>(null);

  useEffect(() => {
    setRows(null);
    if (tab === "booked") api.booked().then(setRows);
    else api.tasks(tab as "active" | "error").then(setRows);
  }, [tab]);

  return (
    <div className="screen">
      <div className="page-title">📋 Vazifalar</div>
      <div className="seg">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "on" : ""} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      <div className="list">
        {tab === "active" && (rows as ActiveTask[] | null)?.map((t) => (
          <div key={t.id} className="row" style={{ cursor: "default" }}>
            <div className="row-main">
              <div className="row-title">⏳ #{t.id} · 🏪 {t.shop_id}</div>
              <div className="row-sub">📦 {t.nakladnoy} · {prefLabel[t.pref] || t.pref}{t.target ? " · 📅 " + t.target : ""}</div>
            </div>
            <div className="row-trail">
              <span className="schip gray">{fmt(t.attempts)}x</span>
              <span style={{ fontSize: 11, opacity: 0.4 }}>id {t.uid}</span>
            </div>
          </div>
        ))}

        {tab === "booked" && (rows as Booked[] | null)?.map((b) => (
          <div key={b.id} className="row" style={{ cursor: "default", alignItems: "flex-start" }}>
            <div className="avatar">{initials(b.name)}</div>
            <div className="row-main">
              <div className="row-title">✅ {b.name} {uname(b.username) !== "—" && <span style={{ opacity: 0.5, fontWeight: 400 }}>{uname(b.username)}</span>}</div>
              <div className="row-sub" style={{ whiteSpace: "normal" }}>🏪 {b.shop_id} · 📦 {b.nakladnoy}</div>
              <div className="row-sub" style={{ whiteSpace: "normal", color: "var(--primary)", opacity: 0.9, fontWeight: 600 }}>🕐 {b.when}</div>
            </div>
            <div className="row-trail"><span style={{ fontSize: 11, opacity: 0.4 }}>{b.booked_at}</span></div>
          </div>
        ))}

        {tab === "error" && (rows as ErrorTask[] | null)?.map((t) => (
          <div key={t.id} className="row" style={{ cursor: "default" }}>
            <div className="row-main">
              <div className="row-title">⚠️ #{t.id} · 🏪 {t.shop_id}</div>
              <div className="row-sub" style={{ color: "var(--red)", whiteSpace: "normal" }}>{t.reason}</div>
            </div>
            <div className="row-trail">
              <span className="schip gray">{fmt(t.attempts)}x</span>
              <span style={{ fontSize: 11, opacity: 0.4 }}>id {t.uid}</span>
            </div>
          </div>
        ))}

        {rows && rows.length === 0 && <div className="empty">Yo'q</div>}
        {!rows && <div className="empty">Yuklanmoqda...</div>}
      </div>
    </div>
  );
}
