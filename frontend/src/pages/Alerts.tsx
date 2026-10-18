import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { relativeTime } from "../lib/blood";
import type { PageProps } from "../app/PageProps";
import type { Alert } from "../lib/types";
import { CheckIcon } from "../components/Icons";
import { useNav } from "../app/NavContext";

function alertTypeBadge(type: string): { label: string; className: string } {
  switch (type) {
    case "ALLOCATED":
      return { label: "REQUEST APPROVED & ALLOCATED", className: "badge-allocated" };
    case "MATCH_FOUND":
      return { label: "MATCH FOUND", className: "badge-match" };
    case "SHORTAGE_DETECTED":
      return { label: "SHORTAGE DETECTED", className: "badge-shortage" };
    case "MATCH_EXPIRED":
      return { label: "HOLD EXPIRED", className: "badge-expired" };
    default:
      return { label: type.replace(/_/g, " "), className: "badge-default" };
  }
}

export function Alerts({ token }: PageProps) {
  const { go } = useNav();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"ALL" | "UNREAD" | "ALLOCATED">("ALL");
  const [actioningId, setActioningId] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await api.alerts(token, { limit: 100 });
      setAlerts(data);
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchAlerts();
    // Poll every 5 seconds for real-time notification of approvals
    const interval = setInterval(() => {
      void fetchAlerts();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const markAsRead = async (id: string) => {
    if (actioningId) return;
    setActioningId(id);
    try {
      await api.readAlert(token, id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, is_read: true, read_at: new Date().toISOString() } : a))
      );
    } catch (err) {
      console.error("Failed to mark alert as read:", err);
    } finally {
      setActioningId(null);
    }
  };

  const markAllAsRead = async () => {
    const unread = alerts.filter((a) => !a.is_read);
    for (const a of unread) {
      try {
        await api.readAlert(token, a.id);
      } catch {
        // continue
      }
    }
    setAlerts((prev) =>
      prev.map((a) => ({ ...a, is_read: true, read_at: new Date().toISOString() }))
    );
  };

  const unreadCount = alerts.filter((a) => !a.is_read).length;
  const allocatedCount = alerts.filter((a) => a.alert_type === "ALLOCATED").length;

  const filtered = useMemo(() => {
    if (filter === "UNREAD") return alerts.filter((a) => !a.is_read);
    if (filter === "ALLOCATED") return alerts.filter((a) => a.alert_type === "ALLOCATED");
    return alerts;
  }, [alerts, filter]);

  return (
    <section id="alerts-page">
      <div className="alerts-page-header">
        <div>
          <h1>Alerts & Notifications</h1>
          <p className="lead">
            Real-time status updates on blood requests, bank approvals, allocations, and stock warnings.
          </p>
        </div>
        <div className="alerts-header-actions">
          <span className="live-pulse-badge">
            <span className="live-dot" /> Live sync active
          </span>
          {unreadCount > 0 && (
            <button
              type="button"
              className="btn-mark-all"
              onClick={markAllAsRead}
            >
              Mark all as read
            </button>
          )}
        </div>
      </div>

      {/* Summary strip / Filter bar */}
      <div className="card strip" style={{ marginBottom: "1.25rem" }}>
        <div
          className={`cell ${filter === "ALL" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("ALL")}
        >
          <span className="lbl">All notifications</span>
          <b className="val">
            {alerts.length}
            <small> total</small>
          </b>
        </div>
        <div
          className={`cell ${filter === "ALLOCATED" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("ALLOCATED")}
        >
          <span className="lbl">Approved & Allocated</span>
          <b className="val good">
            {allocatedCount}
            <small> approved</small>
          </b>
        </div>
        <div
          className={`cell ${filter === "UNREAD" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("UNREAD")}
        >
          <span className="lbl">Unread</span>
          <b className={`val ${unreadCount > 0 ? "warn" : ""}`}>
            {unreadCount}
            <small> new</small>
          </b>
        </div>
      </div>

      {/* Alerts list */}
      <div className="card alerts-container">
        {loading && alerts.length === 0 ? (
          <p className="loading">Loading alerts and notifications…</p>
        ) : filtered.length === 0 ? (
          <div className="alerts-empty-state">
            <div className="empty-icon">🔔</div>
            <h3>No alerts found</h3>
            <p className="hint">
              {filter === "UNREAD"
                ? "You're all caught up! There are no unread notifications."
                : filter === "ALLOCATED"
                ? "No approved requests yet. When a blood bank accepts your request, it will appear here."
                : "No alerts at this moment. You will be notified in real time when requests are reviewed."}
            </p>
          </div>
        ) : (
          <div className="alerts-card-list">
            {filtered.map((item) => {
              const badge = alertTypeBadge(item.alert_type);
              const isAllocated = item.alert_type === "ALLOCATED";

              return (
                <div
                  key={item.id}
                  className={`alert-card ${isAllocated ? "alert-card-allocated" : ""} ${
                    !item.is_read ? "alert-unread" : "alert-read"
                  }`}
                >
                  <div className="alert-card-accent" />
                  <div className="alert-card-body">
                    <div className="alert-card-top">
                      <div className="alert-badge-group">
                        <span className={`alert-badge ${badge.className}`}>
                          {isAllocated && <CheckIcon />}
                          {badge.label}
                        </span>
                        {!item.is_read && <span className="new-chip">NEW</span>}
                      </div>
                      <time className="alert-time" dateTime={item.created_at}>
                        {relativeTime(item.created_at)}
                      </time>
                    </div>

                    <div className="alert-card-content">
                      <p className="alert-message">{item.message}</p>
                    </div>

                    <div className="alert-card-footer">
                      <span className="alert-timestamp">
                        {new Date(item.created_at).toLocaleString("en-IN", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </span>
                      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                        {isAllocated && (
                          <button
                            type="button"
                            className="btn-track-delivery"
                            onClick={() => go("Delivery tracking")}
                          >
                            🚑 Track Delivery →
                          </button>
                        )}
                        {!item.is_read && (
                          <button
                            type="button"
                            className="btn-read-toggle"
                            disabled={actioningId === item.id}
                            onClick={() => markAsRead(item.id)}
                          >
                            Mark as read
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
