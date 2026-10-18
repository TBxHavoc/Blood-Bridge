import { useCallback, useEffect, useMemo, useState } from "react";
import { SearchIcon } from "../components/Icons";

interface BloodGroupSummary {
  key: string;
  total_units: number;
  unique_banks: number;
  record_count: number;
  file_json: string;
  file_csv: string;
}

interface OverallSummary {
  last_updated: string;
  last_updated_iso: string;
  total_records_scanned: number;
  blood_groups: Record<string, BloodGroupSummary>;
}

interface BankStockRecord {
  blood_bank_name: string;
  category: string;
  district: string;
  component: string;
  units: number;
  phone: string;
  email: string;
  address: string;
  last_updated: string;
  type: string;
  all_groups?: Record<string, number>;
}

interface BloodGroupPayload {
  blood_group: string;
  key: string;
  city: string;
  last_updated: string;
  last_updated_iso: string;
  total_units: number;
  unique_banks: number;
  record_count: number;
  data: BankStockRecord[];
}

const BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"] as const;
type BloodGroup = (typeof BLOOD_GROUPS)[number];

const GROUP_KEY_MAP: Record<BloodGroup, string> = {
  "O+": "O_positive",
  "O-": "O_negative",
  "A+": "A_positive",
  "A-": "A_negative",
  "B+": "B_positive",
  "B-": "B_negative",
  "AB+": "AB_positive",
  "AB-": "AB_negative",
};

export function LiveERaktKosh() {
  const [selectedGroup, setSelectedGroup] = useState<BloodGroup>("O+");
  const [summary, setSummary] = useState<OverallSummary | null>(null);
  const [groupData, setGroupData] = useState<BloodGroupPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedComponent, setSelectedComponent] = useState("ALL");
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastCheckTime, setLastCheckTime] = useState<Date>(new Date());

  // Fetch overall summary
  const fetchSummary = useCallback(async () => {
    try {
      // Try local static json first (direct from public/data/eraktkosh)
      const res = await fetch(`/data/eraktkosh/summary.json?t=${Date.now()}`);
      if (res.ok) {
        const data: OverallSummary = await res.json();
        setSummary(data);
        return data;
      }
    } catch {
      // Fallback to backend API
      try {
        const apiRes = await fetch(`/api/v1/eraktkosh/summary?t=${Date.now()}`);
        if (apiRes.ok) {
          const env = await apiRes.json();
          if (env.data) {
            setSummary(env.data);
            return env.data;
          }
        }
      } catch {
        // quiet fallback
      }
    }
    return null;
  }, []);

  // Fetch specific blood group data
  const fetchGroupData = useCallback(async (bg: BloodGroup) => {
    const key = GROUP_KEY_MAP[bg];
    setLoading(true);
    setError(null);
    try {
      // Try static json directly from public
      const res = await fetch(`/data/eraktkosh/${key}.json?t=${Date.now()}`);
      if (res.ok) {
        const data: BloodGroupPayload = await res.json();
        setGroupData(data);
        setLoading(false);
        return;
      }

      // Fallback to backend API
      const apiRes = await fetch(`/api/v1/eraktkosh/bangalore/${bg}?t=${Date.now()}`);
      if (apiRes.ok) {
        const env = await apiRes.json();
        if (env.data) {
          setGroupData(env.data);
          setLoading(false);
          return;
        }
      }
      throw new Error(`Could not load data for blood group ${bg}`);
    } catch (err) {
      setError((err as Error).message || "Failed to load live data");
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchSummary();
    fetchGroupData(selectedGroup);
  }, [fetchSummary, fetchGroupData, selectedGroup]);

  // Periodic polling every 30 seconds for real-time reflection of scraper updates
  useEffect(() => {
    const interval = setInterval(async () => {
      const freshSummary = await fetchSummary();
      setLastCheckTime(new Date());
      if (freshSummary && summary && freshSummary.last_updated_iso !== summary.last_updated_iso) {
        // Scraper wrote new data! Re-fetch active blood group immediately
        fetchGroupData(selectedGroup);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchSummary, fetchGroupData, selectedGroup, summary]);

  // Manual refresh handler
  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await fetchSummary();
    await fetchGroupData(selectedGroup);
    setLastCheckTime(new Date());
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Extract unique component types
  const availableComponents = useMemo(() => {
    if (!groupData?.data) return [];
    const comps = new Set<string>();
    for (const r of groupData.data) {
      if (r.component) comps.add(r.component);
    }
    return Array.from(comps).sort();
  }, [groupData]);

  // Filtered bank records
  const filteredRecords = useMemo(() => {
    if (!groupData?.data) return [];
    return groupData.data.filter((r) => {
      // Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = r.blood_bank_name.toLowerCase().includes(q);
        const matchesAddr = r.address.toLowerCase().includes(q);
        const matchesDist = r.district.toLowerCase().includes(q);
        if (!matchesName && !matchesAddr && !matchesDist) return false;
      }
      // Component filter
      if (selectedComponent !== "ALL" && r.component !== selectedComponent) {
        return false;
      }
      // Category filter
      if (selectedCategory !== "ALL") {
        if (!r.category.toLowerCase().includes(selectedCategory.toLowerCase())) {
          return false;
        }
      }
      return true;
    });
  }, [groupData, searchQuery, selectedComponent, selectedCategory]);

  return (
    <section id="live-eraktkosh" style={{ paddingBottom: "3rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1.25rem" }}>
        <div>
          <h1 style={{ margin: "0 0 0.35rem 0", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span>Bengaluru Blood Stock</span>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#166534",
                background: "#dcfce7",
                padding: "0.2rem 0.6rem",
                borderRadius: "9999px",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.35rem",
                letterSpacing: "0.02em",
                border: "1px solid #bbf7d0"
              }}
            >
              <span
                style={{
                  width: "7px",
                  height: "7px",
                  backgroundColor: "#22c55e",
                  borderRadius: "50%",
                  display: "inline-block",
                  boxShadow: "0 0 0 2px rgba(34, 197, 94, 0.4)"
                }}
              />
              LIVE • SYNCED EVERY 10 MIN
            </span>
          </h1>
          <p className="lead" style={{ margin: 0, color: "var(--muted)" }}>
            Public aggregate blood units published by eRaktKosh (MoHFW / C-DAC) across Bangalore Urban & Rural.
          </p>
        </div>

        {/* Sync Status / Refresh Button */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ textAlign: "right", fontSize: "0.8rem", color: "var(--muted)" }}>
            <div>Last Scraped: <strong>{groupData?.last_updated || summary?.last_updated || "Syncing..."}</strong></div>
            <div style={{ fontSize: "0.75rem" }}>Next cycle in ~10m • Checked {lastCheckTime.toLocaleTimeString()}</div>
          </div>
          <button
            type="button"
            className="ghost"
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.45rem 0.85rem", fontSize: "0.85rem" }}
          >
            <span style={{ display: "inline-block", transform: isRefreshing ? "rotate(360deg)" : "none", transition: "transform 0.5s ease" }}>
              ↻
            </span>
            {isRefreshing ? "Checking..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Blood Group Selector Pills */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
          gap: "0.6rem",
          marginBottom: "1.5rem"
        }}
      >
        {BLOOD_GROUPS.map((bg) => {
          const isSelected = selectedGroup === bg;
          const bgSummary = summary?.blood_groups[bg];
          const units = bgSummary?.total_units ?? (groupData?.blood_group === bg ? groupData.total_units : 0);
          const banks = bgSummary?.unique_banks ?? (groupData?.blood_group === bg ? groupData.unique_banks : 0);

          return (
            <button
              key={bg}
              type="button"
              onClick={() => setSelectedGroup(bg)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "0.75rem 0.5rem",
                borderRadius: "10px",
                border: isSelected ? "2px solid var(--red)" : "1px solid var(--line)",
                backgroundColor: isSelected ? "var(--red-tint)" : "var(--white)",
                color: isSelected ? "var(--red-deep)" : "var(--ink)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: isSelected ? "0 2px 8px rgba(163, 20, 36, 0.15)" : "0 1px 2px rgba(0,0,0,0.02)"
              }}
            >
              <span style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.02em" }}>{bg}</span>
              <span style={{ fontSize: "0.85rem", fontWeight: 600, color: isSelected ? "var(--red)" : "var(--ink)" }}>
                {units.toLocaleString()} units
              </span>
              <span style={{ fontSize: "0.7rem", color: isSelected ? "var(--red-deep)" : "var(--muted)" }}>
                {banks} blood banks
              </span>
            </button>
          );
        })}
      </div>

      {/* Search and Filters */}
      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: "1.25rem",
          backgroundColor: "var(--white)",
          padding: "0.85rem 1rem",
          borderRadius: "8px",
          border: "1px solid var(--line)"
        }}
      >
        {/* Search input */}
        <div style={{ flex: "1 1 240px", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <SearchIcon />
          <input
            type="text"
            placeholder={`Filter ${selectedGroup} banks by name, area or district...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "0.4rem 0.6rem",
              border: "1px solid var(--line)",
              borderRadius: "6px",
              fontSize: "0.88rem"
            }}
          />
        </div>

        {/* Component filter */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <label htmlFor="comp-select" style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--muted)" }}>
            Component:
          </label>
          <select
            id="comp-select"
            value={selectedComponent}
            onChange={(e) => setSelectedComponent(e.target.value)}
            style={{
              padding: "0.4rem 0.6rem",
              borderRadius: "6px",
              border: "1px solid var(--line)",
              backgroundColor: "var(--white)",
              fontSize: "0.85rem"
            }}
          >
            <option value="ALL">All Components ({groupData?.record_count ?? 0})</option>
            {availableComponents.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Category filter */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <label htmlFor="cat-select" style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--muted)" }}>
            Type:
          </label>
          <select
            id="cat-select"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{
              padding: "0.4rem 0.6rem",
              borderRadius: "6px",
              border: "1px solid var(--line)",
              backgroundColor: "var(--white)",
              fontSize: "0.85rem"
            }}
          >
            <option value="ALL">All Categories</option>
            <option value="Govt">Govt.</option>
            <option value="Red Cross">Red Cross</option>
            <option value="Charitable">Charitable / Voluntary</option>
            <option value="Private">Private</option>
          </select>
        </div>

        {/* Clear Filters */}
        {(searchQuery || selectedComponent !== "ALL" || selectedCategory !== "ALL") && (
          <button
            type="button"
            className="link"
            onClick={() => {
              setSearchQuery("");
              setSelectedComponent("ALL");
              setSelectedCategory("ALL");
            }}
            style={{ fontSize: "0.8rem" }}
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Content Area */}
      {loading ? (
        <div className="blank" style={{ padding: "3rem 1rem", textAlign: "center" }}>
          Loading latest {selectedGroup} blood stock from Bengaluru centers…
        </div>
      ) : error ? (
        <div className="blank" style={{ color: "var(--crit)", borderColor: "var(--crit)" }}>
          <p>{error}</p>
          <button type="button" className="ghost" onClick={() => fetchGroupData(selectedGroup)}>
            Retry
          </button>
        </div>
      ) : filteredRecords.length === 0 ? (
        <div className="blank" style={{ textAlign: "center", padding: "2.5rem 1rem" }}>
          <p style={{ margin: "0 0 0.5rem 0", fontWeight: 500 }}>No blood banks match your current filters.</p>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
            Try clearing the search query or selecting "All Components".
          </p>
        </div>
      ) : (
        <div style={{ overflowX: "auto", backgroundColor: "var(--white)", borderRadius: "8px", border: "1px solid var(--line)" }}>
          <table className="inv-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
            <thead>
              <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--line)", textAlign: "left" }}>
                <th style={{ padding: "0.75rem 1rem" }}>Blood Bank & Location</th>
                <th style={{ padding: "0.75rem 0.75rem" }}>Category</th>
                <th style={{ padding: "0.75rem 0.75rem" }}>Component</th>
                <th style={{ padding: "0.75rem 0.75rem", textAlign: "right" }}>{selectedGroup} Units</th>
                <th style={{ padding: "0.75rem 0.75rem" }}>Contact</th>
                <th style={{ padding: "0.75rem 1rem" }}>eRaktKosh Sync</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((r, idx) => {
                const isHighStock = r.units >= 50;
                const isModerateStock = r.units >= 10;
                return (
                  <tr
                    key={`${r.blood_bank_name}-${r.component}-${idx}`}
                    style={{
                      borderBottom: "1px solid var(--line)",
                      backgroundColor: idx % 2 === 0 ? "var(--white)" : "rgba(247, 244, 244, 0.4)"
                    }}
                  >
                    {/* Bank & Address */}
                    <td style={{ padding: "0.85rem 1rem", verticalAlign: "top", maxWidth: "320px" }}>
                      <div style={{ fontWeight: 600, color: "var(--ink)", marginBottom: "0.2rem" }}>
                        {r.blood_bank_name}
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "var(--muted)", lineHeight: 1.35 }}>
                        {r.address}
                      </div>
                    </td>

                    {/* Category */}
                    <td style={{ padding: "0.85rem 0.75rem", verticalAlign: "top" }}>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 500,
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          backgroundColor:
                            r.category.includes("Govt")
                              ? "#e0f2fe"
                              : r.category.includes("Red Cross")
                              ? "#fee2e2"
                              : r.category.includes("Charitable")
                              ? "#fef3c7"
                              : "#f3f4f6",
                          color:
                            r.category.includes("Govt")
                              ? "#0369a1"
                              : r.category.includes("Red Cross")
                              ? "#b91c1c"
                              : r.category.includes("Charitable")
                              ? "#b45309"
                              : "#374151"
                        }}
                      >
                        {r.category}
                      </span>
                    </td>

                    {/* Component */}
                    <td style={{ padding: "0.85rem 0.75rem", verticalAlign: "top", color: "var(--ink)", fontWeight: 500 }}>
                      {r.component}
                    </td>

                    {/* Units */}
                    <td style={{ padding: "0.85rem 0.75rem", verticalAlign: "top", textAlign: "right" }}>
                      <span
                        style={{
                          display: "inline-block",
                          fontWeight: 700,
                          fontSize: "1rem",
                          padding: "0.2rem 0.6rem",
                          borderRadius: "6px",
                          backgroundColor: isHighStock ? "var(--good-bg)" : isModerateStock ? "var(--warn-bg)" : "var(--low-bg)",
                          color: isHighStock ? "var(--good)" : isModerateStock ? "var(--warn)" : "var(--low)"
                        }}
                      >
                        {r.units}
                      </span>
                    </td>

                    {/* Contact */}
                    <td style={{ padding: "0.85rem 0.75rem", verticalAlign: "top", fontSize: "0.8rem", whiteSpace: "nowrap" }}>
                      {r.phone ? (
                        <div style={{ marginBottom: "0.25rem" }}>
                          <a
                            href={`tel:${r.phone.split("/")[0].trim()}`}
                            style={{ color: "var(--red)", textDecoration: "none", fontWeight: 500 }}
                          >
                            📞 {r.phone}
                          </a>
                        </div>
                      ) : (
                        <div style={{ color: "var(--muted)" }}>📞 Phone unlisted</div>
                      )}
                      {r.email && (
                        <div>
                          <a
                            href={`mailto:${r.email}`}
                            title={r.email}
                            style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.75rem" }}
                          >
                            ✉️ {r.email.length > 22 ? `${r.email.slice(0, 20)}…` : r.email}
                          </a>
                        </div>
                      )}
                    </td>

                    {/* Sync Date */}
                    <td style={{ padding: "0.85rem 1rem", verticalAlign: "top", fontSize: "0.78rem", color: "var(--muted)" }}>
                      <div>{r.last_updated}</div>
                      <div style={{ fontSize: "0.72rem", color: "#9ca3af" }}>{r.district}</div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Disclaimer block mandated by eRaktKosh terms */}
      <div
        style={{
          marginTop: "1.5rem",
          padding: "0.85rem 1rem",
          backgroundColor: "var(--paper)",
          border: "1px solid var(--line)",
          borderRadius: "6px",
          fontSize: "0.78rem",
          color: "var(--muted)",
          lineHeight: 1.4
        }}
      >
        <strong>⚠️ Data Notice & Etiquette:</strong> Figures shown above are aggregate public figures fetched via automated
        sync from India's national blood-bank directory (eRaktKosh / C-DAC, MoHFW) for Bengaluru. In accordance with eRaktKosh
        guidelines, counts are indicative; donors and hospitals should telephone the blood center to confirm physical bag availability
        before dispatching emergency requests.
      </div>
    </section>
  );
}
