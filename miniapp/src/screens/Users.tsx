import { useEffect, useState } from "react";
import { Search, ChevronRight } from "lucide-react";
import { api, type UsersResp } from "../lib/api";
import { fmt, initials, uname } from "../lib/util";

export default function Users({ open }: { open: (id: number) => void }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<UsersResp | null>(null);

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api.users(page, q).then((r) => live && setData(r));
    }, q ? 300 : 0);
    return () => { live = false; clearTimeout(t); };
  }, [page, q]);

  return (
    <div className="screen">
      <div>
        <div className="page-title">👥 Foydalanuvchilar</div>
        <div className="page-sub">{data ? `${fmt(data.total)} ta` : "..."}</div>
      </div>

      <div className="search">
        <Search size={18} style={{ opacity: 0.4 }} />
        <input
          placeholder="Ism, @username yoki ID..."
          value={q}
          onChange={(e) => { setPage(0); setQ(e.target.value); }}
        />
      </div>

      <div className="list">
        {data?.users.map((u) => (
          <button key={u.id} className="row" onClick={() => open(u.id)}>
            <div className="avatar">{initials(u.name)}</div>
            <div className="row-main">
              <div className="row-title">
                {u.active ? "" : "🔴 "}{u.name}
              </div>
              <div className="row-sub">{uname(u.username)} · {u.created}</div>
            </div>
            <div className="row-trail">
              <span className="schip lav">💰 {u.credits}</span>
            </div>
            <ChevronRight size={18} style={{ opacity: 0.3 }} />
          </button>
        ))}
        {data && data.users.length === 0 && <div className="empty">Topilmadi</div>}
      </div>

      {data && data.pages > 1 && (
        <div className="pager">
          <button disabled={page <= 0} onClick={() => setPage((p) => p - 1)}>◀️</button>
          <span>{page + 1} / {data.pages}</span>
          <button disabled={page >= data.pages - 1} onClick={() => setPage((p) => p + 1)}>▶️</button>
        </div>
      )}
    </div>
  );
}
