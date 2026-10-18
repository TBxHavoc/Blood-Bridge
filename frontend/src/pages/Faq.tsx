const FAQS: { q: string; a: string }[] = [
  {
    q: "What does the colour on each blood type mean?",
    a: "It is the estimated time until that type runs out, based on current stock and the average daily usage: red is under 1 day, orange 1–3 days, amber 3–7 days, green over 7 days.",
  },
  {
    q: "How is the time-to-run-out calculated?",
    a: "Hours remaining = units available ÷ average units used per day × 24. The forecast comes from the depletion model, driven by historical request volume.",
  },
  {
    q: "How are blood banks chosen for a request?",
    a: "When you submit a request the matching engine ranks partner banks by distance, estimated arrival time and availability of a compatible batch, then returns the ranked list.",
  },
  {
    q: "Why can't I see batch inventory?",
    a: "Raw inventory is scoped to the blood bank that owns it (and administrators). Hospitals see network-wide supply instead.",
  },
  {
    q: "Can I add or adjust stock?",
    a: "Blood-bank accounts can add stock directly from the Inventory page. Hospitals request units rather than holding them.",
  },
];

export function Faq() {
  return (
    <section id="faq">
      <h1>FAQ</h1>
      <p className="lead">Answers to common questions about the dashboard.</p>

      <div className="layout" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
        <div className="left">
          <div className="card">
            <h2>Frequently asked</h2>
            <div className="body">
              <ul className="list">
                {FAQS.map((item) => (
                  <li key={item.q}>
                    <span className="dot" />
                    <div>
                      <strong>{item.q}</strong>
                      <small>{item.a}</small>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
