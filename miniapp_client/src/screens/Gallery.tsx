import { useEffect, useState } from "react";
import { Images, X, Download, Sparkles } from "lucide-react";
import { api, type Generation } from "../lib/api";
import { GallerySkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { haptic, setBackButton } from "../lib/telegram";

export default function Gallery() {
  const [items, setItems] = useState<Generation[] | null>(null);
  const [open, setOpen] = useState<Generation | null>(null);
  const toast = useToast();

  useEffect(() => {
    api.generations()
      .then((r) => setItems(r.items))
      .catch((e) => {
        setItems([]);
        toast("error", e?.message || "Galereyani ochib bo'lmadi");
      });
  }, [toast]);

  // Modal ochiq bo'lsa Telegram «Orqaga» tugmasi uni yopsin
  useEffect(() => {
    if (!open) return;
    return setBackButton(() => setOpen(null));
  }, [open]);

  if (!items) return <GallerySkeleton />;

  const done = items.filter((g) => g.status === "completed" && g.result_url);
  const others = items.filter((g) => g.status !== "completed");

  return (
    <div className="screen">
      <div className="anim">
        <div className="page-title"><Images size={20} color="var(--primary)" /> Galereya</div>
        <div className="page-sub">
          {done.length > 0 ? `${done.length} ta tayyor ish` : "Ishlaringiz shu yerda saqlanadi"}
        </div>
      </div>

      {done.length === 0 && others.length === 0 && (
        <div className="empty-box anim d1">
          <div className="empty-ic float">
            <Sparkles size={30} color="var(--primary)" />
          </div>
          <div className="empty-t">Hozircha bo'sh</div>
          <div className="empty-s">
            «Yaratish» bo'limidan birinchi infografikangizni yasang —
            u shu yerda turadi va istagan vaqtda yuklab olasiz.
          </div>
        </div>
      )}

      {done.length > 0 && (
        <div className="gal">
          {done.map((g, i) => (
            <button className="gal-item" key={g.id}
                    style={{ animationDelay: `${Math.min(i * 0.06, 0.5)}s` }}
                    onClick={() => { haptic.tap(); setOpen(g); }}>
              <img src={g.result_url!} alt={g.product_name || "Infografika"} />
              {g.product_name && <span className="gal-tag">{g.product_name}</span>}
            </button>
          ))}
        </div>
      )}

      {/* Tugallanmagan/xato ishlar — mijoz nima bo'lganini bilsin */}
      {others.length > 0 && (
        <div className="anim d2">
          <div className="page-title" style={{ fontSize: 16, marginBottom: 10 }}>
            Boshqa ishlar
          </div>
          <div className="list">
            {others.map((g) => (
              <div className="row" key={g.id}>
                <div className="row-main">
                  <div className="row-title">{g.product_name || "Nomsiz tovar"}</div>
                  <div className="row-sub">
                    {g.status === "failed"
                      ? `${g.error || "Xato"} · ballar qaytarildi`
                      : "Tayyorlanmoqda…"}
                  </div>
                </div>
                <div className="row-trail">
                  <span className={"schip " + (g.status === "failed" ? "red" : "amber")}>
                    {g.status === "failed" ? "Xato" : "Navbatda"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {open?.result_url && (
        <div className="sheet" onClick={() => setOpen(null)}>
          <div className="sheet-inner" onClick={(e) => e.stopPropagation()}>
            <div className="result-wrap">
              <img className="result-img" src={open.result_url} alt="" />
            </div>
            <a className="btn btn-primary" href={open.result_url} target="_blank"
               rel="noreferrer" onClick={() => haptic.tap()}
               style={{ textDecoration: "none", display: "flex", alignItems: "center",
                        justifyContent: "center", gap: 8 }}>
              <Download size={18} /> Yuklab olish
            </a>
            <button className="btn btn-lav" onClick={() => setOpen(null)}>
              <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                <X size={18} /> Yopish
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
