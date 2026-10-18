import { useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { BLOOD_GROUPS, COMPONENT_TYPES, componentLabel } from "../lib/blood";
import {
  buildStockFromErakthosh,
  buildStockFromInventory,
} from "../lib/derive";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import { useNav } from "../app/NavContext";
import { Legend } from "../components/Legend";
import type {
  BloodGroup,
  EraktkoshSummary,
  InventoryItem,
} from "../lib/types";

function isoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/* ---------------------------------------------------------------- Add stock */
/* Blood banks write to their own inventory; never to the public snapshot. */
function AddStockForm({ token, onAdded }: { token: string; onAdded: () => void }) {
  const [bloodGroup, setBloodGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<"RBC" | "WHOLE_BLOOD">("RBC");
  const [units, setUnits] = useState(20);
  const [collection, setCollection] = useState(isoDate(0));
  const [expiry, setExpiry] = useState(isoDate(35));
  const [rack, setRack] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setBusy(true);
    try {
      await api.createInventory(token, {
        blood_group: bloodGroup,
        component_type: component,
        units_available: units,
        collection_date: collection,
        expiry_date: expiry,
        storage_location_code: rack || null,
      });
      setMessage({ ok: true, text: `Added ${units} units of ${bloodGroup} ${componentLabel(component)}.` });
      onAdded();
    } catch (err) {
      setMessage({
        ok: false,
        text: err instanceof Error ? err.message : "Could not add stock.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Add stock — your blood bank</h2>
      <div className="body">
        {message ? (
          <div className={`notice${message.ok ? "" : " error"}`}>
            <span>
              <strong>{message.ok ? "Stock added" : "Could not add stock"}</strong>
              <small>{message.text}</small>
            </span>
          </div>
        ) : null}
        <form className="form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="sGroup">Blood type</label>
            <select id="sGroup" value={bloodGroup} onChange={(e) => setBloodGroup(e.target.value as BloodGroup)}>
              {BLOOD_GROUPS.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sComponent">Component</label>
          <select id="sComponent" value={component} onChange={(e) => setComponent(e.target.value as "RBC" | "WHOLE_BLOOD")}>
            {COMPONENT_TYPES.map((c) => (
              <option key={c} value={c}>{componentLabel(c)}</option>
            ))}
          </select>
          </div>
          <div className="field">
            <label htmlFor="sUnits">Units</label>
            <input id="sUnits" type="number" min={1} step={1} value={units} onChange={(e) => setUnits(Number(e.target.value))} />
          </div>
          <div className="field">
            <label htmlFor="sRack">Storage location (optional)</label>
            <input id="sRack" type="text" value={rack} onChange={(e) => setRack(e.target.value)} placeholder="RACK_A3" />
          </div>
          <div className="field">
            <label htmlFor="sCollection">Collection date</label>
            <input id="sCollection" type="date" value={collection} onChange={(e) => setCollection(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="sExpiry">Expiry date</label>
            <input id="sExpiry" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
          </div>
          <div className="actions">
            <button className="submit" type="submit" disabled={busy}>
              {busy ? "Adding…" : "Add stock"}
            </button>
            <span className="hint">Written straight to your blood bank's inventory.</span>
          </div>
        </form>
      </div>
    </div>
  );
}

export function Inventory({ token, user }: PageProps) {
  const { go } = useNav();
  const isBank = user.role === "bloodbank_user";
  const isHospital = user.role === "hospital_user";

  const { data, error, loading, reload } = useAsync(async () => {
    if (isBank) {
      const items = await api.inventory(token);
      return { kind: "bank", items } as const;
    }
    if (isHospital) {
      return { kind: "hospital" } as const;
    }
    const summary = await api.eraktkoshSummary();
    return { kind: "network", summary } as const;
  }, [token, user.role, isBank, isHospital]);

  /* -------------------------------- Blood bank: own DB inventory ---------- */
  if (isBank) {
    const items = (data as { kind: "bank"; items: InventoryItem[] } | null)?.items ?? [];
    const stock = buildStockFromInventory(items);
    const totalUnits = items.reduce((sum, item) => sum + item.units_available, 0);
    const affiliated = user.affiliated_org_id ?? "your bank";

    return (
      <section id="inventory">
        <h1>Inventory — your blood bank</h1>
        <p className="lead">
          Your blood bank's own stock (database), not the public eRaktKosh
          snapshot. Add stock below; changes are written to your bank's
          inventory ({affiliated}).
        </p>

        {error ? (
          <div className="notice error">
            <span>
              <strong>Could not load inventory</strong>
              <small>{error}</small>
            </span>
          </div>
        ) : null}

        <div className="card strip">
          <div className="cell">
            <span className="lbl">Total units available</span>
            <b className="val">{totalUnits.toLocaleString()}<small> units</small></b>
          </div>
          <div className="cell">
            <span className="lbl">Blood groups tracked</span>
            <b className="val">{stock.length}</b>
          </div>
          <div className="cell">
            <span className="lbl">Low stock groups (&lt;100 units)</span>
            <b className="val crit">{stock.filter((item) => item.units < 100).length}</b>
          </div>
          <div className="cell">
            <span className="lbl">Expiring &le; 7 days</span>
            <b className="val warn">
              {stock.reduce((sum, item) => sum + (item.expiring?.units ?? 0), 0)}
            </b>
          </div>
        </div>

        <Legend source={`Blood bank ${affiliated} · own inventory`} />

        <div className="card tablecard">
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Blood type</th>
                  <th>Available units</th>
                  <th>Reserved units</th>
                  <th>Expiring ≤ 7 days</th>
                  <th><span className="sr">Restock</span></th>
                </tr>
              </thead>
              <tbody>
                {stock.map((item) => (
                  <tr key={item.type}>
                    <td className="tcol">
                      <div className="tc"><span>{item.type}</span></div>
                    </td>
                    <td>{item.units.toLocaleString()}</td>
                    <td>{item.reserved.toLocaleString()}</td>
                    <td>{item.expiring?.units ?? 0}</td>
                    <td className="act">
                      <button
                        type="button"
                        className="restock"
                        aria-label={`Restock ${item.type}`}
                        onClick={() => go("Find supplies", { type: item.type })}
                      >
                        Restock
                      </button>
                    </td>
                  </tr>
                ))}
                {!stock.length && !loading ? (
                  <tr>
                    <td className="empty" colSpan={5}>
                      No inventory for your blood bank yet. Add stock below.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        <AddStockForm token={token} onAdded={reload} />
        {loading ? <p className="loading">Loading inventory…</p> : null}
      </section>
    );
  }
  if (isHospital) {
    return (
      <section id="inventory">
        <h1>Inventory — your hospital</h1>
        <p className="lead">
          Hospitals request blood; they do not hold inventory. Inventory is
          owned and managed by blood banks, so there is no stock to display for
          your hospital here.
        </p>
        <div className="notice">
          <span>
            <strong>No inventory for your hospital.</strong> Use{" "}
            <button
              type="button"
              className="link"
              onClick={() => go("Request blood")}
            >
              Request blood
            </button>{" "}
            to send a request to partner blood banks.
          </span>
        </div>
      </section>
    );
  }

  /* --------------------------- Admin / auditor: live network stock -------- */
  const summary = (data as { kind: "network"; summary: EraktkoshSummary } | null)
    ?.summary;
  const stock = summary ? buildStockFromErakthosh(summary) : [];
  const totalUnits = stock.reduce((sum, item) => sum + item.units, 0);

  return (
    <section id="inventory">
      <h1>Inventory — live network stock</h1>
      <p className="lead">
        Live Bengaluru blood stock scraped from eRaktKosh (MoHFW / C-DAC),
        refreshed every 10 minutes. Figures are indicative — call the blood
        centre to confirm availability before dispatching emergency requests.
      </p>

      {error ? (
        <div className="notice error">
          <span>
            <strong>Could not load inventory</strong>
            <small>{error}</small>
          </span>
        </div>
      ) : null}

      <div className="card strip">
        <div className="cell">
          <span className="lbl">Total units in stock</span>
          <b className="val">{totalUnits.toLocaleString()}<small> units</small></b>
        </div>
        <div className="cell">
          <span className="lbl">Blood groups tracked</span>
          <b className="val">{stock.length}</b>
        </div>
        <div className="cell">
          <span className="lbl">Records scanned</span>
          <b className="val">{summary?.total_records_scanned?.toLocaleString() ?? 0}</b>
        </div>
        <div className="cell">
          <span className="lbl">Last scraped</span>
          <b className="val">
            {summary?.last_updated_iso ? new Date(summary.last_updated_iso).toLocaleString() : "—"}
          </b>
        </div>
      </div>

      <Legend source="Live eRaktKosh stock (no consumption forecast)" />

      <div className="card tablecard">
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Blood type</th>
                <th>Total units</th>
                <th>Unique banks</th>
                <th>Records</th>
                <th><span className="sr">Find supplies</span></th>
              </tr>
            </thead>
            <tbody>
              {stock.map((item) => {
                const g = summary?.blood_groups[item.type];
                return (
                  <tr key={item.type}>
                    <td className="tcol">
                      <div className="tc"><span>{item.type}</span></div>
                    </td>
                    <td>{item.units.toLocaleString()} units</td>
                    <td>{g?.unique_banks ?? 0}</td>
                    <td>{g?.record_count ?? 0}</td>
                    <td className="act">
                      <button
                        type="button"
                        className="restock"
                        aria-label={`Find supplies for ${item.type}`}
                        onClick={() => go("Find supplies", { type: item.type })}
                      >
                        View banks
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!stock.length && !loading ? (
                <tr>
                  <td className="empty" colSpan={5}>
                    No inventory data available. Run the eRaktKosh scraper to
                    load live Bengaluru stock.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {loading ? <p className="loading">Loading live inventory…</p> : null}
    </section>
  );
}
