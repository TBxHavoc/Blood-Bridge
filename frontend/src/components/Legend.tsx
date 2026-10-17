export function Legend({ source }: { source?: string }) {
  return (
    <div className="legend" aria-label="Colour key for time until we run out">
      <span>
        <i style={{ background: "var(--crit)" }} />
        Under 1 day
      </span>
      <span>
        <i style={{ background: "var(--low)" }} />
        1 to 3 days
      </span>
      <span>
        <i style={{ background: "var(--warn)" }} />
        3 to 7 days
      </span>
      <span>
        <i style={{ background: "var(--good)" }} />
        Over 7 days
      </span>
      {source ? <em>{source}</em> : null}
    </div>
  );
}
