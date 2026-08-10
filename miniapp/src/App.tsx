import { useEffect, useState } from "react";
import BottomNav, { type Screen } from "./components/BottomNav";
import Dashboard from "./screens/Dashboard";
import Users from "./screens/Users";
import UserDetail from "./screens/UserDetail";
import Payments from "./screens/Payments";
import Report from "./screens/Report";
import Tasks from "./screens/Tasks";
import Settings from "./screens/Settings";
import { initTelegram } from "./lib/telegram";

type View = Screen | "user-detail" | "tasks";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [userId, setUserId] = useState<number>(0);
  const [tasksTab, setTasksTab] = useState<string>("active");

  useEffect(() => { initTelegram(); }, []);

  // Dashboard va boshqa ekranlardan navigatsiya
  const go = (v: string, opt?: any) => {
    if (v === "tasks") setTasksTab(opt || "active");
    setView(v as View);
  };

  const activeNav: Screen =
    view === "user-detail" ? "users" :
    view === "tasks" ? "dashboard" :
    (view as Screen);

  return (
    <div className="app-root">
      {view === "dashboard" && <Dashboard go={go} />}
      {view === "users" && <Users open={(id) => { setUserId(id); setView("user-detail"); }} />}
      {view === "user-detail" && <UserDetail id={userId} back={() => setView("users")} />}
      {view === "payments" && <Payments />}
      {view === "report" && <Report />}
      {view === "tasks" && <Tasks initial={tasksTab} />}
      {view === "settings" && <Settings />}
      <BottomNav active={activeNav} onChange={(s) => setView(s)} />
    </div>
  );
}
