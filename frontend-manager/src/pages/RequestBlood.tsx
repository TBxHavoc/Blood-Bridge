import { useState, type FormEvent } from "react";

import { api, ApiError } from "../lib/api";
import {
  BLOOD_GROUPS,
  COMPONENT_TYPES,
  componentLabel,
  requestStatusClass,
  urgencyLabel,
  relativeTime,
} from "../lib/blood";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import { useNav } from "../app/NavContext";
import { CheckIcon } from "../components/Icons";
import type { BloodGroup, BloodRequest, ComponentType } from "../lib/types";

function MatchTable({ request }: { request: BloodRequest }) {
  if (!request.matches.length) {
    return (
      <div className="card tablecard">
        <div className="tablewrap">
          <table className="supplies-table">
            <tbody>
              <tr>
                <td className="empty">
                  No partner blood bank can currently cover this request. It stays open for
                  rematching.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  return (
    <div className="card tablecard">
      <div className="tablewrap">
        <table className="supplies-table">
          <thead>
            <tr>
              <th className="rankcol">Rank</th>
              <th>Blood bank</th>
              <th>Distance</th>
              <th>ETA</th>
              <th>Units</th>
              <th>Score</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {request.matches.map((match, i) => (
              <tr key={match.inventory_id}>
                <td>
                  <span className={`rank${i === 0 ? " top" : ""}`}>{match.ranking}</span>
                </td>
                <td className="bname">{match.blood_bank_name}</td>
                <td>{match.distance_km.toFixed(1)} km</td>
                <td>{match.eta_minutes} min</td>
                <td>
                  {match.units_available - match.units_reserved} units
                </td>
                <td>{Math.round(match.match_score)}</td>
                <td className="hint" style={{ maxWidth: 320 }}>
                  {match.explanation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RequestBlood({ token, user }: PageProps) {
  const { params } = useNav();
  const isHospital = user.role === "hospital_user";
  const isAdmin = user.role === "admin";
  const isAuditor = user.role === "auditor";
  const isBank = user.role === "bloodbank_user";
  const canListRequests = isHospital || isAdmin;

  const { data, error, reload } = useAsync(async () => {
    const requests = canListRequests ? await api.requests(token) : [];
    const queue = isAdmin || isAuditor ? await api.matchQueue(token) : [];
    const reservations = isBank ? await api.reservations(token) : [];
    return { requests, queue, reservations };
  }, [token, user.role]);

  const [bloodGroup, setBloodGroup] = useState<BloodGroup>("O-");
  const [component, setComponent] = useState<ComponentType>("RBC");
  const [units, setUnits] = useState(10);
  const [urgency, setUrgency] = useState(3);
  const [requiredBy, setRequiredBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [result, setResult] = useState<BloodRequest | null>(null);

  const requests = data?.requests ?? [];

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!units || units < 1) {
      setFormError("Enter at least 1 unit.");
      return;
    }
    setBusy(true);
    try {
      const created = await api.createRequest(token, {
        blood_group: bloodGroup,
        component_type: component,
        quantity_units: units,
        urgency,
        required_by_timestamp: requiredBy ? new Date(requiredBy).toISOString() : null,
      });
      setResult(created);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not submit the request.");
    } finally {
      setBusy(false);
    }
  }

  const bestMatch = result?.matches?.[0] ?? null;

  return (
    <section id="restock">
      <h1>Request blood</h1>
      <p className="lead">
        {isHospital
          ? "Submit a request — the matching engine ranks partner blood banks by distance, ETA and availability."
          : isBank
            ? "Requests are raised by hospitals. Here are the holds against your blood bank's stock."
            : "Open requests in priority order (urgency, then oldest first)."}
      </p>

      {error ? (
        <div className="notice error">
          <span>
            <strong>Could not load requests</strong>
            <small>{error}</small>
          </span>
        </div>
      ) : null}

      <div className="layout">
        <div className="left">
          {isHospital ? (
            <div className="card">
              <h2>New request</h2>
              <div className="body">
                {result ? (
                  <div className="notice">
                    <CheckIcon />
                    <div>
                      <strong>Request {result.code} submitted</strong>
                      <small>
                        {result.quantity_units} units of {result.blood_group} ·{" "}
                        {result.matches.length} match{result.matches.length === 1 ? "" : "es"} found.
                        Status {result.status}.
                      </small>
                    </div>
                  </div>
                ) : null}
                {params.bank && !result ? (
                  <p className="hint" style={{ marginTop: 0, marginBottom: 14 }}>
                    Preferred supplier noted: <strong>{params.bank}</strong>. Requests are ranked
                    automatically across all banks.
                  </p>
                ) : null}
                {formError ? (
                  <div className="notice error">
                    <span>
                      <strong>Could not submit</strong>
                      <small>{formError}</small>
                    </span>
                  </div>
                ) : null}
                <form className="form" onSubmit={onSubmit}>
                  <div className="field">
                    <label htmlFor="rType">Blood type</label>
                    <select id="rType" value={bloodGroup} onChange={(e) => setBloodGroup(e.target.value as BloodGroup)}>
                      {BLOOD_GROUPS.map((g) => (
                        <option key={g} value={g}>
                          {g}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="rComponent">Component</label>
                    <select id="rComponent" value={component} onChange={(e) => setComponent(e.target.value as ComponentType)}>
                      {COMPONENT_TYPES.map((c) => (
                        <option key={c} value={c}>
                          {componentLabel(c)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="rUnits">Units requested</label>
                    <input
                      id="rUnits"
                      type="number"
                      min={1}
                      max={100}
                      step={1}
                      value={units}
                      onChange={(e) => setUnits(Number(e.target.value))}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="rUrgency">Urgency</label>
                    <select id="rUrgency" value={urgency} onChange={(e) => setUrgency(Number(e.target.value))}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <option key={n} value={n}>
                          {urgencyLabel(n)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="rRequired">Required by (optional)</label>
                    <input
                      id="rRequired"
                      type="datetime-local"
                      value={requiredBy}
                      onChange={(e) => setRequiredBy(e.target.value)}
                    />
                  </div>
                  <div className="actions">
                    <button className="submit" type="submit" disabled={busy}>
                      {busy ? "Submitting…" : "Submit request"}
                    </button>
                    <span className="hint">Sent to the Blood Bridge matching engine.</span>
                  </div>
                </form>
              </div>
            </div>
          ) : (
            <div className="card">
              <h2>{isBank ? "Incoming holds" : "Priority match queue"}</h2>
              <div className="body">
                <ul className="list">
                  {(isBank ? data?.reservations ?? [] : data?.queue ?? []).map((row) => {
                    const isReservation = "inventory_id" in row;
                    if (isReservation) {
                      return (
                        <li key={row.id} className={`alert ${requestStatusClass("HELD")}`}>
                          <span className="dot" />
                          <div>
                            Hold of {row.quantity} units · {row.status}
                            <small>Expires {relativeTime(row.expires_at)}</small>
                          </div>
                        </li>
                      );
                    }
                    const req = row as BloodRequest;
                    return (
                      <li key={req.id} className={`alert ${requestStatusClass(req.status)}`}>
                        <span className="dot" />
                        <div>
                          {req.code} · {req.quantity_units} units of {req.blood_group}
                          <small>
                            {urgencyLabel(req.urgency)} · {req.status} ·{" "}
                            {relativeTime(req.request_timestamp)}
                          </small>
                        </div>
                      </li>
                    );
                  })}
                  {!(isBank ? data?.reservations?.length : data?.queue?.length) ? (
                    <li className="empty">Nothing in the queue right now.</li>
                  ) : null}
                </ul>
              </div>
            </div>
          )}

          {result ? <div style={{ marginTop: 20 }}>
            <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: "1.6rem", margin: "0 0 12px" }}>
              Ranked suppliers
            </h2>
            <MatchTable request={result} />
          </div> : null}
        </div>

        <div className="rail">
          <aside className="card">
            <h2>Selected blood bank</h2>
            <div className="body">
              <p className="rc-bank">{bestMatch?.blood_bank_name ?? params.bank ?? "—"}</p>
              <p className="rc-sub">
                {bestMatch ? `${bestMatch.distance_km.toFixed(1)} km away · ETA ${bestMatch.eta_minutes} min` : "Ranked automatically on submit"}
              </p>
              <div className="kv">
                <span>Units available</span>
                <b>{bestMatch ? bestMatch.units_available - bestMatch.units_reserved : "—"}</b>
              </div>
              <div className="kv">
                <span>Match score</span>
                <b>{bestMatch ? Math.round(bestMatch.match_score) : "—"}</b>
              </div>
              <div className="kv">
                <span>Batch expiry</span>
                <b>{bestMatch ? bestMatch.expiry_date : "—"}</b>
              </div>
            </div>
          </aside>

          {canListRequests ? (
            <aside className="card">
              <h2>
                Your requests <span className="count">{requests.length}</span>
              </h2>
              <div className="body">
                <ul className="list">
                  {requests.slice(0, 6).map((req) => (
                    <li key={req.id} className={`alert ${requestStatusClass(req.status)}`}>
                      <span className="dot" />
                      <div>
                        <strong>
                          {req.quantity_units} units of {req.blood_group}
                        </strong>
                        <small>
                          {req.code} · {req.status} · {relativeTime(req.request_timestamp)}
                        </small>
                      </div>
                    </li>
                  ))}
                  {!requests.length ? <li className="empty">No requests submitted yet.</li> : null}
                </ul>
              </div>
            </aside>
          ) : null}
        </div>
      </div>
    </section>
  );
}
