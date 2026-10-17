import { useEffect, useRef } from "react";

/**
 * Ambient "inside a blood vessel" animation for the sidebar.
 *
 * Four components drift bottom-to-top: red blood cells (biconcave discs),
 * white blood cells (irregular pale blobs with purple nuclei), platelets
 * (small angular fragments) and plasma (tiny motes plus a slow light band).
 *
 * Cells live in one pool and are recycled — re-randomised and moved back to
 * the bottom — once they clear the top edge, so the population never drains.
 * A per-cell `z` (depth) drives size, speed, alpha and horizontal drift, and
 * the pool is painted far-to-near, which sells the sense of volume.
 *
 * Purely decorative: aria-hidden, pointer-events off, and it relies on `.side`
 * being a stacking context so it sits under the nav (see DECISIONS.md).
 */

const TAU = Math.PI * 2;
const rnd = (a: number, b: number) => a + Math.random() * (b - a);

type Kind = "rbc" | "wbc" | "platelet" | "mote";

interface Cell {
  kind: Kind;
  baseX: number; // sway pivots around this
  x: number;
  y: number;
  z: number; // 0 = far, 1 = near
  r: number;
  vy: number; // upward, px/s
  driftX: number; // slow horizontal current, px/s
  swayAmp: number;
  swayPhase: number;
  swaySpeed: number;
  rot: number;
  spin: number; // rad/s
  alpha: number;
  shape: number[]; // per-vertex radius multipliers (wbc contour / platelet polygon)
  nuclei: { dx: number; dy: number; r: number }[]; // wbc only
}

/** How many of each to keep alive; randomised within the range on init. */
const COUNT: Record<Kind, [number, number]> = {
  rbc: [13, 19],
  wbc: [3, 4],
  platelet: [16, 24],
  mote: [26, 40],
};

const SIZE: Record<Kind, [number, number]> = {
  rbc: [6.5, 13],
  wbc: [15, 23],
  platelet: [1.5, 3.1],
  mote: [0.5, 1.4],
};

const SPEED: Record<Kind, [number, number]> = {
  rbc: [11, 27],
  wbc: [6, 15],
  platelet: [15, 33],
  mote: [9, 26],
};

const ALPHA: Record<Kind, [number, number]> = {
  rbc: [0.42, 0.78],
  wbc: [0.5, 0.78],
  platelet: [0.4, 0.8],
  mote: [0.12, 0.3],
};

const ring = (n: number, lo: number, hi: number) =>
  Array.from({ length: n }, () => rnd(lo, hi));

/** Smooth closed contour through jittered radii — the WBC's irregular edge. */
function traceBlob(ctx: CanvasRenderingContext2D, c: Cell) {
  const n = c.shape.length;
  const pts: [number, number][] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU;
    const rr = c.r * c.shape[i];
    pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
  }
  const mid = (i: number, j: number): [number, number] => [
    (pts[i][0] + pts[j][0]) / 2,
    (pts[i][1] + pts[j][1]) / 2,
  ];
  const start = mid(0, n - 1);
  ctx.moveTo(start[0], start[1]);
  for (let i = 0; i < n; i++) {
    const m = mid(i, (i + 1) % n);
    ctx.quadraticCurveTo(pts[i][0], pts[i][1], m[0], m[1]);
  }
  ctx.closePath();
}

/** Biconcave disc: dimpled dark centre, brighter ring, specular highlight. */
function drawRbc(ctx: CanvasRenderingContext2D, c: Cell) {
  const { r, alpha } = c;
  ctx.save();
  ctx.translate(c.x, c.y);
  ctx.rotate(c.rot); // carries the highlight round with it

  const g = ctx.createRadialGradient(0, 0, r * 0.12, 0, 0, r);
  g.addColorStop(0, `rgba(108, 15, 25, ${alpha})`);
  g.addColorStop(0.44, `rgba(196, 40, 52, ${alpha})`);
  g.addColorStop(0.8, `rgba(216, 60, 70, ${alpha * 0.95})`);
  g.addColorStop(1, `rgba(138, 23, 33, ${alpha})`);
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, TAU);
  ctx.fill();

  ctx.strokeStyle = `rgba(255, 160, 168, ${alpha * 0.18})`;
  ctx.lineWidth = Math.max(0.6, r * 0.06);
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.98, 0, TAU);
  ctx.stroke();

  const hx = -r * 0.34;
  const hy = -r * 0.38;
  const hg = ctx.createRadialGradient(hx, hy, 0, hx, hy, r * 0.62);
  hg.addColorStop(0, `rgba(255, 226, 228, ${alpha * 0.34})`);
  hg.addColorStop(1, "rgba(255, 226, 228, 0)");
  ctx.fillStyle = hg;
  ctx.beginPath();
  ctx.arc(hx, hy, r * 0.62, 0, TAU);
  ctx.fill();
  ctx.restore();
}

/** Pale translucent blob with one or two denser purple nuclei. */
function drawWbc(ctx: CanvasRenderingContext2D, c: Cell) {
  const { r, alpha } = c;
  ctx.save();
  ctx.translate(c.x, c.y);
  ctx.rotate(c.rot);

  ctx.beginPath();
  traceBlob(ctx, c);
  const g = ctx.createRadialGradient(-r * 0.2, -r * 0.2, r * 0.1, 0, 0, r * 1.1);
  g.addColorStop(0, `rgba(255, 244, 248, ${alpha})`);
  g.addColorStop(0.68, `rgba(238, 214, 230, ${alpha * 0.8})`);
  g.addColorStop(1, `rgba(204, 170, 200, ${alpha * 0.5})`);
  ctx.fillStyle = g;
  ctx.fill();
  ctx.strokeStyle = `rgba(255, 240, 246, ${alpha * 0.32})`;
  ctx.lineWidth = Math.max(0.6, r * 0.05);
  ctx.stroke();

  for (const n of c.nuclei) {
    for (const [scale, tint] of [
      [1, 0.6],
      [0.58, 0.5],
    ] as const) {
      ctx.beginPath();
      ctx.ellipse(n.dx, n.dy, n.r * scale, n.r * scale * 0.78, c.rot * 1.7, 0, TAU);
      ctx.fillStyle = `rgba(${scale === 1 ? "126, 88, 168" : "94, 62, 138"}, ${alpha * tint})`;
      ctx.fill();
    }
  }
  ctx.restore();
}

/** Small angular fragment — a jittered polygon, not a circle. */
function drawPlatelet(ctx: CanvasRenderingContext2D, c: Cell) {
  const { r, alpha } = c;
  ctx.save();
  ctx.translate(c.x, c.y);
  ctx.rotate(c.rot);

  const n = c.shape.length;
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU;
    const rr = r * c.shape[i];
    const px = Math.cos(a) * rr;
    const py = Math.sin(a) * rr;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();

  const g = ctx.createLinearGradient(-r, -r, r, r);
  g.addColorStop(0, `rgba(216, 142, 198, ${alpha})`);
  g.addColorStop(1, `rgba(146, 96, 176, ${alpha})`);
  ctx.fillStyle = g;
  ctx.fill();
  ctx.restore();
}

function drawMote(ctx: CanvasRenderingContext2D, c: Cell) {
  ctx.beginPath();
  ctx.arc(c.x, c.y, c.r, 0, TAU);
  ctx.fillStyle = `rgba(255, 208, 214, ${c.alpha})`;
  ctx.fill();
}

export function Bloodstream() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    /** Build a cell. `fresh` scatters it over the panel; otherwise it enters
     *  from just below the bottom edge (the recycle path). */
    const spawn = (kind: Kind, fresh: boolean): Cell => {
      const z = kind === "mote" ? rnd(0.08, 0.55) : rnd(0.2, 1);
      const zf = 0.55 + 0.45 * z;
      const r = rnd(...SIZE[kind]) * zf;
      const c: Cell = {
        kind,
        baseX: rnd(-30, w + 30),
        x: 0,
        y: fresh ? rnd(-r, h + r) : h + r * 2 + rnd(0, 90),
        z,
        r,
        vy: rnd(...SPEED[kind]) * zf,
        driftX: rnd(-7, 7) * (0.5 + z),
        swayAmp: rnd(3, 13) * (0.6 + z),
        swayPhase: rnd(0, TAU),
        swaySpeed: rnd(0.25, 0.8),
        rot: rnd(0, TAU),
        spin: rnd(-0.5, 0.5) * (0.4 + z),
        alpha: rnd(...ALPHA[kind]) * (0.55 + 0.45 * z),
        shape:
          kind === "wbc"
            ? ring(10, 0.76, 1.16)
            : kind === "platelet"
              ? ring(6, 0.55, 1.25)
              : [],
        nuclei: [],
      };
      if (kind === "wbc") {
        const count = Math.random() < 0.45 ? 2 : 1;
        for (let i = 0; i < count; i++) {
          c.nuclei.push({
            dx: rnd(-r * 0.34, r * 0.34),
            dy: rnd(-r * 0.34, r * 0.34),
            r: rnd(r * 0.3, r * 0.46),
          });
        }
      }
      c.x = c.baseX + Math.sin(c.swayPhase) * c.swayAmp;
      return c;
    };

    const cells: Cell[] = [];
    (Object.keys(COUNT) as Kind[]).forEach((kind) => {
      const [lo, hi] = COUNT[kind];
      const n = Math.round(rnd(lo, hi));
      for (let i = 0; i < n; i++) cells.push(spawn(kind, true));
    });

    /** Faint band of plasma drifting upward through the whole panel. */
    const drawPlasma = (t: number) => {
      const bandY = h + 300 - ((t * 26) % (h + 600));
      const g = ctx.createLinearGradient(0, bandY - 300, 0, bandY + 300);
      g.addColorStop(0, "rgba(255, 170, 180, 0)");
      g.addColorStop(0.5, "rgba(255, 170, 180, 0.04)");
      g.addColorStop(1, "rgba(255, 170, 180, 0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    };

    const render = (dt: number, t: number) => {
      ctx.clearRect(0, 0, w, h);
      drawPlasma(t);

      for (const c of cells) {
        c.y -= c.vy * dt;
        c.rot += c.spin * dt;
        c.swayPhase += c.swaySpeed * dt;
        c.baseX += c.driftX * dt;
        if (c.baseX < -50) c.baseX = w + 50;
        else if (c.baseX > w + 50) c.baseX = -50;
        c.x = c.baseX + Math.sin(c.swayPhase) * c.swayAmp;

        if (c.y + c.r * 1.8 < 0) Object.assign(c, spawn(c.kind, false));
      }

      // far-to-near so nearer cells overlap the ones behind them
      for (const c of [...cells].sort((a, b) => a.z - b.z)) {
        if (c.kind === "rbc") drawRbc(ctx, c);
        else if (c.kind === "wbc") drawWbc(ctx, c);
        else if (c.kind === "platelet") drawPlatelet(ctx, c);
        else drawMote(ctx, c);
      }
    };

    if (still) {
      render(0, 0);
      return () => ro.disconnect();
    }

    let prev = 0;
    let t = 0;
    let raf = 0;
    const tick = (now: number) => {
      // clamp so a backgrounded tab doesn't jump the flow on return
      const dt = prev ? Math.min((now - prev) / 1000, 0.05) : 0;
      prev = now;
      t += dt;
      render(dt, t);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={ref} className="blood" aria-hidden="true" />;
}
