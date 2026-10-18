import { useEffect, useMemo, useState, type FormEvent } from "react";

import { api } from "../lib/api";
import { availabilityOf, nameScore, parseQuery } from "../lib/blood";
import { buildBankSupply, type BankSupply } from "../lib/derive";
import { useAsync } from "../hooks/useAsync";
import type { PageProps } from "../app/PageProps";
import { useNav } from "../app/NavContext";
import { ArrowRight, SearchIcon } from "../components/Icons";
import type { BloodGroup } from "../lib/types";

export function FindSupplies({ token }: PageProps) {
  const { go, params } = useNav();
  const [input, setInput] = useState("");
  const [filter, setFilter] = useState<{ type: BloodGroup | ""; q: string }>({ type: "", q: "" });

  const { data, error, loading } = useAsync(async () => buildBankSupply(await api.depletion(token)), [token]);
  const banks: BankSupply[] = useMemo(() => data ?? [], [data]);

  // Deep-link from the Inventory "Restock" button: go('Find supplies', { type })
  useEffect(() => {
    if (params.type) {
      setInput(params.type);
      setFilter({ type: params.type, q: "" });
    }
  }, [params.type]);

  const { type, q } = filter;
  const all = useMemo(
    () =>
      banks.map((bank) => ({
        ...bank,
        units: type ? bank.unitsByType[type] ?? 0 : bank.total,
      })),
    [banks, type],
  );

  let list = all;
  let suggestion = "";
  if (type) list = list.filter((bank) => bank.units > 0);
  if (q) {
    const matched = all.filter((bank) => nameScore(bank.name, q) > 0);
    if (matched.length) {
      list = matched;
    } else {
      suggestion = `No blood bank matched "${input.trim()}". Showing the best-stocked bank instead.`;
      list = list.slice().sort((a, b) => b.units - a.units).slice(0, 1);
    }
  }
  list = list.slice().sort((a, b) => b.units - a.units || a.name.localeCompare(b.name));

  const unitsHead = type ? `Units of ${type}` : "Total units in stock";
  const statusText = suggestion
    ? suggestion
    : type
      ? `Showing banks with ${type} in stock, ranked by available units.`
      : q
        ? `Showing banks matching "${input.trim()}", ranked by available units.`
        : "Showing all blood banks, ranked by available units.";

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFilter(parseQuery(input));
  }

  function clearSearch() {
    setInput("");
    setFilter({ type: "", q: "" });
  }

  return (
    <section id="supplies">
      <h1>Find supplies</h1>
      <p className="lead">
        See which partner blood banks hold a blood type. Ranked by units available.
      </p>

      <form className="search" role="search" onSubmit={onSubmit}>
        <div className="sbox">
          <SearchIcon />
          <input
            type="text"
            autoComplete="off"
            placeholder="Search a blood type (like O-) or a blood bank"
            aria-label="Search a blood type or a blood bank"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
        </div>
        <button className="go" type="submit">
          Enter
        </button>
      </form>

      <p className="sstatus" aria-live="polite">
        <span>{statusText}</span>
        {type || q ? (
          <button type="button" className="link" onClick={clearSearch}>
            Clear search
          </button>
        ) : null}
      </p>

      {error ? (
        <div className="notice error">
          <span>
            <strong>Could not load blood banks</strong>
            <small>{error}</small>
          </span>
        </div>
      ) : null}

      <div className="card tablecard">
        <div className="tablewrap">
          <table className="supplies-table">
            <thead>
              <tr>
                <th className="rankcol">Rank</th>
                <th>Blood bank</th>
                <th>{unitsHead}</th>
                <th>Availability</th>
              </tr>
            </thead>
            <tbody>
              {list.map((bank, i) => {
                const [cls, label] = availabilityOf(bank.units, !!type);
                return (
                  <tr
                    key={bank.id}
                    className="bankrow"
                    title={`Request blood — ${bank.name}`}
                    onClick={() => go("Request blood", { bank: bank.name })}
                  >
                    <td>
                      <span className={`rank${i === 0 ? " top" : ""}`}>{i + 1}</span>
                    </td>
                    <td className="bname">
                      <button type="button" className="banklink">
                        {bank.name}
                        <ArrowRight />
                      </button>
                    </td>
                    <td>{bank.units} units</td>
                    <td>
                      <span className={`time ${cls}`}>{label}</span>
                    </td>
                  </tr>
                );
              })}
              {!list.length ? (
                <tr>
                  <td className="empty" colSpan={4}>
                    {loading
                      ? "Loading blood banks…"
                      : type
                        ? `No blood banks have ${type} in stock right now.`
                        : "No blood banks match your search."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      <p className="hint" style={{ padding: "10px 2px 0" }}>
        Distances and ETAs are computed per request — submit a request to see ranked suppliers.
      </p>
    </section>
  );
}
