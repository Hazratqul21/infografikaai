import { useEffect, useRef, useState } from "react";
import {
  Wand2, X, ImagePlus, Download, Bookmark, RotateCcw, Check, Sparkles, Send,
} from "lucide-react";
import { api, type Generation, type ImageInput, type Me, type Style } from "../lib/api";
import { prepareImage, type Prepared } from "../lib/image";
import { useToast } from "../components/Toast";
import { haptic, setBackButton } from "../lib/telegram";

const MAX_IMAGES = 5;
// Aidentika 20-60 soniyada tayyorlaydi; birinchi so'rovni 8s dan keyin
// yuboramiz (undan oldin baribir "running" keladi — bekorga so'rov).
const POLL_FIRST_DELAY = 8000;
const POLL_INTERVAL = 4000;
// Yozilgan matn saqlanadi: mijoz ilovani yopib qaytsa, qaytadan yozmasin
const DRAFT_KEY = "innaslot.studio.draft";

type Draft = { name: string; wishes: string; description: string };

function loadDraft(): Draft {
  try {
    return { name: "", wishes: "", description: "",
             ...JSON.parse(localStorage.getItem(DRAFT_KEY) || "{}") };
  } catch {
    return { name: "", wishes: "", description: "" };
  }
}

export default function Create({
  me, refresh, goGallery,
}: {
  me: Me | null;
  refresh: () => Promise<void>;
  goGallery: () => void;
}) {
  const draft = useRef<Draft>(loadDraft());
  const [images, setImages] = useState<Prepared[]>([]);
  const [name, setName] = useState(draft.current.name);
  const [wishes, setWishes] = useState(draft.current.wishes);
  const [description, setDescription] = useState(draft.current.description);
  const [suggesting, setSuggesting] = useState(false);
  const [useStyle, setUseStyle] = useState(true);
  const [styles, setStyles] = useState<Style[]>([]);
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState<Generation | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [saved, setSaved] = useState(false);
  const [fix, setFix] = useState("");            // «yaxshilash» matni
  const timer = useRef<any>(null);
  const toast = useToast();

  useEffect(() => {
    api.styles().then((r) => setStyles(r.items)).catch(() => {});
    return () => clearInterval(timer.current);
  }, []);

  // Qoralamani saqlash (har o'zgarishda, arzon amal)
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ name, wishes, description }));
    } catch { /* xotira to'la — muhim emas */ }
  }, [name, wishes, description]);

  // Natija/kutish ekranida Telegram «Orqaga» — formaga qaytaradi
  useEffect(() => {
    if (!gen) return setBackButton(null);
    return setBackButton(() => setGen(null));
  }, [gen]);

  // ── Natijani kutish (poll) ──
  useEffect(() => {
    if (!gen || gen.status === "completed" || gen.status === "failed") return;

    let stopped = false;
    const tick = async () => {
      if (stopped) return;
      try {
        const fresh = await api.generation(gen.id);
        if (stopped) return;
        setGen(fresh);
        if (fresh.status === "completed") {
          clearInterval(timer.current);
          haptic.success();
          window.scrollTo({ top: 0, behavior: "smooth" });
          refresh();
        } else if (fresh.status === "failed") {
          clearInterval(timer.current);
          haptic.error();
          refresh();
        }
      } catch {
        /* vaqtinchalik tarmoq xatosi — keyingi urinishda qayta so'raymiz */
      }
    };

    const start = setTimeout(() => {
      tick();
      timer.current = setInterval(tick, POLL_INTERVAL);
    }, POLL_FIRST_DELAY);
    const sec = setInterval(() => setElapsed((e) => e + 1), 1000);

    return () => {
      stopped = true;
      clearTimeout(start);
      clearInterval(timer.current);
      clearInterval(sec);
    };
  }, [gen?.id, gen?.status, refresh]);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";               // bir xil faylni qayta tanlash uchun
    if (!files.length) return;
    const room = MAX_IMAGES - images.length;
    if (room <= 0) {
      toast("info", `Ko'pi bilan ${MAX_IMAGES} ta rasm`);
      return;
    }
    if (files.length > room) {
      toast("info", `Faqat ${room} ta rasm qo'shildi (jami ${MAX_IMAGES} ta)`);
    }
    try {
      const prepared = await Promise.all(files.slice(0, room).map(prepareImage));
      setImages((prev) => [...prev, ...prepared]);
      haptic.tap();
    } catch (err: any) {
      toast("error", err?.message || "Rasmni o'qib bo'lmadi");
    }
  }

  // «AI g'oya» — nom/tavsif/pojelaniyani AI taklif qiladi (bepul)
  async function aiIdea() {
    setSuggesting(true);
    haptic.tap();
    try {
      const s = await api.suggest(name.trim());
      if (s.product_name && !name.trim()) setName(s.product_name);
      if (s.description) setDescription(s.description);
      if (s.wishes) setWishes(s.wishes);
      if (!s.description && !s.wishes && !s.product_name) {
        toast("info", "AI hozir taklif bera olmadi — o'zingiz yozib ko'ring");
      } else {
        toast("success", "AI takliflari to'ldirildi");
      }
    } catch (e: any) {
      toast("error", e?.message || "AI g'oya olinmadi");
    } finally {
      setSuggesting(false);
    }
  }

  async function launch(retry = false) {
    if (!images.length) {
      toast("info", "Avval tovar rasmini tanlang");
      return;
    }
    setBusy(true);
    setSaved(false);
    setFix("");
    haptic.tap("medium");
    try {
      const payload: ImageInput[] = images.map((i) => ({
        data: i.data, media_type: i.media_type,
      }));
      const res = await api.generateCard({
        images: payload,
        product_name: name.trim(),
        description: description.trim(),
        wishes: wishes.trim(),
        use_style: useStyle && styles.length > 0,
        retry,
        parent_id: retry && gen ? gen.id : undefined,
      });
      setElapsed(0);
      setGen({
        id: res.id, action_id: res.action_id, kind: "card",
        status: "pending", product_name: name.trim(),
        result_url: null, error: null, created_at: Date.now() / 1000,
      });
      window.scrollTo({ top: 0 });
      refresh();
    } catch (e: any) {
      toast("error", e?.message || "Generatsiya boshlanmadi");
    } finally {
      setBusy(false);
    }
  }

  // «Yaxshilash» — tayyor natijani matn bilan tuzatish
  async function enhance() {
    if (!gen || fix.trim().length < 3) {
      toast("info", "Nima o'zgartirishni yozing");
      return;
    }
    setBusy(true);
    haptic.tap("medium");
    try {
      const res = await api.enhance(gen.id, fix.trim());
      setElapsed(0);
      setGen({
        id: res.id, action_id: res.action_id, kind: "edit",
        status: "pending", product_name: gen.product_name,
        result_url: null, error: null, created_at: Date.now() / 1000,
      });
      setFix("");
      window.scrollTo({ top: 0 });
      refresh();
    } catch (e: any) {
      toast("error", e?.message || "Yaxshilab bo'lmadi");
    } finally {
      setBusy(false);
    }
  }

  async function saveAsStyle() {
    if (!gen?.result_url) return;
    haptic.tap();
    try {
      await api.addStyle(gen.result_url, name.trim() || "Mening uslubim");
      setSaved(true);
      setStyles((await api.styles()).items);
      toast("success", "Uslub saqlandi — keyingi kartochkalar shu dizaynda chiqadi");
    } catch (e: any) {
      toast("error", e?.message || "Uslub saqlanmadi");
    }
  }

  function reset() {
    setGen(null); setImages([]); setName(""); setWishes(""); setDescription("");
    setElapsed(0); setSaved(false); setFix("");
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* muhim emas */ }
    window.scrollTo({ top: 0 });
  }

  const balls = me?.wallet.balls ?? 0;
  const freeLeft = me?.free_retries ?? 0;
  const working = gen && (gen.status === "pending" || gen.status === "running");

  // ───────── Natija ekrani ─────────
  if (gen?.status === "completed" && gen.result_url) {
    return (
      <div className="screen">
        <div className="anim">
          <div className="page-title"><Check size={20} color="var(--green)" /> Tayyor!</div>
          <div className="page-sub">{gen.product_name || "Infografika"}</div>
        </div>

        <div className="result-wrap anim d1">
          <img className="result-img" src={gen.result_url} alt="Tayyor infografika" />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}
             className="anim d2">
          <a className="btn btn-primary shine" href={gen.result_url} target="_blank"
             rel="noreferrer" onClick={() => haptic.tap()}
             style={{ textAlign: "center", textDecoration: "none",
                      display: "flex", alignItems: "center",
                      justifyContent: "center", gap: 8 }}>
            <Download size={18} /> Yuklab olish
          </a>

          {/* USLUB XOTIRASI — bizning asosiy ustunligimiz */}
          <button className="btn btn-lav" onClick={saveAsStyle} disabled={saved}>
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <Bookmark size={18} />
              {saved ? "Uslub saqlandi ✓" : "Shu uslubni saqlash"}
            </span>
          </button>

          {/* QAYTA YARATISH — Aidentikadagi 3 ta bepul almashtirish */}
          <button className="btn btn-lav" disabled={busy} onClick={() => launch(true)}>
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <RotateCcw size={18} />
              {freeLeft > 0 ? `Qayta yaratish · bepul (${freeLeft})` : "Qayta yaratish · 1 ball"}
            </span>
          </button>
        </div>

        {/* YAXSHILASH — Aidentikadagi «Улучшение» */}
        <div className="card pad anim d3" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontWeight: 700, fontSize: 14 }}>Biror narsani o'zgartiramizmi?</div>
          <textarea className="field" value={fix} maxLength={500}
                    style={{ minHeight: 70 }}
                    aria-label="Nimani o'zgartirish kerak"
                    onChange={(e) => setFix(e.target.value)}
                    placeholder="Masalan: fonni ochroq qil, matnni kattalashtir" />
          <button className="btn btn-primary" disabled={busy || balls < 1 || fix.trim().length < 3}
                  style={{ opacity: (busy || balls < 1 || fix.trim().length < 3) ? .5 : 1 }}
                  onClick={enhance}>
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <Send size={17} /> Yaxshilash · 1 ball
            </span>
          </button>
        </div>

        <div className="btn-row anim d4">
          <button className="btn btn-lav" onClick={reset}>Yangi tovar</button>
          <button className="btn btn-lav" onClick={goGallery}>Galereya</button>
        </div>
      </div>
    );
  }

  // ───────── Kutish ekrani ─────────
  if (working) {
    const pct = Math.min(95, 8 + elapsed * 2.2);
    return (
      <div className="screen">
        <div className="anim">
          <div className="page-title"><Wand2 size={20} color="var(--primary)" /> Tayyorlanmoqda</div>
          <div className="page-sub">Odatda 20–60 soniya oladi</div>
        </div>

        {images[0] && (
          <div className="result-wrap">
            <img className="result-img pulse" src={images[0].preview} alt="" />
          </div>
        )}

        <div className="progress">
          <div className="progress-bar" style={{ width: `${pct}%` }} />
        </div>
        <div style={{ textAlign: "center", fontSize: 13, opacity: .6 }}>
          {elapsed} soniya…
        </div>

        <div className="note">
          <div>
            Ilovani yopsangiz ham bo'ladi — tayyor bo'lganda natija
            <b> Galereya</b> bo'limida turadi.
          </div>
        </div>
      </div>
    );
  }

  // ───────── Xato ekrani ─────────
  if (gen?.status === "failed") {
    return (
      <div className="screen">
        <div className="empty-box anim">
          <div className="empty-ic">
            <X size={30} color="var(--red)" />
          </div>
          <div className="empty-t">Generatsiya bajarilmadi</div>
          <div className="empty-s">{gen.error || "Noma'lum xato"}</div>
          <div className="empty-s">
            Ballaringiz <b>qaytarildi</b> — hech narsa yechilmadi.
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => setGen(null)}>
          Qayta urinish
        </button>
      </div>
    );
  }

  // ───────── Yaratish formasi ─────────
  return (
    <div className="screen">
      <div className="anim">
        <div className="page-title"><Wand2 size={20} color="var(--primary)" /> Infografika yaratish</div>
        <div className="page-sub">Tovar rasmini yuklang — qolganini bot qiladi</div>
      </div>

      {images.length > 0 && (
        <div className="thumbs">
          {images.map((im, i) => (
            <div className="thumb" key={i}
                 style={{ animationDelay: `${i * 0.05}s` }}>
              <img src={im.preview} alt={`Tanlangan rasm ${i + 1}`} />
              <button className="thumb-x" aria-label="Rasmni olib tashlash"
                      onClick={() => { haptic.tap(); setImages(images.filter((_, k) => k !== i)); }}>
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {images.length < MAX_IMAGES && (
        <label className="dropzone anim d1">
          <div className="ic float">
            <ImagePlus size={26} color="var(--primary)" />
          </div>
          <div className="t">
            {images.length ? "Yana rasm qo'shish" : "Tovar rasmini tanlang"}
          </div>
          <div className="s">
            JPG yoki PNG · {MAX_IMAGES} tagacha
            <br />Turli tomondan olingan bir necha rasm — natija yaxshiroq
          </div>
          <input type="file" accept="image/*" multiple onChange={onPick} />
        </label>
      )}

      <div className="anim d2">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, opacity: .7 }}>Tovar nomi</div>
          <button className="chip" style={{ padding: "6px 12px", fontSize: 12 }}
                  disabled={suggesting} onClick={aiIdea}>
            <Sparkles size={15} color="var(--primary)" className={suggesting ? "spin" : ""} />
            {suggesting ? "O'ylanmoqda…" : "AI g'oya"}
          </button>
        </div>
        <input className="field" value={name} maxLength={200}
               aria-label="Tovar nomi"
               onChange={(e) => setName(e.target.value)}
               placeholder="Masalan: Termos 500 ml" />
      </div>

      {description && (
        <div className="anim">
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, opacity: .7 }}>
            Tavsif
          </div>
          <textarea className="field" value={description} maxLength={2000}
                    style={{ minHeight: 80 }} aria-label="Tovar tavsifi"
                    onChange={(e) => setDescription(e.target.value)} />
        </div>
      )}

      {/* POJELANIYA — Aidentikadagi «Пожелания» */}
      <div className="anim d3">
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, opacity: .7 }}>
          Qanday bo'lsin? (ixtiyoriy)
        </div>
        <textarea className="field" value={wishes} maxLength={1000}
                  style={{ minHeight: 80 }} aria-label="Dizayn bo'yicha istaklar"
                  onChange={(e) => setWishes(e.target.value)}
                  placeholder="Uslub, rang, kayfiyat, kompozitsiya…" />
        <div style={{ fontSize: 11, opacity: .5, marginTop: 6, lineHeight: 1.5 }}>
          💡 «Fonni ko'k qil» deb yozing — «qizil qilma» deb emas.
          AI nima <b>kerakligini</b> yaxshi tushunadi.
        </div>
      </div>

      {styles.length > 0 && (
        <div className="anim d4">
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, opacity: .7 }}>
            Dizayn uslubi
          </div>
          <div className="style-row">
            <button className={"style-card" + (useStyle ? " on" : "")}
                    onClick={() => { haptic.select(); setUseStyle(true); }}>
              <div className="box">
                <img src={styles.find((s) => s.is_default)?.source_url || styles[0].source_url}
                     alt="Saqlangan uslub" />
              </div>
              <div className="cap">Mening uslubim</div>
            </button>
            <button className={"style-card" + (!useStyle ? " on" : "")}
                    onClick={() => { haptic.select(); setUseStyle(false); }}>
              <div className="box"><Wand2 size={22} color="var(--primary)" /></div>
              <div className="cap">Yangi uslub</div>
            </button>
          </div>
        </div>
      )}

      {balls < 1 && (
        <div className="note warn">
          <div>
            <b>Ball yetarli emas.</b> «Hamyon» bo'limidan kreditni ballga
            almashtiring.
          </div>
        </div>
      )}

      <button className={"btn btn-primary" + (images.length && balls >= 1 ? " shine" : "")}
              disabled={busy || !images.length || balls < 1}
              onClick={() => launch(false)}
              style={{ opacity: (busy || !images.length || balls < 1) ? .5 : 1 }}>
        {busy ? "Yuborilmoqda…" : "✨ Yaratish · 1 ball"}
      </button>
    </div>
  );
}
