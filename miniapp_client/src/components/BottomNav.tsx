import { Home, Wand2, Images, Wallet } from "lucide-react";

export type Screen = "home" | "create" | "gallery" | "wallet";

// Keyingi modullar (gabarit, hujjatlar) shu yerga qo'shiladi.
const items: { key: Screen; label: string; Icon: any }[] = [
  { key: "home", label: "Bosh sahifa", Icon: Home },
  { key: "create", label: "Yaratish", Icon: Wand2 },
  { key: "gallery", label: "Galereya", Icon: Images },
  { key: "wallet", label: "Hamyon", Icon: Wallet },
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
