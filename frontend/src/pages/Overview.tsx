import { api } from "../lib/api";
import {
  availabilityOf,
  componentLabel,
  relativeTime,
  requestStatusClass,
  type StatusClass,
} from "../lib/blood";
import {
  buildStockFromErakthosh,
  buildStockFromInventory,
} from "../lib/derive";
import { datelineFor, greetingFor, orgLabel } from "../lib/session";
import { useAsync } from "../hooks/useAsync";
import { useClock } from "../hooks/useClock";
import type { PageProps } from "../app/PageProps";
import type { Alert, BloodRequest, EraktkoshSummary, InventoryItem, Reservation } from "../lib/types";
import { AlertList, type AlertItem } from "../components/AlertList";
import { BloodBox } from "../components/BloodBox";
import { Legend } from "../components/Legend";
import { useNav } from "../app/NavContext";

type OverviewData =
  | { kind: "bank"; items: InventoryItem[]; reservations: Reservation[] }
  | { kind: "hospital"; requests: BloodRequest[] }
  | {
      kind: "network";
      summary: EraktkoshSummary;
      apiAlerts: Alert[];
      requests: BloodRequest[];
      reservations: Reservation[];
    };

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
  const isBank = user.role === "bloodbank_user";
  const isHospital = user.role === "hospital_user";

  const { data, error, loading } = useAsync(async (): Promise<OverviewData> => {
    if (isBank) {
      const [items, reservations] = await Promise.all([
        api.inventory(token),
        api.reservations(token),
      ]);
      return { kind: "bank", items, reservations };
    }
    if (isHospital) {
      const requests = await api.requests(token);
      return { kind: "hospital", requests };
    }
    const [summary, apiAlerts, requests, reservations] = await Promise.all([
      api.eraktkoshSummary(),
      api.alerts(token, { limit: 50 }),
      api.requests(token),
      api.reservations(token),
    ]);
    return { kind: "network", summary, apiAlerts, requests, reservations };
  }, [token, user.role]);

  const stock =
    data?.kind === "bank"
      ? buildStockFromInventory(data.items)
      : data?.kind === "network"
        ? buildStockFromErakthosh(data.summary)
        : [];

  const apiAlerts: Alert[] = data?.kind === "network" ? data.apiAlerts : [];
  const requests: BloodRequest[] =
    data?.kind === "hospital" ? data.requests : data?.kind === "network" ? data.requests : [];
  const reservations: Reservation[] =
    data?.kind === "bank" ? data.reservations : data?.kind === "network" ? data.reservations : [];

  const scopeLabel =
    isBank
      ? "Your blood bank · live inventory"
      : isHospital
        ? "Your hospital · your requests"
        : "Live eRaktKosh stock";

  const alerts: AlertItem[] = [];
  for (const item of stock) {
    const [cls] = availabilityOf(item.units, true);
    if (cls === "low") {
      alerts.push({
        cls: "crit",
        title: `${item.type} is critically low`,
        note: `${item.units} units left.`,
      });
    } else if (cls === "warn") {
      alerts.push({
        cls: "warn",
        title: `${item.type} running low`,
        note: `${item.units} units left.`,
      });
    }
  }
  for (const alert of apiAlerts) {
    alerts.push({
      cls: ALERT_LEVEL[alert.alert_type] ?? "warn",
      title: alertTitle(alert.alert_type),
      note: alert.message,
    });
  }
  const pending = requests.filter(
    (r) => r.status === "OPEN" || r.status === "HELD",
  ).length;
  if (pending > 0) {
    alerts.push({
      cls: "warn",
      title: `${pending} request${pending === 1 ? "" : "s"} awaiting approval`,
      note: "Review and respond today",
    });
  }

  const activity = requests.slice(0, 5).map((r) => ({
    cls: requestStatusClass(r.status),
    title: `${r.quantity_units} units of ${r.blood_group} · ${r.status.toLowerCase()}`,
    note: `${componentLabel(r.component_type)} · ${relativeTime(r.request_timestamp)}`,
  }));
  const reservationActivity = reservations.slice(0, 5).map((res) => ({
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
          <Legend source={scopeLabel} />

          {loading ? <p className="loading">Loading…</p> : null}
          {error ? (
            <p className="notice error">
              <span>
                <strong>Could not load the overview</strong>
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
