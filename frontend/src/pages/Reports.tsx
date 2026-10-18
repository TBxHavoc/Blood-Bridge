import { api } from "../lib/api";
import { componentLabel, duration } from "../lib/blood";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import type { Depletion } from "../lib/types";

function riskBadgeClass(risk: string): string {
  switch (risk) {
    case "CRITICAL":
      return "status-chip status-cancelled";
    case "HIGH":
      return "status-chip status-open";
    case "MEDIUM":
      return "status-chip status-held";
    default:
      return "status-chip status-confirmed";
  }
}

export function Reports({ token }: PageProps) {
  const { data, error, loading } = useAsync(async () => {
    const [summary, depletion] = await Promise.all([
      api.summary(token),
      api.depletion(token).catch(() => [] as Depletion[]),
    ]);
    return { summary, depletion };
  }, [token]);

  const summary = data?.summary;
  const usage = summary?.usage_statistics ?? [];
  const depletion = data?.depletion ?? [];

  return (
    <section id="reports">
      <h1>Reports — ML Forecasts & Analytics</h1>
      <p className="lead">
        Predictive supply depletion, runout timelines, and consumption velocity derived from machine-learning models and clinical history.
      </p>

      {error ? (
        <div className="notice error">
          <span>
            <strong>Could not load reports</strong>
            <small>{error}</small>
          </span>
        </div>
      ) : null}

      <div className="card strip">
        <div className="cell">
          <span className="lbl">Inventory items monitored</span>
          <b className="val">{summary?.total_inventory_items_monitored ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">Critical stockouts</span>
          <b className="val crit">{summary?.critical_stockouts_count ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">High-risk stockouts</span>
          <b className="val warn">{summary?.high_risk_stockouts_count ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">Forecast engine</span>
          <b className="val">
            {summary ? (summary.ml_model_loaded ? "ML model" : "Heuristic") : "—"}
            <small> {summary?.ml_model_loaded ? "LightGBM/RF" : "simulation"}</small>
          </b>
        </div>
      </div>

      {/* ML Depletion Forecast Table */}
      <div className="card tablecard" style={{ marginBottom: 24 }}>
        <div className="body" style={{ padding: "16px 20px 8px" }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem" }}>ML Supply Depletion & Stockout Risks</h2>
          <p className="hint" style={{ margin: "4px 0 0" }}>
            Forecasts when partner blood supplies will deplete based on current burn rate and batch expiration.
          </p>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Blood type</th>
                <th>Component</th>
                <th>Blood bank</th>
                <th>Available units</th>
                <th>Runout in</th>
                <th>Stockout risk</th>
                <th>Primary trigger</th>
              </tr>
            </thead>
            <tbody>
              {depletion.map((row, i) => (
                <tr key={`${row.blood_bank_code}-${row.blood_group}-${row.component_type}-${i}`}>
                  <td className="tcol">
                    <strong>{row.blood_group}</strong>
                  </td>
                  <td>{componentLabel(row.component_type)}</td>
                  <td>{row.blood_bank_name || row.blood_bank_code}</td>
                  <td>{row.units_unreserved ?? row.units_available} units</td>
                  <td>
                    <span className={row.hours_until_depletion < 48 ? "crit" : "good"} style={{ fontWeight: 600 }}>
                      {duration(row.hours_until_depletion)}
                    </span>
                  </td>
                  <td>
                    <span className={riskBadgeClass(row.stockout_risk)}>
                      {row.stockout_risk}
                    </span>
                  </td>
                  <td className="hint" style={{ maxWidth: 220 }}>
                    {row.depletion_cause.replace(/_/g, " ")}
                  </td>
                </tr>
              ))}
              {!depletion.length && !loading ? (
                <tr>
                  <td className="empty" colSpan={7}>
                    No depletion forecasts available at this moment.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {/* Consumption Velocity Table */}
      <div className="card tablecard">
        <div className="body" style={{ padding: "16px 20px 8px" }}>
          <h2 style={{ margin: 0, fontSize: "1.1rem" }}>Consumption Velocity & Usage Statistics</h2>
          <p className="hint" style={{ margin: "4px 0 0" }}>
            Daily burn rates, weekly demand volume, and peak surge observations.
          </p>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Blood group</th>
                <th>Component</th>
                <th>Requests</th>
                <th>Units consumed</th>
                <th>Avg / day</th>
                <th>Weekly</th>
                <th>Peak 24h</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {usage.map((row) => (
                <tr key={`${row.blood_group}-${row.component_type}`}>
                  <td className="tcol">
                    <strong>{row.blood_group}</strong>
                  </td>
                  <td>{componentLabel(row.component_type)}</td>
                  <td>{row.total_requests}</td>
                  <td>{row.total_units_consumed}</td>
                  <td>{Math.round(row.avg_usage_per_day * 10) / 10}</td>
                  <td>{Math.round(row.weekly_usage * 10) / 10}</td>
                  <td>{row.peak_24h_demand}</td>
                  <td>{row.recent_trend}</td>
                </tr>
              ))}
              {!usage.length && !loading ? (
                <tr>
                  <td className="empty" colSpan={8}>
                    No usage statistics yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      {loading ? <p className="loading">Loading ML reports…</p> : null}
    </section>
  );
}
