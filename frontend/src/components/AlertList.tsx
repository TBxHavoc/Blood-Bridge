import type { StatusClass } from "../lib/blood";

export interface AlertItem {
  cls: StatusClass;
  title: string;
  note?: string;
}

export function AlertList({ items }: { items: AlertItem[] }) {
  if (!items.length) {
    return (
      <ul className="list">
        <li className="empty">Nothing needs attention right now.</li>
      </ul>
    );
  }
  return (
    <ul className="list">
      {items.map((alert, i) => (
        <li key={`${alert.title}-${i}`} className={`alert ${alert.cls}`}>
          <span className="dot" />
          <div>
            <strong>{alert.title}</strong>
            {alert.note ? <small>{alert.note}</small> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
