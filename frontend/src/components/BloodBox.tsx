import { useEffect, useRef, useState } from "react";

import type { StockItem } from "../lib/derive";
import { availabilityOf, duration, levelPct, status } from "../lib/blood";
import { ChevronDown } from "./Icons";
import { ExpTag } from "./ExpTag";

/** The blood box *is* the gauge: a translucent status wash wipes left→right and
 *  recedes as stock drops. Re-animates from 0 each time it opens. */
export function BloodBox({ item }: { item: StockItem }) {
  const [open, setOpen] = useState(false);
  const fillRef = useRef<HTMLSpanElement>(null);

  const [cls, label] =
    item.hours === null ? availabilityOf(item.units, true) : status(item.hours);
  const pct =
    item.hours === null ? Math.min(item.units / 300, 1) * 100 : levelPct(item.hours);
  const time = item.hours === null ? "—" : duration(item.hours);

  useEffect(() => {
    const el = fillRef.current;
    if (!el) return;
    el.style.width = "0%";
    const raf = requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        el.style.width = `${pct}%`;
      }),
    );
    return () => cancelAnimationFrame(raf);
  }, [pct, open]);

  return (
    <div className={`box ${cls}${open ? " open" : ""}`}>
      <button
        type="button"
        className="boxhead"
        aria-expanded={open}
        aria-label={`Blood type ${item.type} details`}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="fill" ref={fillRef} />
        <span className="sdot" />
        <span className="bt">{item.type}</span>
        <span className="btime">{time}</span>
        <ChevronDown />
      </button>
      <div className="boxbody" hidden={!open}>
        <div className="unitrow">
          <div className="units">
            {item.units}
            <small>units available</small>
          </div>
          <span className="pill">{label}</span>
        </div>
        {item.expiring ? <ExpTag expiring={item.expiring} /> : null}
        <div className="runout">
          <small>Estimated time until we run out</small>
          <b>{time}</b>
        </div>
      </div>
    </div>
  );
}
