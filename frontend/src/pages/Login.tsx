import { useEffect, useRef, useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/api";
import { BloodDropMark } from "../components/Icons";

interface FlowLine {
  ay: number;
  endY: number;
  c1: number;
  c2: number;
  amp: number;
  amp2: number;
  speed: number;
  phase: number;
  width: number;
  bright: boolean;
  dots: { u: number; v: number; r: number }[];
}

/** Left brand panel with the flowing-lines canvas animation (ported 1:1). */
export function Login() {
  const { login } = useAuth();
  const brandRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [userErr, setUserErr] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const brand = brandRef.current;
    const canvas = canvasRef.current;
    if (!brand || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ANCHORS = [0.25, 0.35, 0.45, 0.55, 0.65, 0.76, 0.86];
    const rnd = (a: number, b: number) => a + Math.random() * (b - a);

    const lines: FlowLine[] = [];
    ANCHORS.forEach((ay, i) => {
      const count = 2 + (i % 2);
      for (let k = 0; k < count; k++) {
        lines.push({
          ay,
          endY: rnd(0.05, 0.98),
          c1: rnd(-0.12, 0.12),
          c2: rnd(-0.3, 0.3),
          amp: rnd(0.02, 0.07),
          amp2: rnd(0.04, 0.12),
          speed: rnd(0.12, 0.3),
          phase: rnd(0, 6.28),
          width: rnd(0.8, 1.7),
          bright: k === 0,
          dots: Array.from({ length: Math.random() < 0.6 ? 1 : 2 }, () => ({
            u: Math.random(),
            v: rnd(0.012, 0.03),
            r: rnd(1.6, 3),
          })),
        });
      }
    });

    let W = 0;
    let H = 0;
    let dpr = 1;
    const resize = () => {
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = brand.clientWidth;
      H = brand.clientHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const ro = new ResizeObserver(resize);
    ro.observe(brand);
    resize();

    const bez = (p0: number, p1: number, p2: number, p3: number, u: number) => {
      const m = 1 - u;
      return m * m * m * p0 + 3 * m * m * u * p1 + 3 * m * u * u * p2 + u * u * u * p3;
    };

    let raf = 0;
    const frame = (ms: number) => {
      const t = ms / 1000;
      ctx.clearRect(0, 0, W, H);
      ctx.lineCap = "round";

      for (const L of lines) {
        const x0 = W + 12;
        const y0 = L.ay * H;
        const x1 = W * 0.68;
        const y1 = y0 + (L.c1 + Math.sin(t * L.speed + L.phase) * L.amp) * H;
        const x2 = W * 0.34;
        const y2 = L.endY * H + (L.c2 + Math.sin(t * L.speed * 0.8 + L.phase * 2) * L.amp2) * H;
        const x3 = -12;
        const y3 = L.endY * H + Math.sin(t * L.speed * 0.6 + L.phase) * L.amp2 * H;

        const g = ctx.createLinearGradient(0, 0, W, 0);
        g.addColorStop(0, "rgba(255,170,180,0)");
        g.addColorStop(0.55, `rgba(255,170,180,${L.bright ? 0.28 : 0.16})`);
        g.addColorStop(1, `rgba(255,214,218,${L.bright ? 0.95 : 0.55})`);
        ctx.strokeStyle = g;
        ctx.lineWidth = L.bright ? L.width + 0.4 : L.width;
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.bezierCurveTo(x1, y1, x2, y2, x3, y3);
        ctx.stroke();

        for (const d of L.dots) {
          if (!reduce) {
            d.u += d.v * 0.016;
            if (d.u > 1) d.u = 0;
          }
          const x = bez(x0, x1, x2, x3, d.u);
          const y = bez(y0, y1, y2, y3, d.u);
          const a = Math.sin(Math.PI * d.u);
          const glow = ctx.createRadialGradient(x, y, 0, x, y, d.r * 5);
          glow.addColorStop(0, `rgba(255,225,228,${0.9 * a})`);
          glow.addColorStop(1, "rgba(255,225,228,0)");
          ctx.fillStyle = glow;
          ctx.beginPath();
          ctx.arc(x, y, d.r * 5, 0, 6.2832);
          ctx.fill();
          ctx.fillStyle = `rgba(255,255,255,${a})`;
          ctx.beginPath();
          ctx.arc(x, y, d.r, 0, 6.2832);
          ctx.fill();
        }

        if (L.bright) {
          ctx.fillStyle = "rgba(255,230,232,.95)";
          ctx.beginPath();
          ctx.arc(W - 3, y0, 2.4, 0, 6.2832);
          ctx.fill();
        }
      }
      if (!reduce) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("");
    const nextUserErr = username.trim() ? "" : "Enter your username or email.";
    const nextPwErr = password ? "" : "Enter your password.";
    setUserErr(nextUserErr);
    setPwErr(nextPwErr);
    if (nextUserErr || nextPwErr) return;

    setBusy(true);
    try {
      await login(username.trim(), password);
      setStatus("Signed in.");
    } catch (err) {
      setStatus(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <section className="brand" ref={brandRef}>
        <canvas ref={canvasRef} aria-hidden="true" />
        <div className="logo">
          <BloodDropMark />
          BloodBridge
        </div>
        <div className="pitch">
          <h2>Every unit, accounted for.</h2>
          <p>
            A centralized platform to manage blood stock, maintain records, and simplify
            blood bank operations.
          </p>
        </div>
      </section>

      <main className="panel">
        <div className="box">
          <h1>Welcome back</h1>
          <p className="sub">Sign in to manage your blood bank's inventory.</p>

          <form onSubmit={onSubmit} noValidate>
            <div className="field">
              <label htmlFor="user">Username or email</label>
              <input
                id="user"
                type="text"
                autoComplete="username"
                required
                value={username}
                aria-invalid={userErr ? "true" : "false"}
                onChange={(e) => setUsername(e.target.value)}
              />
              <p className="err" role="alert">
                {userErr}
              </p>
            </div>
            <div className="field">
              <label htmlFor="pw">Password</label>
              <input
                id="pw"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                aria-invalid={pwErr ? "true" : "false"}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="err" role="alert">
                {pwErr}
              </p>
            </div>
            <a className="forgot" href="#">
              Forgot password?
            </a>
            <button className="submit" type="submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <p className="status" aria-live="polite">
              {status}
            </p>
          </form>

          <p className="notice">
            For authorized blood bank staff only. Activity on this system may be logged.
          </p>
        </div>
      </main>
    </div>
  );
}
