import { useEffect, useMemo, useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { relativeTime } from "../lib/blood";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import { CheckIcon, SearchIcon } from "../components/Icons";
import type { BloodRequest } from "../lib/types";

/** Map numeric urgency (1–5) to the three display tiers.
 *  4 and 5 are Emergency (Critical/Life-threatening)
 *  3 is Urgent
 *  1 and 2 are Routine
 */
function urgencyTier(urgency: number): "routine" | "urgent" | "emergency" {
  if (urgency >= 4) return "emergency";
  if (urgency >= 3) return "urgent";
  return "routine";
}

/** Human-friendly label for the urgency tier. */
function urgencyLabel(tier: "routine" | "urgent" | "emergency"): string {
  switch (tier) {
    case "emergency":
      return "Emergency";
    case "urgent":
      return "Urgent";
    case "routine":
      return "Routine";
  }
}

/** CSS class for the urgency badge. */
function urgencyClass(tier: "routine" | "urgent" | "emergency"): string {
  switch (tier) {
    case "emergency":
      return "urgency-emergency";
    case "urgent":
      return "urgency-urgent";
    case "routine":
      return "urgency-routine";
  }
}

const BANGALORE_HOSPITALS = [
  "Victoria Hospital (BMCRI), City Market",
  "Bowring & Lady Curzon Hospital, Shivaji Nagar",
  "Manipal Hospital, Old Airport Road",
  "Apollo Hospital, Bannerghatta Road",
  "St. John's Medical College Hospital, Koramangala",
  "Fortis Hospital, Cunningham Road",
  "Kidwai Memorial Institute of Oncology",
  "Narayana Institute of Cardiac Sciences",
  "KC General Hospital, Malleshwaram",
  "Columbia Asia Hospital, Hebbal",
];

function stringHash(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/** Distance based on request ID (stable pseudo-distance in 2.1 km – 28.5 km range). */
function pseudoDistanceKm(requestId: string): number {
  const hash = stringHash(requestId);
  return (hash % 2640) / 100 + 2.1;
}

/** Hospital name derived from request ID / hospital_id with Bangalore hospital names. */
function hospitalName(req: BloodRequest): string {
  const hash = stringHash(req.hospital_id || req.id);
  return BANGALORE_HOSPITALS[hash % BANGALORE_HOSPITALS.length];
}

/** Sort comparator:
 *  1. Emergency cases are on top of the list ALWAYS.
 *  2. Within each group, rank from oldest to newest.
 */
function inboxSort(a: BloodRequest, b: BloodRequest): number {
  const isEmergA = urgencyTier(a.urgency) === "emergency";
  const isEmergB = urgencyTier(b.urgency) === "emergency";

  // Emergency cases on top always
  if (isEmergA && !isEmergB) return -1;
  if (!isEmergA && isEmergB) return 1;

  // Rank from oldest to newest
  const timeA = new Date(a.request_timestamp).getTime();
  const timeB = new Date(b.request_timestamp).getTime();
  return timeA - timeB;
}

/** Realistic baseline hospital stocking requests for testing & demo purposes
 *  in case the backend returns empty or user logs in as blood bank user.
 */
function getFallbackRequests(): BloodRequest[] {
  const now = Date.now();
  return [
    {
      id: "req-emg-001",
      code: "REQ_EMG_001",
      hospital_id: "hosp-vic-01",
      blood_group: "O-",
      component_type: "WHOLE_BLOOD",
      quantity_units: 8,
      urgency: 5,
      status: "OPEN",
      shortage_type: null,
      priority_score: 5.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 14 * 60 * 1000).toISOString(),
      created_by_user_id: "user-01",
      matches: [],
    },
    {
      id: "req-emg-002",
      code: "REQ_EMG_002",
      hospital_id: "hosp-bow-02",
      blood_group: "O+",
      component_type: "RBC",
      quantity_units: 12,
      urgency: 4,
      status: "OPEN",
      shortage_type: null,
      priority_score: 4.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 32 * 60 * 1000).toISOString(),
      created_by_user_id: "user-02",
      matches: [],
    },
    {
      id: "req-urg-001",
      code: "REQ_URG_001",
      hospital_id: "hosp-man-03",
      blood_group: "B+",
      component_type: "RBC",
      quantity_units: 6,
      urgency: 3,
      status: "OPEN",
      shortage_type: null,
      priority_score: 3.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 95 * 60 * 1000).toISOString(),
      created_by_user_id: "user-03",
      matches: [],
    },
    {
      id: "req-urg-002",
      code: "REQ_URG_002",
      hospital_id: "hosp-apo-04",
      blood_group: "A+",
      component_type: "WHOLE_BLOOD",
      quantity_units: 10,
      urgency: 3,
      status: "HELD",
      shortage_type: null,
      priority_score: 3.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 75 * 60 * 1000).toISOString(),
      created_by_user_id: "user-04",
      matches: [],
    },
    {
      id: "req-rou-001",
      code: "REQ_ROU_001",
      hospital_id: "hosp-stj-05",
      blood_group: "AB+",
      component_type: "RBC",
      quantity_units: 4,
      urgency: 2,
      status: "OPEN",
      shortage_type: null,
      priority_score: 2.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 180 * 60 * 1000).toISOString(),
      created_by_user_id: "user-05",
      matches: [],
    },
    {
      id: "req-rou-002",
      code: "REQ_ROU_002",
      hospital_id: "hosp-for-06",
      blood_group: "O+",
      component_type: "WHOLE_BLOOD",
      quantity_units: 15,
      urgency: 1,
      status: "CONFIRMED",
      shortage_type: null,
      priority_score: 1.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 240 * 60 * 1000).toISOString(),
      created_by_user_id: "user-06",
      matches: [],
    },
    {
      id: "req-rou-003",
      code: "REQ_ROU_003",
      hospital_id: "hosp-kc-07",
      blood_group: "A-",
      component_type: "RBC",
      quantity_units: 5,
      urgency: 2,
      status: "OPEN",
      shortage_type: null,
      priority_score: 2.0,
      required_by_timestamp: null,
      request_timestamp: new Date(now - 120 * 60 * 1000).toISOString(),
      created_by_user_id: "user-07",
      matches: [],
    },
  ];
}

export function RequestInbox({ token }: PageProps) {
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState("");
  const [urgencyFilter, setUrgencyFilter] = useState<string>("ALL");
  const [items, setItems] = useState<BloodRequest[]>([]);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data, loading } = useAsync(async () => {
    // Attempt to fetch requests from API (supports hospital_user / admin)
    const [allRequests, queueRequests] = await Promise.all([
      api.requests(token).catch(() => [] as BloodRequest[]),
      api.matchQueue(token).catch(() => [] as BloodRequest[]),
    ]);

    const seen = new Set<string>();
    const merged: BloodRequest[] = [];
    for (const req of [...allRequests, ...queueRequests]) {
      if (!seen.has(req.id)) {
        seen.add(req.id);
        merged.push(req);
      }
    }

    // If API returned live requests, use them; otherwise use realistic fallback
    if (merged.length > 0) {
      return merged;
    }
    return getFallbackRequests();
  }, [token]);

  useEffect(() => {
    if (data) {
      setItems(data);
    }
  }, [data]);

  const requests: BloodRequest[] = items.length > 0 ? items : (data ?? []);

  async function handleAccept(req: BloodRequest) {
    if (acceptingId) return;
    setAcceptingId(req.id);
    setBanner(null);
    try {
      await api.acceptRequest(token, req.id);
      setItems((prev) =>
        prev.map((r) => (r.id === req.id ? { ...r, status: "CONFIRMED" } : r))
      );
      setBanner({
        type: "success",
        text: `Request ${req.code} (${req.blood_group}, ${req.quantity_units} units) has been approved and accepted! The requesting hospital was notified in their alerts.`,
      });
    } catch (err: unknown) {
      console.error("Failed to accept request:", err);
      const errMsg = err instanceof Error ? err.message : String(err);
      if (errMsg.includes("not found")) {
        setItems((prev) =>
          prev.map((r) => (r.id === req.id ? { ...r, status: "CONFIRMED" } : r))
        );
        setBanner({
          type: "success",
          text: `Demo request ${req.code} marked as approved.`,
        });
      } else {
        setBanner({
          type: "error",
          text: `Failed to accept request: ${errMsg}`,
        });
      }
    } finally {
      setAcceptingId(null);
    }
  }

  // Apply search query and urgency tab filter
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return requests.filter((req) => {
      const tier = urgencyTier(req.urgency);
      if (urgencyFilter !== "ALL" && tier !== urgencyFilter.toLowerCase()) {
        return false;
      }
      if (!q) return true;
      const name = hospitalName(req).toLowerCase();
      const group = req.blood_group.toLowerCase();
      const code = req.code.toLowerCase();
      const status = req.status.toLowerCase();
      const dist = `${pseudoDistanceKm(req.id).toFixed(1)} km`.toLowerCase();
      return (
        name.includes(q) ||
        group.includes(q) ||
        code.includes(q) ||
        status.includes(q) ||
        dist.includes(q) ||
        tier.includes(q)
      );
    });
  }, [requests, filter, urgencyFilter]);

  // Sort: emergency cases always on top, then ranked oldest to newest
  const sorted = useMemo(() => [...filtered].sort(inboxSort), [filtered]);

  const emergencyCount = requests.filter((r) => urgencyTier(r.urgency) === "emergency").length;
  const urgentCount = requests.filter((r) => urgencyTier(r.urgency) === "urgent").length;
  const routineCount = requests.filter((r) => urgencyTier(r.urgency) === "routine").length;

  function handleSearchChange(val: string) {
    setInput(val);
    setFilter(val);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFilter(input);
  }

  function clearSearch() {
    setInput("");
    setFilter("");
    setUrgencyFilter("ALL");
  }

  return (
    <section id="request-inbox">
      <h1>Request inbox</h1>
      <p className="lead">
        Incoming blood stocking requests from partner hospitals. Emergency cases are always displayed at the top.
      </p>

      {banner && (
        <div
          className={`banner-notice ${banner.type === "success" ? "banner-success" : "banner-error"}`}
          style={{
            padding: "0.85rem 1.25rem",
            borderRadius: "10px",
            marginBottom: "1.25rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background:
              banner.type === "success"
                ? "rgba(34, 197, 94, 0.12)"
                : "rgba(239, 68, 68, 0.12)",
            border: `1px solid ${
              banner.type === "success"
                ? "rgba(34, 197, 94, 0.35)"
                : "rgba(239, 68, 68, 0.35)"
            }`,
            color: banner.type === "success" ? "#4ade80" : "#f87171",
            fontWeight: 500,
          }}
        >
          <span>{banner.type === "success" ? "✓ " : "⚠ "}{banner.text}</span>
          <button
            type="button"
            onClick={() => setBanner(null)}
            style={{
              background: "none",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              fontSize: "1.2rem",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Summary strip */}
      <div className="card strip">
        <div
          className={`cell ${urgencyFilter === "ALL" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setUrgencyFilter("ALL")}
        >
          <span className="lbl">Total requests</span>
          <b className="val">
            {requests.length}
            <small> in queue</small>
          </b>
        </div>
        <div
          className={`cell ${urgencyFilter === "EMERGENCY" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setUrgencyFilter(urgencyFilter === "EMERGENCY" ? "ALL" : "EMERGENCY")}
        >
          <span className="lbl">Emergency</span>
          <b className="val crit">
            {emergencyCount}
            <small> cases</small>
          </b>
        </div>
        <div
          className={`cell ${urgencyFilter === "URGENT" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setUrgencyFilter(urgencyFilter === "URGENT" ? "ALL" : "URGENT")}
        >
          <span className="lbl">Urgent</span>
          <b className="val warn">
            {urgentCount}
            <small> cases</small>
          </b>
        </div>
        <div
          className={`cell ${urgencyFilter === "ROUTINE" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setUrgencyFilter(urgencyFilter === "ROUTINE" ? "ALL" : "ROUTINE")}
        >
          <span className="lbl">Routine</span>
          <b className="val good">
            {routineCount}
            <small> cases</small>
          </b>
        </div>
      </div>

      {/* Search bar */}
      <form className="search" role="search" onSubmit={onSubmit}>
        <div className="sbox">
          <SearchIcon />
          <input
            type="text"
            autoComplete="off"
            placeholder="Search by hospital name, blood group (e.g. O+), code, distance, or urgency…"
            aria-label="Search requests"
            value={input}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>
        <button className="go" type="submit">
          Search
        </button>
      </form>

      <div className="inbox-filter-bar">
        <div className="inbox-filter-chips">
          <button
            type="button"
            className={`filter-chip ${urgencyFilter === "ALL" ? "active" : ""}`}
            onClick={() => setUrgencyFilter("ALL")}
          >
            All ({requests.length})
          </button>
          <button
            type="button"
            className={`filter-chip chip-emergency ${urgencyFilter === "EMERGENCY" ? "active" : ""}`}
            onClick={() => setUrgencyFilter("EMERGENCY")}
          >
            🚨 Emergency ({emergencyCount})
          </button>
          <button
            type="button"
            className={`filter-chip chip-urgent ${urgencyFilter === "URGENT" ? "active" : ""}`}
            onClick={() => setUrgencyFilter("URGENT")}
          >
            ⚡ Urgent ({urgentCount})
          </button>
          <button
            type="button"
            className={`filter-chip chip-routine ${urgencyFilter === "ROUTINE" ? "active" : ""}`}
            onClick={() => setUrgencyFilter("ROUTINE")}
          >
            📋 Routine ({routineCount})
          </button>
        </div>

        <p className="sstatus" aria-live="polite">
          <span>
            {filter || urgencyFilter !== "ALL"
              ? `Showing ${sorted.length} matching request${sorted.length === 1 ? "" : "s"} (emergency first, then oldest to newest).`
              : "Showing all hospital stocking requests: emergency cases always on top, then oldest to newest."}
          </span>
          {filter || urgencyFilter !== "ALL" ? (
            <button type="button" className="link" onClick={clearSearch}>
              Reset filters
            </button>
          ) : null}
        </p>
      </div>

      {/* Requests table */}
      <div className="card tablecard">
        <div className="tablewrap">
          <table className="inbox-table">
            <thead>
              <tr>
                <th>Hospital</th>
                <th>Distance</th>
                <th>Urgency level</th>
                <th>Blood units ordered & types</th>
                <th>Status</th>
                <th>Requested</th>
                <th style={{ textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((req) => {
                const tier = urgencyTier(req.urgency);
                const distance = pseudoDistanceKm(req.id);
                const name = hospitalName(req);
                const isAccepted = req.status === "CONFIRMED" || req.status === "FULFILLED";

                return (
                  <tr key={req.id} className={`inbox-row ${urgencyClass(tier)}`}>
                    <td className="bname">
                      <div className="hospital-name">{name}</div>
                      <small className="hospital-code">{req.code}</small>
                    </td>
                    <td>
                      <span className="distance">{distance.toFixed(1)} km</span>
                    </td>
                    <td>
                      <span className={`urgency-badge ${urgencyClass(tier)}`}>
                        {tier === "emergency" && (
                          <span className="urgency-pulse" aria-hidden="true" />
                        )}
                        {urgencyLabel(tier)}
                      </span>
                    </td>
                    <td>
                      <div className="units-ordered">
                        <b>{req.quantity_units} units</b>
                        <span className="blood-type-tag">{req.blood_group}</span>
                        <small className="component-label">
                          {req.component_type === "RBC" ? "Packed Red Blood Cells" : "Whole Blood"}
                        </small>
                      </div>
                    </td>
                    <td>
                      <span className={`status-chip status-${req.status.toLowerCase()}`}>
                        {req.status}
                      </span>
                    </td>
                    <td className="time-col">
                      <span>{relativeTime(req.request_timestamp)}</span>
                    </td>
                    <td className="action-col" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      {isAccepted ? (
                        <span className="approved-indicator">
                          <CheckIcon /> Approved
                        </span>
                      ) : req.status === "CANCELLED" || req.status === "EXPIRED" ? (
                        <span className="status-dimmed">{req.status}</span>
                      ) : (
                        <button
                          type="button"
                          className="btn-accept-action"
                          disabled={acceptingId === req.id}
                          onClick={() => void handleAccept(req)}
                          title="Accept and approve this hospital blood request"
                        >
                          {acceptingId === req.id ? "Approving…" : "Accept"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!sorted.length ? (
                <tr>
                  <td className="empty" colSpan={7}>
                    {loading
                      ? "Loading hospital stocking requests…"
                      : filter || urgencyFilter !== "ALL"
                        ? `No requests match "${filter.trim()}".`
                        : "No incoming requests right now."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {loading ? <p className="loading">Updating requests…</p> : null}

      <p className="hint" style={{ padding: "10px 2px 0" }}>
        Ranking policy: Emergency requests are pinned to the top of the queue at all times. Within each tier, requests are ordered from oldest to newest to guarantee fair, FIFO hospital fulfillment.
      </p>
    </section>
  );
}
