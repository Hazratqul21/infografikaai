import { useEffect, useState } from "react";
import {
  Sparkles, Users, ClipboardList, CheckCircle2, Ticket,
  LineChart, CreditCard, BarChart3, AlertTriangle, CircleDot,
} from "lucide-react";
import { api, type Dashboard as DashData } from "../lib/api";

type Go = (view: string, opt?: any) => void;

const fmt = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");

function Kpi({ Icon, num, label, onClick }: { Icon: any; num: string; label: string; onClick?: () => void }) {
  return (
    <div className="kpi" onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined}>
      <Icon size={20} className="icon-muted" strokeWidth={2} />
      <div>
        <div className="kpi-num">{num}</div>
        <div className="kpi-label">{label}</div>
      </div>
    </div>
  );
}

export default function Dashboard({ go }: { go: Go }) {
  const [d, setD] = useState<DashData | null>(null);
  useEffect(() => { api.dashboard().then(setD); }, []);
  if (!d) return <div className="screen" />;

  return (
    <div className="screen">
      {/* Sarlavha */}
      <div>
        <div className="greeting-title">
          <Sparkles size={20} color="var(--primary)" />
          Salom, Hazratqul
        </div>
        <div className="greeting-sub">Admin panel</div>
      </div>

      {/* KPI kartalar */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="kpi-grid">
          <Kpi Icon={Users} num={fmt(d.users)} label="Foydalanuvchilar" onClick={() => go("users")} />
          <Kpi Icon={ClipboardList} num={fmt(d.active_tasks)} label="Faol vazifalar" onClick={() => go("tasks", "active")} />
        </div>
        <div className="kpi-grid">
          <Kpi Icon={CheckCircle2} num={fmt(d.booked)} label="Band qilingan" onClick={() => go("tasks", "booked")} />
          <Kpi Icon={Ticket} num={fmt(d.total_credits)} label="Jami kredit" onClick={() => go("report")} />
        </div>
      </div>

      {/* Daromad kartasi */}
      <div className="card revenue">
        <div>
          <div className="revenue-num">
            <LineChart size={20} color="var(--primary)" />
            {fmt(d.revenue)} so'm
          </div>
          <div className="revenue-sub">Sof daromad</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div className="legend-row">
            <span className="dot" style={{ background: "var(--primary)" }} />
            Test/sherik: {fmt(d.test_amount)} so'm
          </div>
          <div className="legend-row">
            <span className="dot" style={{ background: "var(--lime)" }} />
            Kutilayotgan: {d.pending_count}
          </div>
        </div>
        <div className="bars">
          {d.chart.map((h, i) => (
            <div
              key={i}
              className="bar"
              style={{ height: Math.max(8, h * 0.6), opacity: 0.3 + i * 0.1 }}
            />
          ))}
        </div>
      </div>

      {/* Tez amallar */}
      <div className="chips">
        <button className="chip" onClick={() => go("payments")}>
          <CreditCard size={20} />
          To'lovlar
          {d.pending_count > 0 && <span className="badge badge-lime">{d.pending_count}</span>}
        </button>
        <button className="chip" onClick={() => go("users")}>
          <Users size={20} />
          Userlar
        </button>
        <button className="chip" onClick={() => go("report")}>
          <BarChart3 size={20} />
          Hisobot
        </button>
        <button className="chip" onClick={() => go("tasks", "error")}>
          <AlertTriangle size={20} />
          Xatoliklar
          {d.errors > 0 && <span className="badge badge-red">{d.errors}</span>}
        </button>
      </div>

      {/* Bot holati */}
      <div className="status-bar-row">
        <CircleDot size={20} color={d.session_ok ? "var(--green)" : "var(--red)"} />
        Faol · Uzum sessiya {d.session_ok ? "OK" : "XATO"} · {d.active_tasks} vazifa
      </div>
    </div>
  );
}
