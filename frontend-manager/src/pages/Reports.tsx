import { api } from "../lib/api";
import { componentLabel } from "../lib/blood";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";

export function Reports({ token }: PageProps) {
  const { data, error, loading } = useAsync(async () => api.summary(token), [token]);

  const usage = data?.usage_statistics ?? [];

  return (
    <section id="reports">
      <h1>Reports</h1>
      <p className="lead">Consumption velocity and stockout exposure derived from request history.</p>

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
          <b className="val">{data?.total_inventory_items_monitored ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">Critical stockouts</span>
          <b className="val crit">{data?.critical_stockouts_count ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">High-risk stockouts</span>
          <b className="val warn">{data?.high_risk_stockouts_count ?? "—"}</b>
        </div>
        <div className="cell">
          <span className="lbl">Forecast source</span>
          <b className="val">
            {data ? (data.ml_model_loaded ? "ML model" : "Heuristic") : "—"}
            <small> {data?.ml_model_loaded ? "LightGBM/RF" : "simulation"}</small>
          </b>
        </div>
      </div>

      <div className="card tablecard">
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
                  <td className="tcol">{row.blood_group}</td>
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
      {loading ? <p className="loading">Loading report…</p> : null}
    </section>
  );
}
