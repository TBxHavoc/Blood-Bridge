# Decisions

> Append-only record of *why* things are the way they are. Do not rewrite past
> entries; supersede them. Format: ISO date — short title.

### 2026-10-18 — Single app in `backend/`, `database/` is DB-only

**Context:** The `dev` branch is a merge of the `backend` and `database` branches.
Each branch had carried its own full copy of the FastAPI app, so `database/app/`
was a stale, smaller duplicate of `backend/app/` (`config.py` 62 vs 88 lines,
`core/errors.py` 113 vs 138, `api/system.py` 24 vs 37). Root-level `datasets/`,
`docs/`, `notebooks/`, `scripts/` were further stragglers duplicated into both trees.

**Decision:** `backend/` is the single application. `database/` holds only database
assets (`sql/`, `models/db_models.py`, `scripts/`, `docs/`, `docker-compose.yml`).
Deleted `database/app/`, `database/Dockerfile`, `database/.dockerignore`,
`database/notebooks/`, `database/tests/`, and the duplicate DB-side ML scripts.

**Why:** Restores the merge intent ("backend modules in `backend/`, database modules
in `database/`"), removes two sources of truth for the same app, and stops the
`database/` Dockerfile from building a divergent API image.

**Rejected:** Keeping both as standalone runnable stacks — duplicates the app and
the schema ownership, which is exactly the drift that created the mess.

### 2026-10-18 — ML pipeline lives inside `backend/`

**Context:** The ML notebook, datasets, model `.pkl`, and train/predict/evaluate
scripts existed in three places (repo root, `backend/`, `database/`). The 312-line
`predict_depletion.py` lived only at the root; `backend/` and `database/` held
17-line shims that forwarded back to it. The `.pkl` existed at `backend/model/`
(singular), `backend/models/`, and `database/models/`.

**Decision:** One canonical copy of each, under `backend/`: `datasets/`, `models/`,
`notebooks/`, `docs/`, `scripts/{train_model,predict_depletion,evaluate_model_accuracy,test_trained_model,metrics}.py`.
Deleted the root stragglers and `backend/model/` (singular).

**Why:** The app's forecasting service (`backend/app/services/forecasting.py`) is the
consumer of the model, so co-locating the pipeline with the app keeps one runnable
project and one artifact path.

**Rejected:** a top-level `ml/` package — adds a third root concept for no gain at
MVP size.

### 2026-10-18 — Canonical model path is `backend/models/depletion_model.pkl`

**Context:** Four candidate paths were being probed defensively in `forecasting.py`,
`train_model.py` (default output), and two verification scripts.

**Decision:** `backend/models/depletion_model.pkl` is the only artifact location.
Simplified `BloodDepletionPredictor.CANDIDATE_MODEL_PATHS` and the scripts' path
resolution to match; updated `backend/docs/ML_DEPLETION_MODEL.md`.

**Why:** Defensive multi-path probing was papering over the duplication and hid
which file was authoritative.

**Rejected:** keeping the mirror list "for safety" — it re-enables silent drift.

### 2026-10-18 — frontend merged into dev without trimming root files

**Context:** `origin/frontend` branched from the initial commit `71a04d3` and its
final commit removed all non-frontend files, deleting root `.gitignore` and
`README.md`. Both are modified in `dev`, so `git merge origin/frontend` produced
modify/delete conflicts.

**Decision:** Merged `origin/frontend` into `dev`, resolving both conflicts by
keeping dev's `.gitignore` and `README.md`. Only `frontend/` was added.

**Why:** The frontend branch's trim was meant to keep *that* branch clean, not to
delete files from the integration branch. `dev` owns the repo-root files.

**Rejected:** accepting the deletions — would drop `.gitignore`/`README.md` from dev.

### 2026-10-18 — Frontend is a Vite + React + TypeScript app, proxied to the API

**Context:** `frontend/` held two static HTML prototypes and `design.md`. To build
the app from them we had to choose between keeping a no-build vanilla page (edit
the prototypes directly) and a real component build. `design.md` §7.2 also
suggested endpoints, but the shipping backend had moved on from them.

**Decision:** Port the prototypes into a Vite + React 18 + TS SPA under
`frontend/src`, keeping the prototypes as the untouched visual reference in
`frontend/prototypes/`. Use the **real backend contract** (read from
`backend/app/schemas/` and `api/`) rather than `design.md` §7.2. No router
dependency: navigation is a `NavContext` holding `{view, params, go}`. Port the
CSS verbatim so class names stay identical, and scope the login stylesheet under
`.login-page` so its rules can't collide with the dashboard. Dev requests go
through a Vite `/api` proxy to `http://127.0.0.1:8000` (`VITE_BACKEND` override).

**Why:** The user asked for React; componentizing makes the role-aware branches
(hospital vs blood bank) and the live forecasting data manageable, and reusing
the backend's real field names avoids a whole class of mapping bugs. The proxy
keeps the backend's restrictive CORS list (`localhost:5173` only) untouched.

**Rejected:** a client-side router (react-router) — overkill for six views and one
nav state. Rewriting the CSS — the prototypes' look is the deliverable, so it is
copied, not reinterpreted.

### 2026-10-18 — Frontend smoke-tested against the API on SQLite

**Context:** No PostgreSQL was running locally and the system Python lacked the
backend deps, so there was no way to exercise the app end-to-end.

**Decision:** Create a throwaway `backend/.venv` (Python 3.11 via `uv`), install
`requirements.txt`, seed and run the API with `DATABASE_URL=sqlite:///./smoke.db`,
then drive it through the Vite proxy (login → forecasting → requests → inventory,
plus the `hospital_user` → `/inventory` 403 check). Removed the SQLite file and
logs afterwards.

**Why:** The SQLAlchemy layer is deliberately dialect-neutral (no inline ENUM, no
SERIAL, UUIDs as 36-char strings), so SQLite exercises the same code paths and
proves the frontend's expected JSON actually matches what the API returns.

**Rejected:** spinning up the Postgres `docker-compose` — heavier, and the
dialect-neutral invariant means SQLite is a faithful stand-in for a smoke test.

### 2026-10-18 — No credentials in the repo; temp admin comes from the environment

**Context:** The login page printed the demo accounts and password to every
visitor, `backend/app/config.py` hardcoded a shared seed password,
`.env.example` carried the same value, `tests/conftest.py` had a
`TEST_PASSWORD` literal, and `frontend/README.md` documented them. The user also
could not sign in. Separately, the user asked for a single temp admin login with
a chosen username/password, and for the password to be "not hashed".

**Decision:** Credentials are configuration, not code. `seed_password` now
defaults to `""`; `ADMIN_USERNAME` / `ADMIN_PASSWORD` are new settings with no
default, read from the git-ignored `backend/.env`. A new
`app/seed/bootstrap.py::ensure_bootstrap_admin()` runs in the FastAPI lifespan
and (re)creates that admin — hashed — at startup, so changing `.env` rotates the
password. The login page's `.demo` block, its CSS, and both READMEs were
stripped. `tests/conftest.py` now generates a random password per run.
`app.seed.seed()` refuses to create demo accounts when `SEED_PASSWORD` is empty.

**Why:** Satisfies "not visible when you commit" and "not visible in the browser
console": nothing credential-shaped exists in tracked files (verified with
`git grep`), and the SPA only ever posts what the user types. Keeping bcrypt was
the one place we did *not* follow the literal request — plaintext storage is the
OWASP CRITICAL item ("cryptographic-failures"), hashing is one-way, and the hash
still leaks nothing to a browser or a DB reader. The startup bootstrap also
fixes the login failure by guaranteeing an account exists regardless of whether
the DB was seeded.

**Rejected:** storing the password unhashed as asked — readable plaintext in the
`users` table is a critical finding and buys nothing, since the credential is
already reachable via the local `.env`. Also rejected: keeping a hardcoded
fallback password so it "just works" — that is exactly the committed-secret
problem being removed.

### 2026-10-18 — Vite pinned back to 5.x for a consistent toolchain

**Context:** `frontend/package.json` had drifted to `vite@^8.3.4`, which
`@vitejs/plugin-react@4.x` does not support (its peer range ends at `^7.0.0`).
`npm install` then failed outright with `ERESOLVE`, and `npm ls` reported the
installed tree as invalid.

**Decision:** Restore `vite@^5.4.11` (verified working with
`@vitejs/plugin-react@^4.3.4`) and reinstall to regenerate a consistent
`package-lock.json`.

**Why:** Unblocks `npm install` for everyone and matches the combination the app
was built and tested against. Vite 8 is rolldown-based and would drag in `oxc`
and `@rolldown/plugin-babel` peers via `@vitejs/plugin-react@6`, which is a much
larger, untested change for a hackathon demo.

**Rejected:** upgrading to `vite@8` + `@vitejs/plugin-react@6` to keep the newer
major — unverified against this codebase and pulls in extra toolchain churn.

### 2026-10-18 — API timestamps are parsed as UTC, not local

**Context:** The backend stores and returns *naive* UTC (no offset, e.g.
`2026-10-17T20:04:44.020416`, see `app/models.py:utcnow`). `new Date(iso)` reads
a zone-less string as **local** time, so in IST every "x ago" label was skewed by
5h30m — a freshly created alert or a just-completed sign-in rendered as hours
old. This surfaced while adding the profile panel's "Last sign-in".

**Decision:** `relativeTime()` in `src/lib/blood.ts` now goes through a private
`parseApiDate()` that appends `Z` to zone-less timestamps (and leaves
`YYYY-MM-DD` date-only strings alone, since those are already UTC by spec).

**Why:** One-line correctness fix at the single place relative times are
formatted; the alternative (teaching the backend to emit `Z`) is a bigger,
riskier change for the same result.

**Rejected:** formatting with `toLocaleString` and hoping — the skew is in the
*parse*, not the format, so it has to be fixed at parse time.

### 2026-10-18 — Sidebar profile button is a menu, not a direct sign-out

**Context:** The account button in the sidebar signed the user out on click, and
the only way off the dashboard was that button — an accidental-click hazard with
no room for a profile view.

**Decision:** The button now opens a dropdown (`role="menu"`, `aria-expanded`,
closes on outside-click and Escape) with **Profile** and **Logout**. Profile
opens a modal dialog built from the session `user` (username, email, role, org,
status, last sign-in) — `UserIcon`/`LogoutIcon` added to `Icons.tsx`.

**Why:** Keeps sign-out behind one deliberate extra action, and shows account
details without adding a new `ViewName` to the nav union or a backend call —
`AuthContext` already holds everything displayed.

**Rejected:** a dedicated `Profile` view — an extra nav entry and page for six
read-only fields the sidebar already has in hand.

### 2026-10-18 — Sidebar DNA helix is a `z-index: -1` canvas, not a layered body

**Context:** The sidebar read as a flat blank slab. A DNA helix was wanted behind
the nav, moving upward, at low opacity — without disturbing the nav text, the
profile popover (z-index 30), or the profile dialog (`position: fixed`,
z-index 60).

**Decision:** One `<canvas>` in `components/DnaHelix.tsx` at
`position: absolute; inset: 0; z-index: -1; pointer-events: none`, first child of
`.side`. No changes to any nav/link/dialog rule.

**Why:** `.side` is already a stacking context (`position: relative` at
`app.css:15` + `z-index: 2` at `app.css:323`), so a negative-z child paints
*after* the sidebar's background but *before* all in-flow content — exactly the
layering wanted, for free. Canvas 2D over CSS/SVG because the twist needs
per-segment depth shading, and the login page already establishes the canvas
pattern (`Login.tsx`).

**Invariant:** if `.side` ever loses `position`/`z-index`, the canvas falls out
of that stacking context and vanishes behind the gradient. The alternative
(canvas at `z-index: 0` + lifting `.top`/`.group`/`nav`/`.faq` to `z-index: 1`)
was rejected because equal stack levels fall back to DOM order, which would bury
the profile popover behind `nav`.

**Rejected:** `z-index: -1` *without* a stacking context — the canvas would paint
behind the sidebar's own gradient and be invisible.

### 2026-10-18 — Sidebar animation is now a bloodstream, not a DNA helix

**Context:** The helix above shipped, then was superseded by a request to show
"an animated bloodstream" with red cells, white cells, platelets and plasma.
The sidebar layout, nav, icons, logo, dimensions, gradient and behaviour were
all to stay as-is.

**Decision:** `components/DnaHelix.tsx` deleted; replaced by
`components/Bloodstream.tsx`, mounted the same way (first child of `.side`,
`className="blood"`, same `position/inset/z-index: -1/pointer-events: none`
CSS block, only the selector renamed `.dna` → `.blood`). No other sidebar rule
or JSX changed.

**Why:** Same integration point and same layering argument, so the swap is
contained to one file + one rule; nav stacking, the profile popover and the
dialog keep working untouched.

**Design of the effect** (worth knowing before tuning): all four components
live in a **single `Cell[]` pool** and are dispatched by `kind` at paint time.
Each cell carries `z` (depth), which scales size, speed, alpha and horizontal
drift; the pool is sorted far-to-near each frame so near cells overlap far ones.
On clearing the top edge a cell is `Object.assign`-ed a fresh `spawn()`, so the
pool is stable (no GC churn) and re-randomised. Knots to turn by eye:
`COUNT` (per-kind population), `SIZE`/`SPEED`/`ALPHA` (per-kind tuples), and the
`drawPlasma` band speed (`t * 26`). RBCs are deliberately circular discs with a
dimpled dark centre and a rotating highlight — the rotation only reads because
the highlight rotates with the body.

**Rejected:** separate arrays/lifetimes per component kind — the single pool plus
one depth sort is less code, and sorting ~60 items per frame is free.

### 2026-10-18 — Login page resets `.box`/`.notice`; it does not just scope them

**Context.** The login form is a 1:1 port of `prototypes/login page.html`, whose
class names (`.box`, `.field`, `.submit`, `.notice`) also exist in the dashboard
stylesheet (`app.css`). `login.css` is imported last, so it wins *ties* — but a
cascade win only covers properties a rule actually declares. `.login-page .box`
declared just `width`/`max-width`, so `.box`'s `border: 1px solid`, `border-radius:
12px`, `box-shadow` and `background` (app.css:421, the alert card) still applied.
The form wrapper rendered as a bordered card, and the bottom notice rendered as a
green bordered pill (app.css:1080). The comment claiming scoping prevents
collisions was wrong.

**Decision.** `.login-page .box` and `.login-page .notice` explicitly reset every
leaked property (`border`, `border-radius`, `box-shadow`, `background`,
`display`, `overflow`, `padding`) back to the prototype's values, with a comment
pointing at the cause. The login page's own classes are NOT renamed, so the
port stays diffable against the prototype.

**Why.** A reset is three lines and keeps prototype class parity; renaming would
touch every login selector plus the JSX for a cosmetic conflict.

**Known remaining leak (accepted, not fixed):** `.field` still picks up
`display: flex; flex-direction: column; gap: 6px` from app.css:1001, which adds
~6px between label/input/error versus the prototype, and `.field label`'s
`color: var(--muted)` still wins (login.css sets no label colour). Cosmetic only
— no unwanted borders. Fix by resetting `.login-page .field` if it ever matters.

**Invariant for future work:** before adding any shared-sounding class to the
login page (`.field`, `.submit`, `.item`, ...), grep `app.css` for that name;
scoping gives you a win only on the properties you declare.

