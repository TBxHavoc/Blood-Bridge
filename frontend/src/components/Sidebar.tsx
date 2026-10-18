import { useEffect, useRef, useState } from "react";
import { useNav, HELP_ITEM, getWorkspaceItems, type ViewName } from "../app/NavContext";

import { relativeTime } from "../lib/blood";
import { roleLabel } from "../lib/session";
import type { User } from "../lib/types";
import { Bloodstream } from "./Bloodstream";
import {
  CubeIcon,
  DocIcon,
  DropIcon,
  GridIcon,
  HelpIcon,
  InboxIcon,
  LogoutIcon,
  PulseIcon,
  SearchIcon,
  UserIcon,
} from "./Icons";

const ICONS: Record<ViewName, (props: { className?: string }) => JSX.Element> = {
  Overview: GridIcon,
  Inventory: CubeIcon,
  "Find supplies": SearchIcon,
  "Request inbox": InboxIcon,
  "Live eRaktKosh": PulseIcon,
  "Request blood": DropIcon,
  Reports: DocIcon,
  FAQ: HelpIcon,
};


interface SidebarProps {
  orgName: string;
  user: User;
  onSignOut: () => void;
}

function ProfileDialog({
  user,
  orgName,
  onClose,
  onSignOut,
}: {
  user: User;
  orgName: string;
  onClose: () => void;
  onSignOut: () => void;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="dialog-scrim" role="presentation" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialog-head">
          <h2 id="profile-title">Profile</h2>
          <button className="dialog-close" type="button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="dialog-body">
          <dl className="facts">
            <div>
              <dt>Username</dt>
              <dd>{user.username}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{roleLabel(user.role)}</dd>
            </div>
            <div>
              <dt>Organisation</dt>
              <dd>{orgName}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{user.is_active ? "Active" : "Inactive"}</dd>
            </div>
            <div>
              <dt>Last sign-in</dt>
              <dd>{user.last_login ? relativeTime(user.last_login) : "—"}</dd>
            </div>
          </dl>
        </div>
        <div className="dialog-foot">
          <button className="ghost" type="button" onClick={onClose}>
            Close
          </button>
          <button className="submit" type="button" onClick={onSignOut}>
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}

export function Sidebar({ orgName, user, onSignOut }: SidebarProps) {
  const { view, go } = useNav();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  return (
    <aside className="side">
      <Bloodstream />
      <div className="top">
        <span className="hospital" title={orgName}>
          {orgName}
        </span>
        <div className="profile-menu" ref={menuRef}>
          <button
            className="profile"
            type="button"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label={`Account menu for ${user.username}`}
            title={user.username}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <UserIcon />
          </button>

          {menuOpen ? (
            <div className="profile-pop" role="menu">
              <div className="profile-who">
                <strong>{user.username}</strong>
                <span>{roleLabel(user.role)}</span>
              </div>
              <button
                className="menu-item"
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  setProfileOpen(true);
                }}
              >
                <UserIcon />
                Profile
              </button>
              <button
                className="menu-item danger"
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onSignOut();
                }}
              >
                <LogoutIcon />
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="group" id="workspace">
        Workspace
      </div>
      <nav aria-labelledby="workspace">
        {getWorkspaceItems(user.role).map(({ view: itemView, label }) => {
          const Icon = ICONS[itemView];
          return (
            <button
              key={itemView}
              className="item"
              type="button"
              aria-current={view === itemView ? "page" : undefined}
              onClick={() => go(itemView)}
            >
              <Icon />
              {label}
              {itemView === "Request inbox" ? (
                <span className="badge-count" style={{
                  marginLeft: "auto",
                  background: "var(--crit)",
                  color: "#fff",
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "2px 7px",
                  borderRadius: "999px"
                }}>2</span>
              ) : null}
            </button>
          );
        })}
      </nav>


      <div className="faq">
        <button
          className="item"
          type="button"
          aria-current={view === HELP_ITEM.view ? "page" : undefined}
          onClick={() => go(HELP_ITEM.view)}
        >
          <HelpIcon />
          {HELP_ITEM.label}
        </button>
      </div>

      {profileOpen ? (
        <ProfileDialog
          user={user}
          orgName={orgName}
          onClose={() => setProfileOpen(false)}
          onSignOut={onSignOut}
        />
      ) : null}
    </aside>
  );
}
