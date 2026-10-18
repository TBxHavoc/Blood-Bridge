import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { orgLabel } from "../lib/session";
import { Deco } from "../components/Deco";
import { Sidebar } from "../components/Sidebar";
import {
  NavContext,
  type NavParams,
  type NavValue,
  type ViewName,
} from "../app/NavContext";
import type { PageProps } from "../app/PageProps";
import { Overview } from "./Overview";
import { Inventory } from "./Inventory";
import { RequestInbox } from "./RequestInbox";
import { RequestBlood } from "./RequestBlood";
import { Reports } from "./Reports";
import { Faq } from "./Faq";
import { LiveERaktKosh } from "./LiveERaktKosh";

export function Dashboard({ token, user }: PageProps) {
  const { logout } = useAuth();
  const [view, setView] = useState<ViewName>("Overview");
  const [params, setParams] = useState<NavParams>({});

  const go = useCallback((next: ViewName, nextParams: NavParams = {}) => {
    setView(next);
    setParams(nextParams);
    document.title = `HemoTrack | ${next}`;
    const main = document.querySelector("main");
    if (main) main.scrollTop = 0;
  }, []);

  useEffect(() => {
    document.title = "HemoTrack | Overview";
  }, []);

  const nav = useMemo<NavValue>(() => ({ view, params, go }), [view, params, go]);

  return (
    <NavContext.Provider value={nav}>
      <div className="app">
        <Sidebar orgName={orgLabel(user)} user={user} onSignOut={() => void logout()} />
        <main>
          <div className="topline" aria-hidden="true" />
          <Deco />
          {view === "Overview" ? <Overview token={token} user={user} /> : null}
          {view === "Inventory" ? <Inventory token={token} user={user} /> : null}
          {view === "Request inbox" ? <RequestInbox token={token} user={user} /> : null}
          {view === "Live eRaktKosh" ? <LiveERaktKosh /> : null}
          {view === "Request blood" ? <RequestBlood token={token} user={user} /> : null}
          {view === "Reports" ? <Reports token={token} user={user} /> : null}
          {view === "FAQ" ? <Faq /> : null}
        </main>
      </div>
    </NavContext.Provider>
  );
}
