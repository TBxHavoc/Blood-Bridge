import { api } from "../lib/api";
import { duration, status, type StatusClass } from "../lib/blood";
import { buildStock } from "../lib/derive";
import { datelineFor, greetingFor, orgLabel } from "../lib/session";
import { componentLabel, relativeTime, requestStatusClass } from "../lib/blood";
import { useAsync } from "../hooks/useAsync";
import { useClock } from "../hooks/useClock";
import type { PageProps } from "../app/PageProps";
import { AlertList, type AlertItem } from "../components/AlertList";
import { BloodBox } from "../components/BloodBox";
import { Legend } from "../components/Legend";
import { useNav } from "../app/NavContext";

const ALERT_LEVEL: Record<string, StatusClass> = {
  SHORTAGE_DETECTED: "crit",
  MATCH_EXPIRED: "warn",
  MATCH_FOUND: "good",
  ALLOCATED: "good",
};

function reservationClass(status: string): StatusClass {
  if (status === "CONFIRMED") return "good";
  if (status === "ACTIVE") return "warn";
  if (status === "RELEASED") return "warn";
  return "crit";
}

function alertTitle(type: string): string {
  return type
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function Overview({ token, user }: PageProps) {
  const now = useClock();
  const { go } = useNav();
  const canSeeRequests = user.role === "hospital_user" || user.role === "admin";
  const bankId = user.role === "bloodbank_user" ? user.affiliated_org_id ?? undefined : undefined;

  const { data, error, loading } = useAsync(async () => {
    const [depletion, usage, alerts] = await Promise.all([
      api.depletion(token),
      api.usage(token),
      api.alerts(token, { limit: 50 }),
    ]);
    const requests = canSeeRequests ? await api.requests(token) : [];
    const reservations = user.role === "bloodbank_user" ? await api.reservations(token) : [];
    return { depletion, usage, alerts, requests, reservations };
  }, [token, canSeeRequests, user.role]);

  const stock = data ? buildStock(data.depletion, data.usage, { bankId }) : [];
  const scopeLabel = bankId ? "Your blood bank" : "Network-wide";

  const alerts: AlertItem[] = [];
  for (const item of stock) {
    if (item.hours < 72) {
      const [cls] = status(item.hours);
      alerts.push({
        cls,
        title: `${item.type} is ${cls === "crit" ? "critically low" : "running low"}`,
        note: `${item.units} units left, about ${duration(item.hours)} remaining`,
      });
    }
  }
  for (const item of stock) {
    if (item.expiring) {
      alerts.push({
        cls: item.expiring.days <= 2 ? "low" : "warn",
        title: `${item.expiring.units} units of ${item.type} expiring soon`,
        note: `Expire in ${item.expiring.days} day(s). Use or transfer them.`,
      });
    }
  }
  for (const alert of data?.alerts ?? []) {
    alerts.push({
      cls: ALERT_LEVEL[alert.alert_type] ?? "warn",
      title: alertTitle(alert.alert_type),
      note: alert.message,
    });
  }
  const pending = (data?.requests ?? []).filter(
    (r) => r.status === "OPEN" || r.status === "HELD",
  ).length;
  if (pending > 0) {
    alerts.push({
      cls: "warn",
      title: `${pending} request${pending === 1 ? "" : "s"} awaiting approval`,
      note: "Review and respond today",
    });
  }

  const activity = (data?.requests ?? []).slice(0, 5).map((r) => ({
    cls: requestStatusClass(r.status),
    title: `${r.quantity_units} units of ${r.blood_group} · ${r.status.toLowerCase()}`,
    note: `${componentLabel(r.component_type)} · ${relativeTime(r.request_timestamp)}`,
  }));
  const reservationActivity = (data?.reservations ?? []).slice(0, 5).map((res) => ({
    cls: reservationClass(res.status),
    title: `Hold of ${res.quantity} units · ${res.status.toLowerCase()}`,
    note: `Expires in ${relativeTime(res.expires_at)}`,
  }));
  const feed = activity.length ? activity : reservationActivity;

  const updated = data ? new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "";

  return (
    <section id="home">
      <p className="dateline">{datelineFor(now, orgLabel(user))}</p>
      <h2 className="greeting">{greetingFor(now)}</h2>

      <div className="layout">
        <div className="left">
          <Legend source={data ? `${scopeLabel} · live forecast` : undefined} />

          {loading ? <p className="loading">Loading live forecast…</p> : null}
          {error ? (
            <p className="notice error">
              <span>
                <strong>Could not load the forecast</strong>
                <small>{error}</small>
              </span>
            </p>
          ) : null}

          <div className="types">
            {stock.map((item) => (
              <BloodBox key={item.type} item={item} />
            ))}
          </div>

          <div className="card">
            <h2>Recent activity</h2>
            <div className="body">
              {feed.length ? (
                <ul className="list">
                  {feed.map((entry, i) => (
                    <li key={i} className={`alert ${entry.cls}`}>
                      <span className="dot" />
                      <div>
                        {entry.title}
                        <small>{entry.note}</small>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <ul className="list">
                  <li className="empty">
                    No recent activity.{" "}
                    <button className="link" type="button" onClick={() => go("Request blood")}>
                      Request blood
                    </button>{" "}
                    to get started.
                  </li>
                </ul>
              )}
            </div>
          </div>
        </div>

        <div className="rail">
          <aside className="card alerts">
            <h2>
              Alerts <span className="count">{alerts.length}</span>
            </h2>
            <div className="body">
              <AlertList items={alerts} />
            </div>
          </aside>
        </div>
      </div>

      {updated ? <p className="hint" style={{ paddingTop: 12 }}>Updated {updated}.</p> : null}
    </section>
  );
}
