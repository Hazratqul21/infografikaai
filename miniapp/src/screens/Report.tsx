import { useEffect, useState } from "react";
import { api, type Report as Rep } from "../lib/api";
import { fmt, uname } from "../lib/util";

function Bar({ label, val, max, color }: { label: string; val: number; max: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
      <div style={{ width: 44, opacity: 0.6 }}>{label}</div>
      <div style={{ flex: 1, height: 10, background: "rgba(0,0,0,.05)", borderRadius: 6 }}>
        <div style={{ width: `${max ? (val / max) * 100 : 0}%`, height: "100%", background: color, borderRadius: 6, minWidth: val ? 6 : 0 }} />
      </div>
      <div style={{ width: 32, textAlign: "right", fontWeight: 700 }}>{val}</div>
    </div>
  );
}

export default function Report() {
  const [r, setR] = useState<Rep | null>(null);
  useEffect(() => { api.report().then(setR); }, []);
  if (!r) return <div className="screen" />;
  const maxDist = Math.max(r.d0, r.d1_5, r.d6_10, r.d11, 1);

  return (
    <div className="screen">
      <div className="page-title">💰 Kredit & Daromad</div>

      {/* Umumiy */}
      <div className="card pad">
        <div className="info"><span className="k">👥 Foydalanuvchi</span><span className="v">{fmt(r.total_users)} (krediti bor: {r.with_credits})</span></div>
        <div className="info"><span className="k">🎟 Jami kredit qoldiq</span><span className="v mini-num">{fmt(r.total_credits)}</span></div>
      </div>

      {/* Taqsimot */}
      <div className="card pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontWeight: 700 }}>📊 Kredit taqsimoti</div>
        <Bar label="0" val={r.d0} max={maxDist} color="#9aa" />
        <Bar label="1–5" val={r.d1_5} max={maxDist} color="var(--primary)" />
        <Bar label="6–10" val={r.d6_10} max={maxDist} color="var(--green)" />
        <Bar label="11+" val={r.d11} max={maxDist} color="var(--amber)" />
      </div>

      {/* Daromad */}
      <div className="card pad">
        <div style={{ fontWeight: 600, opacity: 0.5, fontSize: 13 }}>Sof daromad (real)</div>
        <div className="revenue-num" style={{ fontSize: 26, marginTop: 4 }}>{fmt(r.paid_amount)} so'm</div>
        <div style={{ opacity: 0.6, fontSize: 13, marginTop: 4 }}>{r.paid_count} to'lov · {r.payers} mijoz · {r.paid_credits} kredit</div>
        <div className="info" style={{ marginTop: 10 }}><span className="k">🧪 Test/sherik (kirmaydi)</span><span className="v">{fmt(r.test_amount)} so'm</span></div>
        <div className="info"><span className="k">⏳ Kutilayotgan</span><span className="v">{r.pending_count} ta · {fmt(r.pending_amount)} so'm</span></div>
      </div>

      {/* Top kreditli */}
      {r.top_holders.length > 0 && (
        <div className="card pad">
          <div style={{ fontWeight: 700, marginBottom: 6 }}>🏆 Eng ko'p kreditli</div>
          {r.top_holders.map((h) => (
            <div key={h.telegram_id} className="info">
              <span className="k">{uname(h.username) !== "—" ? uname(h.username) : (h.full_name || h.telegram_id)}</span>
              <span className="v">{h.credits} kr</span>
            </div>
          ))}
        </div>
      )}

      {/* Top to'lovchilar */}
      {r.top_payers.length > 0 && (
        <div className="card pad">
          <div style={{ fontWeight: 700, marginBottom: 6 }}>💳 Top to'lovchilar</div>
          {r.top_payers.map((p) => (
            <div key={p.telegram_id} className="info">
              <span className="k">{uname(p.username) !== "—" ? uname(p.username) : p.telegram_id}</span>
              <span className="v">{fmt(p.amt)} so'm · {p.cnt}x</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
