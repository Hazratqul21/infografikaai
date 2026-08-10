import { Sparkles, Wand2, Images, Wallet, Clock } from "lucide-react";
import type { Me } from "../lib/api";
import type { Screen } from "../components/BottomNav";
import { HomeSkeleton } from "../components/Skeleton";

const fmt = (n: number) => n.toLocaleString("ru-RU").replace(/,/g, " ");

export default function Home({ me, go }: { me: Me | null; go: (s: Screen) => void }) {
  if (!me) return <HomeSkeleton />;

  const w = me.wallet;

  return (
    <div className="screen">
      <div className="anim">
        <div className="hero-badge">
          <Sparkles size={13} /> AI STUDIYA
        </div>
        <div className="greeting-title">
          INNASLOT Studio
        </div>
        <div className="greeting-sub">Tovaringizga infografika — 40 soniyada</div>
      </div>

      {/* Hamyon */}
      <div className="wallet anim d1">
        <div>
          <div className="wallet-num">
            {fmt(w.balls)}
            <span className="wallet-unit">ball</span>
          </div>
          <div className="wallet-label">Generatsiya balansi</div>
        </div>
        <div className="wallet-split">
          <div className="wallet-cell">
            <div className="n">{fmt(w.credits)}</div>
            <div className="l">Kredit (slot uchun)</div>
          </div>
          <div className="wallet-cell">
            <div className="n">{fmt(w.convertible_balls)}</div>
            <div className="l">Almashtirsa — ball</div>
          </div>
        </div>
        <button className="btn btn-lime shine" onClick={() => go("wallet")}>
          Kreditni ballga almashtirish
        </button>
      </div>

      {/* Ball tugagan bo'lsa — yo'l ko'rsatamiz */}
      {w.balls === 0 && (
        <div className="note warn">
          <div>
            <b>Ballaringiz tugagan.</b>
            <div style={{ marginTop: 4 }}>
              {w.credits > 0
                ? `Sizda ${w.credits} ta kredit bor — 1 kredit = ${w.balls_per_credit} ball.`
                : "Kredit sotib olish uchun botdagi «💎 Kredit sotib olish» bo'limiga o'ting."}
            </div>
          </div>
        </div>
      )}

      {/* Navbatdagi ishlar */}
      {me.open_jobs > 0 && (
        <div className="status-bar-row">
          <Clock size={20} color="var(--primary)" />
          {me.open_jobs} ta generatsiya tayyorlanmoqda…
        </div>
      )}

      {/* Tez amallar */}
      <div className="chips anim d2">
        <button className="chip" onClick={() => go("create")}>
          <Wand2 size={20} />
          Infografika yaratish
        </button>
        <button className="chip" onClick={() => go("gallery")}>
          <Images size={20} />
          Galereya
        </button>
        <button className="chip" onClick={() => go("wallet")}>
          <Wallet size={20} />
          Hamyon
        </button>
      </div>

      {/* Oxirgi natijalar */}
      {me.recent.length > 0 && (
        <div className="anim d3">
          <div className="page-title" style={{ fontSize: 16, marginBottom: 10 }}>
            Oxirgi ishlar
          </div>
          <div className="list">
            {me.recent.map((g) => (
              <div className="row" key={g.id}>
                <div className="avatar">
                  {g.result_url
                    ? <img src={g.result_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
                    : <Wand2 size={16} />}
                </div>
                <div className="row-main">
                  <div className="row-title">{g.product_name || "Nomsiz tovar"}</div>
                  <div className="row-sub">
                    {g.status === "completed" && "Tayyor"}
                    {g.status === "failed" && (g.error || "Xato")}
                    {(g.status === "pending" || g.status === "running") && "Tayyorlanmoqda…"}
                  </div>
                </div>
                <div className="row-trail">
                  <span className={"schip " + statusClass(g.status)}>
                    {statusLabel(g.status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function statusClass(s: string) {
  if (s === "completed") return "green";
  if (s === "failed") return "red";
  return "amber";
}

function statusLabel(s: string) {
  if (s === "completed") return "Tayyor";
  if (s === "failed") return "Xato";
  return "Navbatda";
}
