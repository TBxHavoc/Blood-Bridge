import { WarningIcon } from "./Icons";

export function ExpTag({ expiring }: { expiring: { units: number; days: number } }) {
  const soon = expiring.days <= 2;
  return (
    <span className={`exp${soon ? " soon" : ""}`}>
      <WarningIcon />
      {expiring.units} expiring in {expiring.days} day{expiring.days === 1 ? "" : "s"}
    </span>
  );
}
