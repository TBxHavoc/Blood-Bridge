import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { relativeTime } from "../lib/blood";
import type { PageProps } from "../app/PageProps";
import type { DeliveryTracking as DeliveryItem, DeliveryPhase } from "../lib/types";

/* ─── Phase helpers ─── */

function phaseIcon(phase: DeliveryPhase): string {
  switch (phase) {
    case "DISPATCHED":
      return "🩸";
    case "IN_TRANSIT":
      return "🚑";
    case "ARRIVING":
      return "🏥";
    case "DELIVERED":
      return "✅";
    default:
      return "📦";
  }
}

function phaseLabel(phase: DeliveryPhase): string {
  switch (phase) {
    case "DISPATCHED":
      return "Dispatched";
    case "IN_TRANSIT":
      return "In Transit";
    case "ARRIVING":
      return "Arriving Now";
    case "DELIVERED":
      return "Delivered";
    default:
      return phase;
  }
}

function phaseBadgeClass(phase: DeliveryPhase): string {
  switch (phase) {
    case "DISPATCHED":
      return "delivery-badge-dispatched";
    case "IN_TRANSIT":
      return "delivery-badge-transit";
    case "ARRIVING":
      return "delivery-badge-arriving";
    case "DELIVERED":
      return "delivery-badge-delivered";
    default:
      return "";
  }
}

function phaseStepIndex(phase: DeliveryPhase): number {
  switch (phase) {
    case "DISPATCHED":
      return 0;
    case "IN_TRANSIT":
      return 1;
    case "ARRIVING":
      return 2;
    case "DELIVERED":
      return 3;
    default:
      return 0;
  }
}

const PHASE_STEPS = ["Dispatched", "In Transit", "Arriving", "Delivered"];

/* ─── ETA countdown display ─── */

function ETADisplay({ delivery }: { delivery: DeliveryItem }) {
  if (delivery.phase === "DELIVERED") {
    return (
      <div className="delivery-eta-box delivery-eta-done">
        <span className="eta-label">Delivered</span>
        <span className="eta-value">✅</span>
      </div>
    );
  }

  if (!delivery.show_eta) {
    return (
      <div className="delivery-eta-box delivery-eta-pending">
        <span className="eta-label">ETA</span>
        <span className="eta-value eta-calculating">
          <span className="eta-dot-pulse" />
          Calculating…
        </span>
        <span className="eta-hint">Available in ~5 min after dispatch</span>
      </div>
    );
  }

  const mins = Math.ceil(delivery.eta_remaining_minutes);
  return (
    <div className="delivery-eta-box delivery-eta-active">
      <span className="eta-label">Estimated Arrival</span>
      <span className="eta-value eta-countdown">
        {mins <= 0 ? "Any moment" : `${mins} min`}
      </span>
      <span className="eta-distance">{delivery.distance_km} km away</span>
    </div>
  );
}

/* ─── Progress bar stepper ─── */

function DeliveryProgress({ phase }: { phase: DeliveryPhase }) {
  const currentStep = phaseStepIndex(phase);
  return (
    <div className="delivery-stepper">
      {PHASE_STEPS.map((label, i) => (
        <div
          key={label}
          className={`stepper-step ${i <= currentStep ? "stepper-done" : ""} ${
            i === currentStep ? "stepper-current" : ""
          }`}
        >
          <div className="stepper-dot">
            {i < currentStep ? (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path
                  d="M2 6l3 3 5-5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : i === currentStep ? (
              <span className="stepper-pulse" />
            ) : null}
          </div>
          {i < PHASE_STEPS.length - 1 && (
            <div className={`stepper-line ${i < currentStep ? "stepper-line-done" : ""}`} />
          )}
          <span className="stepper-label">{label}</span>
        </div>
      ))}
    </div>
  );
}

/* ─── Main component ─── */

type FilterTab = "ALL" | "ACTIVE" | "DELIVERED";

export function DeliveryTrackingPage({ token }: PageProps) {
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>("ALL");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const fetchDeliveries = useCallback(async () => {
    try {
      const data = await api.deliveries(token);
      setDeliveries(data);
    } catch (err) {
      console.error("Failed to load deliveries:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchDeliveries();
    // Poll every 10 seconds for live ETA updates
    const interval = setInterval(() => {
      void fetchDeliveries();
    }, 10_000);
    return () => clearInterval(interval);
  }, [fetchDeliveries]);

  const confirmArrival = async (id: string) => {
    if (confirmingId) return;
    setConfirmingId(id);
    try {
      const updated = await api.confirmDeliveryArrival(token, id);
      setDeliveries((prev) =>
        prev.map((d) => (d.id === id ? updated : d))
      );
    } catch (err) {
      console.error("Failed to confirm delivery:", err);
    } finally {
      setConfirmingId(null);
    }
  };

  const activeCount = deliveries.filter((d) => d.phase !== "DELIVERED").length;
  const deliveredCount = deliveries.filter((d) => d.phase === "DELIVERED").length;

  const filtered = useMemo(() => {
    if (filter === "ACTIVE") return deliveries.filter((d) => d.phase !== "DELIVERED");
    if (filter === "DELIVERED") return deliveries.filter((d) => d.phase === "DELIVERED");
    return deliveries;
  }, [deliveries, filter]);

  return (
    <section id="delivery-tracking-page">
      {/* ─── Header ─── */}
      <div className="delivery-header">
        <div>
          <h1>Delivery Tracking</h1>
          <p className="lead">
            Live ETA monitoring for approved blood deliveries. Track dispatched
            shipments from blood banks in real time.
          </p>
        </div>
        <div className="delivery-header-actions">
          <span className="live-pulse-badge">
            <span className="live-dot" /> Live tracking active
          </span>
        </div>
      </div>

      {/* ─── Summary strip / Filter bar ─── */}
      <div className="card strip" style={{ marginBottom: "1.25rem" }}>
        <div
          className={`cell ${filter === "ALL" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("ALL")}
        >
          <span className="lbl">All deliveries</span>
          <b className="val">
            {deliveries.length}
            <small> total</small>
          </b>
        </div>
        <div
          className={`cell ${filter === "ACTIVE" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("ACTIVE")}
        >
          <span className="lbl">In Progress</span>
          <b className={`val ${activeCount > 0 ? "warn" : ""}`}>
            {activeCount}
            <small> active</small>
          </b>
        </div>
        <div
          className={`cell ${filter === "DELIVERED" ? "cell-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("DELIVERED")}
        >
          <span className="lbl">Completed</span>
          <b className="val good">
            {deliveredCount}
            <small> delivered</small>
          </b>
        </div>
      </div>

      {/* ─── Deliveries list ─── */}
      <div className="delivery-container">
        {loading && deliveries.length === 0 ? (
          <div className="card" style={{ padding: "3rem", textAlign: "center" }}>
            <p className="loading">Loading deliveries…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="card delivery-empty">
            <div className="empty-icon">🚑</div>
            <h3>No deliveries found</h3>
            <p className="hint">
              {filter === "ACTIVE"
                ? "No active deliveries right now. When a blood bank approves your request, the shipment will appear here."
                : filter === "DELIVERED"
                ? "No completed deliveries yet."
                : "When a blood bank approves a request, delivery tracking will appear here with real-time ETA."}
            </p>
          </div>
        ) : (
          <div className="delivery-card-list">
            {filtered.map((item) => {
              const isActive = item.phase !== "DELIVERED";

              return (
                <div
                  key={item.id}
                  className={`card delivery-card ${
                    isActive ? "delivery-card-active" : "delivery-card-done"
                  }`}
                >
                  {/* Top row: badge + time */}
                  <div className="delivery-card-top">
                    <div className="delivery-badge-group">
                      <span className={`delivery-badge ${phaseBadgeClass(item.phase)}`}>
                        {phaseIcon(item.phase)} {phaseLabel(item.phase)}
                      </span>
                      {item.request_code && (
                        <span className="delivery-request-code">{item.request_code}</span>
                      )}
                    </div>
                    <time className="delivery-time" dateTime={item.created_at || ""}>
                      {item.dispatched_at ? relativeTime(item.dispatched_at) : "—"}
                    </time>
                  </div>

                  {/* Message */}
                  <p className="delivery-message">{item.message}</p>

                  {/* Details row */}
                  <div className="delivery-details">
                    <div className="delivery-detail">
                      <span className="detail-label">Blood Group</span>
                      <span className="detail-value detail-blood">{item.blood_group || "—"}</span>
                    </div>
                    <div className="delivery-detail">
                      <span className="detail-label">Type</span>
                      <span className="detail-value">{item.component_type?.replace("_", " ") || "—"}</span>
                    </div>
                    <div className="delivery-detail">
                      <span className="detail-label">Units</span>
                      <span className="detail-value">{item.quantity_units ?? "—"}</span>
                    </div>
                    <div className="delivery-detail">
                      <span className="detail-label">From</span>
                      <span className="detail-value">{item.blood_bank_name}</span>
                    </div>
                  </div>

                  {/* Stepper progress */}
                  <DeliveryProgress phase={item.phase} />

                  {/* ETA section */}
                  <ETADisplay delivery={item} />

                  {/* Footer / Actions */}
                  <div className="delivery-card-footer">
                    <span className="delivery-elapsed">
                      {item.phase !== "DELIVERED"
                        ? `${Math.round(item.elapsed_minutes)} min since dispatch`
                        : item.delivered_at
                        ? `Delivered ${relativeTime(item.delivered_at)}`
                        : "Delivered"}
                    </span>
                    {isActive && item.phase === "ARRIVING" && (
                      <button
                        type="button"
                        className="btn-confirm-arrival"
                        disabled={confirmingId === item.id}
                        onClick={() => confirmArrival(item.id)}
                      >
                        {confirmingId === item.id ? "Confirming…" : "✓ Confirm Arrival"}
                      </button>
                    )}
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
