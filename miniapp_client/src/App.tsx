import { useCallback, useEffect, useRef, useState } from "react";
import { WifiOff, RefreshCw } from "lucide-react";
import BottomNav, { type Screen } from "./components/BottomNav";
import { ToastProvider } from "./components/Toast";
import Home from "./screens/Home";
import Create from "./screens/Create";
import Gallery from "./screens/Gallery";
import WalletScreen from "./screens/Wallet";
import { initTelegram, haptic, setBackButton } from "./lib/telegram";
import { api, ApiError, type Me } from "./lib/api";

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}

function Shell() {
  const [view, setView] = useState<Screen>("home");
  const [me, setMe] = useState<Me | null>(null);
  const [fatal, setFatal] = useState<{ auth: boolean; text: string } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const topRef = useRef<HTMLDivElement>(null);

  // Hamyon bir joyda saqlanadi: generatsiya/almashtirishdan keyin yangilanadi,
  // shunda barcha ekranlar bir xil balansni ko'radi.
  const refresh = useCallback(async () => {
    try {
      setMe(await api.me());
      setFatal(null);
    } catch (e: any) {
      // 401 — kirish muammosi (boshqacha yechim kerak);
      // qolgani — tarmoq/server (qayta urinish yordam beradi)
      const auth = e instanceof ApiError && e.status === 401;
      setFatal({ auth, text: e?.message || "Ulanib bo'lmadi" });
    }
  }, []);

  useEffect(() => {
    initTelegram();
    refresh();
  }, [refresh]);

  // Ekran almashganda tepaga qaytamiz — aks holda yangi ekran
  // o'rtasidan ochilgandek tuyuladi
  useEffect(() => {
    topRef.current?.scrollIntoView({ block: "start" });
    window.scrollTo({ top: 0 });
  }, [view]);

  // Telegram «Orqaga» tugmasi: bosh sahifadan boshqa joyda ko'rinadi
  useEffect(() => {
    if (view === "home") return setBackButton(null);
    return setBackButton(() => {
      haptic.tap();
      setView("home");
    });
  }, [view]);

  const go = (s: Screen) => {
    haptic.tap();
    setView(s);
  };

  if (fatal) {
    return (
      <div className="app-root">
        <div className="screen">
          <div className="empty-box anim">
            <div className="empty-ic">
              <WifiOff size={30} color="var(--primary)" />
            </div>
            <div className="empty-t">
              {fatal.auth ? "Kirish amalga oshmadi" : "Ulanib bo'lmadi"}
            </div>
            <div className="empty-s">{fatal.text}</div>
            <div className="empty-s">
              {fatal.auth
                ? "Ilovani Telegram bot orqali oching. Muammo qolsa — botda /start bosing."
                : "Internetni tekshirib, qayta urinib ko'ring."}
            </div>
            {!fatal.auth && (
              <button className="btn btn-primary" style={{ maxWidth: 220 }}
                      disabled={retrying}
                      onClick={async () => {
                        setRetrying(true);
                        haptic.tap();
                        await refresh();
                        setRetrying(false);
                      }}>
                <span style={{ display: "flex", alignItems: "center",
                               justifyContent: "center", gap: 8 }}>
                  <RefreshCw size={17} className={retrying ? "spin" : ""} />
                  {retrying ? "Urinilmoqda…" : "Qayta urinish"}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-root">
      <div ref={topRef} />
      {view === "home" && <Home me={me} go={go} />}
      {view === "create" && (
        <Create me={me} refresh={refresh} goGallery={() => go("gallery")} />
      )}
      {view === "gallery" && <Gallery />}
      {view === "wallet" && <WalletScreen me={me} refresh={refresh} />}
      <BottomNav active={view} onChange={go} />
    </div>
  );
}
