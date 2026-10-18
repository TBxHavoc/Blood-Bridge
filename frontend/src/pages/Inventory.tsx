import { useState, type FormEvent } from "react";

import { api, ApiError } from "../lib/api";
import { BLOOD_GROUPS, COMPONENT_TYPES, componentLabel, daysUntil, duration, status } from "../lib/blood";
import { buildStock } from "../lib/derive";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import { useNav } from "../app/NavContext";
import { ExpTag } from "../components/ExpTag";
import { Legend } from "../components/Legend";
import type { BloodGroup, ComponentType } from "../lib/types";

function isoDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function AddStockForm({ token, onAdded }: { token: string; onAdded: () => void }) {
  const [bloodGroup, setBloodGroup] = useState<BloodGroup>("O+");
  const [component, setComponent] = useState<ComponentType>("RBC");
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
        text: err instanceof ApiError ? err.message : "Could not add stock.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Add stock</h2>
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
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sComponent">Component</label>
            <select id="sComponent" value={component} onChange={(e) => setComponent(e.target.value as ComponentType)}>
              {COMPONENT_TYPES.map((c) => (
                <option key={c} value={c}>
                  {componentLabel(c)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sUnits">Units</label>
            <input
              id="sUnits"
              type="number"
              min={1}
              step={1}
              value={units}
              onChange={(e) => setUnits(Number(e.target.value))}
            />
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
  const canManage = user.role === "bloodbank_user" || user.role === "admin";
  const canAdd = user.role === "bloodbank_user";
  const bankId = user.role === "bloodbank_user" ? user.affiliated_org_id ?? undefined : undefined;

  const { data, error, loading, reload } = useAsync(async () => {
    const [depletion, usage] = await Promise.all([api.depletion(token), api.usage(token)]);
    const items = canManage ? await api.inventory(token) : [];
    return { depletion, usage, items };
  }, [token, canManage]);

  const stock = data ? buildStock(data.depletion, data.usage, { bankId }) : [];
  const items = data?.items ?? [];

  const totalUnits = items.length
    ? items.reduce((sum, item) => sum + item.units_available, 0)
    : stock.reduce((sum, item) => sum + item.units, 0);
  const weeklyUsage = Math.round(stock.reduce((sum, item) => sum + item.perDay * 7, 0));
  const lowTypes = stock.filter((item) => item.hours < 72).length;
  const expiringUnits = items.length
    ? items.reduce((sum, item) => {
        const days = daysUntil(item.expiry_date);
        return days >= 0 && days <= 7 ? sum + item.units_available : sum;
      }, 0)
    : stock.reduce((sum, item) => sum + (item.expiring?.units ?? 0), 0);

  return (
    <section id="inventory">
      <h1>Inventory</h1>
      <p className="lead">
        {canManage
          ? "Current stock, usage and restock options for every blood type."
          : "Read-only network supply. Raw batch inventory is visible only to blood banks and admins."}
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
          <span className="lbl">Total units in inventory</span>
          <b className="val">
            {totalUnits}
            <small> units</small>
          </b>
        </div>
        <div className="cell">
          <span className="lbl">Weekly usage</span>
          <b className="val">
            {weeklyUsage}
            <small> units</small>
          </b>
        </div>
        <div className="cell">
          <span className="lbl">Low stock types</span>
          <b className="val crit">
            {lowTypes}
            <small> of {stock.length} types</small>
          </b>
        </div>
        <div className="cell">
          <span className="lbl">Expiring soon</span>
          <b className="val warn">
            {expiringUnits}
            <small> units</small>
          </b>
        </div>
      </div>

      <Legend source={bankId ? "Your blood bank" : "Network-wide"} />

      <div className="card tablecard">
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>Blood type</th>
                <th>Total units</th>
                <th>Average used per day</th>
                <th>Estimated time before running out</th>
                <th>
                  <span className="sr">Restock</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {stock.map((item) => {
                const [cls, label] = status(item.hours);
                return (
                  <tr key={item.type}>
                    <td className="tcol">
                      <div className="tc">
                        <span>{item.type}</span>
                        {item.expiring ? <ExpTag expiring={item.expiring} /> : null}
                      </div>
                    </td>
                    <td>{item.units} units</td>
                    <td>{Math.round(item.perDay * 10) / 10} units</td>
                    <td>
                      <span className={`time ${cls}`}>{duration(item.hours)}</span>
                      <span className="st">{label}</span>
                    </td>
                    <td className="act">
                      <button
                        type="button"
                        className="restock"
                        aria-label={`Restock ${item.type}`}
                        onClick={() =>
                          go(user?.role === "bloodbank_user" ? "Request inbox" : "Find supplies", {
                            type: item.type,
                          })
                        }
                      >
                        Restock
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!stock.length && !loading ? (
                <tr>
                  <td className="empty" colSpan={5}>
                    No inventory data available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {loading ? <p className="loading">Loading inventory…</p> : null}

      <div style={{ marginTop: 24 }}>
        {canAdd ? (
          <AddStockForm token={token} onAdded={reload} />
        ) : (
          <p className="hint">
            {canManage
              ? "Adding stock is available to blood-bank accounts (admin writes need an explicit blood_bank_id)."
              : "Sign in as a blood-bank account to add or adjust stock."}
          </p>
        )}
      </div>
    </section>
  );
}
