# Blood Bridge — frontend

React + TypeScript + Vite single-page app for the Blood Bridge demo. It ported the
`prototypes/` HTML 1:1 (same markup structure, class names, tokens and canvas
animation) into components, and talks to the real FastAPI backend in `../backend`.

## Run

Start the API first, then the app.

```bash
# terminal 1 — backend (from repo root)
cd backend
python -m venv .venv && .venv\Scripts\activate      # or: uv venv .venv
pip install -r requirements.txt
python -m app.seed.seed                             # synthetic data; needs DATABASE_URL
python -m uvicorn app.main:app --port 8000

# terminal 2 — frontend
cd frontend
npm install
npm run dev                                         # http://localhost:5173
```

Dev requests to `/api/*` are proxied by Vite to the backend, so there is no CORS
setup to touch. To point at another backend, set `VITE_BACKEND`:

```bash
set VITE_BACKEND=http://127.0.0.1:8000        # Windows PowerShell: $env:VITE_BACKEND="..."
```

## Scripts

| script              | what it does                          |
| ------------------- | ------------------------------------- |
| `npm run dev`       | Vite dev server on port 5173          |
| `npm run build`     | type-check (`tsc`) + production bundle |
| `npm run preview`   | serve the built `dist/`               |
| `npm run typecheck` | `tsc --noEmit` only                   |

## Signing in

No credentials are stored in this repo or shipped to the browser. The backend
reads a temporary admin login from `backend/.env` (git-ignored) as
`ADMIN_USERNAME` / `ADMIN_PASSWORD`, hashes it, and (re)creates that account at
startup — so a temp login always exists. Change the password there and restart
to rotate it. Roles: `hospital_user`, `bloodbank_user`, `admin`, `auditor`.

The synthetic demo accounts (`_admin`, `_auditor`, `hospital_h_001`,
`bank_bb_001`, …) share the `SEED_PASSWORD` from that same `.env`; they are not
advertised anywhere in the UI.

## Layout

```
src/
  main.tsx            entry: mounts <App/> inside <AuthProvider>
  App.tsx             splash → Login → Dashboard gate
  app/
    NavContext.tsx    view name, nav params, `go(view, params)`
    PageProps.ts      { token, user } props every page receives
  auth/AuthContext.tsx login/logout/me, token in localStorage (`bb.session`)
  lib/
    api.ts            envelope-unwrapping fetch (`{success,data,meta}` → data)
    types.ts          backend response shapes
    blood.ts          status/expiry/duration/relative-time helpers
    derive.ts         buildStock / buildBankSupply / inventorySummary
    session.ts        org & role labels, greeting, dateline
  components/         Sidebar, AlertList, BloodBox, Legend, ExpTag, Deco, Icons
  pages/              Login, Dashboard, Overview, Inventory, FindSupplies,
                      RequestBlood, Reports, Faq
  styles/             tokens.css, app.css, login.css  (ported verbatim)
```

## Notes / limits

- The look & feel is the source of truth in `prototypes/`; the CSS is copied
  verbatim, so keep original class names when editing markup.
- `login.css` is scoped under `.login-page` so its rules can't leak into the app.
- Two UI bits have no backend endpoint and are derived or omitted: the blood-bank
  directory (bank names come from forecasting rows) and the activity feed (built
  from alerts + depletion rows). Distance/ETA show only on a created request's
  `matches`.
- `backend/models/depletion_model.pkl` needs `lightgbm` to load; without it the
  forecasting service falls back to a deterministic simulation (fine for the demo).
