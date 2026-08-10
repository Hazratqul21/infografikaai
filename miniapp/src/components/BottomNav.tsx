import { Home, Users, CreditCard, PieChart, Settings } from "lucide-react";

export type Screen = "dashboard" | "users" | "payments" | "report" | "settings";

const items: { key: Screen; label: string; Icon: any }[] = [
  { key: "dashboard", label: "Bosh sahifa", Icon: Home },
  { key: "users", label: "Userlar", Icon: Users },
  { key: "payments", label: "To'lovlar", Icon: CreditCard },
  { key: "report", label: "Hisobot", Icon: PieChart },
  { key: "settings", label: "Sozlamalar", Icon: Settings },
];

export default function BottomNav({
  active,
  onChange,
}: {
  active: Screen;
  onChange: (s: Screen) => void;
}) {
  return (
    <nav className="bottom-nav">
      <div className="bottom-nav-row">
        {items.map(({ key, label, Icon }) => {
          const isActive = active === key;
          return (
            <button
              key={key}
              className={"nav-item" + (isActive ? "" : " inactive")}
              onClick={() => onChange(key)}
            >
              <Icon size={24} color="#fff" strokeWidth={isActive ? 2.4 : 2} />
              <span>{label}</span>
              {isActive && <div className="nav-dot" />}
            </button>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "center", paddingBottom: 8 }}>
        <div style={{ width: 134, height: 5, borderRadius: 100, background: "rgba(255,255,255,0.3)" }} />
      </div>
    </nav>
  );
}
