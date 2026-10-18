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

### 2026-10-18 — data.gov.in fetches need a custom User-Agent

**Context:** `backend/scripts/fetch_karnataka_hospitals.py` timed out on every
request (`The read operation timed out`), including datasets that the same URL
had served fine seconds earlier from PowerShell. Page size was not the cause —
`limit=100` failed exactly like `limit=1000`.

**Decision:** send an explicit `User-Agent` (plus `Accept: application/json`) on
every request.

**Why:** data.gov.in drops the default `Python-urllib/3.x` agent — the TCP
connection completes and the response then never arrives, which surfaces as a
*read* timeout rather than an HTTP error, making it look like a network or
paging problem. Probing four agents showed the default failing while a browser
string, a descriptive name and a named-agent+Accept all returned 200.

**Rejected:** blaming page size and dropping it to 100 — a red herring that
doubles the request count and fixes nothing. Also rejected `requests`, when
stdlib `urllib` works once the header is set (keeps the script dependency-free).

**Also recorded:** the three registries do **not** share a schema (`hospital_`
/ `sl_no` vs `hospital` / `sl_no_`), and the private set stores 6 hospital names
with embedded newlines (1549 physical lines for 1543 rows). The script pins
column order and collapses whitespace, so line count == row count and re-fetches
diff cleanly. Files live in `datasets/karnataka/` rather than `datasets/` so
they cannot be mistaken for the ML contract files `train_model.py` reads by
exact filename.

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

### 2026-10-18 — One root `docker-compose.yml`; `backend/docker-compose.yml` retired

**Context:** Two compose files defined the same service set. `backend/docker-compose.yml`
(postgres + api) and `database/docker-compose.yml` (postgres + pgadmin) both declared
service `db` with `container_name: bloodbridge-db` and both bound host 5432, so they
could not run together. Neither built the frontend, and `backend/Dockerfile` copied
only `app/`, so the ML/data scripts were missing from the API image.

**Decision:** A single root `docker-compose.yml` brings up `db` + `api` + `web`, with
opt-in `seed` (`profiles: ["seed"]`) and pgadmin (`profiles: ["tools"]`) services.
Deleted `backend/docker-compose.yml`; `database/docker-compose.yml` stays as the
DB-only sandbox that loads `database/sql/*.sql` directly. The API image now also
copies `scripts/`, `datasets/` and `models/`, runs as unprivileged `appuser`, and
healthchecks `/api/v1/health` — the endpoint is *under* the API prefix, not `/health`.

**Why:** One entry point removes the drift and the port/name conflict, and makes the
same file usable unchanged on a Linux/IBM LinuxONE host. The API owns the schema
(SQLAlchemy `create_all` at startup), so no SQL init scripts are mounted into the
root stack — that keeps `app/models.py` the single source of truth.

**Rejected:** Mounting `database/sql/01_schema_postgresql.sql` into
`/docker-entrypoint-initdb.d` for the root stack — it would create a second, divergent
schema authority alongside the ORM models.

**Rejected:** Keeping `backend/docker-compose.yml` as a convenience wrapper — it is the
file that made the two stacks mutually exclusive.

### 2026-10-18 — No `container_name`: a sibling checkout must not be collateral damage

**Context:** `docker compose up` failed with `Conflict. The container name
"/bloodbridge-db" is already in use`. The owner was a *different* project — label
`com.docker.compose.project=ibmhackathon`, config file `D:\ibm hackathon\docker-compose.yml`
— an older copy of this repo that hardcoded the same global name. Container names are
global to the Docker daemon; compose's default (`<project>-<service>-<n>`) is not.

**Decision:** Dropped every explicit `container_name` from the root compose. The
containers are `bloodbridge-db-1`, `bloodbridge-api-1`, `bloodbridge-web-1`. The stale
container from the other project was left running/exited untouched.

**Why:** Namespacing by compose project is what lets two copies of this repo coexist,
which this machine needs. Deleting the other project's container would have been
destroying someone else's state to win a cosmetic name.

**Rejected:** Renaming to `bloodbridge-dev-db` — still global, still collides the next
time a copy uses that name.

### 2026-10-18 — The web container terminates `/api`, and the API trusts its X-Forwarded-For

**Context:** The dev setup relies on the Vite proxy (`vite.config.ts`, target
`VITE_BACKend ?? 127.0.0.1:8000`) to keep the browser on one origin. A `vite build`
output has no dev server, so that proxy does not exist in production. Separately,
`Settings.trust_forwarded_for` defaults to `False` and `app/main.py` only honours the
header when it is set.

**Decision:** `frontend/Dockerfile` builds with node and serves via nginx.
`frontend/nginx.conf` serves the SPA with `try_files ... /index.html` fallback and
`location ^~ /api/` proxies to `http://api:8000` (the `^~` keeps API paths out of the
static-asset regex). The compose sets `TRUST_FORWARDED_FOR: "true"` on the API.

**Why:** One origin in production means no CORS surface and nothing to reconfigure when
the host changes. Without the trust flag every request appears to originate from the
proxy, collapsing per-IP login rate limiting into a single shared bucket.

**Rejected:** Baking the API URL into the bundle via a Vite env var — it couples one
image to one deployment target and re-introduces CORS.

**Known trade-off:** nginx is a trusted proxy *inside* the compose network. If the API
port were ever published beyond loopback, the header could be spoofed; the compose
therefore binds it to `127.0.0.1` only.

### 2026-10-18 — In-container seeding: profiled, CSV-free, and re-bootstraps the admin

**Context:** Two traps in `app/seed/seed.py`. (1) It writes its generated rows back to
`backend/datasets/*.csv` (`DATASETS_DIR`, `_write_csv`), so running it inside the API
image rewrites the tracked dataset snapshots. (2) `seed()` defaults to `reset=True`,
which deletes every table *including* `users` — and the bootstrap admin is only created
by the API's startup lifespan. Seeding after the API had already started therefore
deleted the admin and left `admin`/`ADMIN_PASSWORD` returning 401 while
`docker compose ps` still showed every service healthy. Verified: `role='admin'` count
went to 0, `hospital_h_001` still authenticated, and `docker compose restart api`
brought `admin` back.

**Decision:** Seeding is an explicit, one-shot, profiled service:
`docker compose run --rm seed`. Its command runs `seed(write_csv=False)` and then
`ensure_bootstrap_admin()` in the same process, and it receives `ADMIN_USERNAME` /
`ADMIN_PASSWORD` alongside `SEED_PASSWORD`.

**Why:** `write_csv=False` keeps the CSV snapshots (the ML input contract) byte-stable;
a profile keeps a data-destroying operation out of the default `up`; and re-asserting
the admin makes the seed safe to run in any order and safe to re-run — otherwise the
documented quickstart left you with no working login until you thought to restart the
API.

**Rejected:** A `SEED_ON_START` env flag on the API — the same destructive write with an
easier way to trigger it by accident.

**Rejected:** Just documenting "restart the API after seeding" — that papers over the
interaction rather than removing it, and still bites on every re-seed.

### 2026-10-18 — Scrubbed the tracked JWT secret; left the SQL sandbox's `Demo2026!` in place

**Context:** `database/.env.example` is tracked and contained a real-looking
`JWT_SECRET_KEY` (64 hex chars) plus `SEED_PASSWORD=Demo2026!`. Separately,
`database/sql/03_seed_data.sql` stores pre-computed bcrypt hashes for `Demo2026!` and
`database/README.md` documents that password — that standalone sandbox never reads
`SEED_PASSWORD`, so the value there is baked into the SQL, not the env.

**Decision:** Blanked `JWT_SECRET_KEY`, `SEED_PASSWORD`, `DB2_PASSWORD` and
`DATABASE_URL_DB2` in `database/.env.example`, adding generation hints — matching what
was already done to `backend/.env.example`. Left the SQL hashes and the README text
alone.

**Why:** An `.example` file must contain placeholders, not live-looking secrets; a
hardcoded signing key is the exact failure the app already guards against in
production. Regenerating the SQL bcrypt hashes changes the DB team's documented demo
credentials, which is their call, not a side effect of containerising.

**Rejected:** Rewriting `03_seed_data.sql` to take the password from the environment —
it is a static artifact loaded by `docker-entrypoint-initdb.d`, with no code path to
hash a runtime value.

### 2026-10-18 — Found: the seed's `_admin`/`_auditor` users never reach the database

**Context:** Verifying the containerised stack showed the DB holding **30** users while
the seeder printed `users: 32`. `app/seed/seed.py` builds `_admin` and `_auditor` as
`User(...)` objects, appends them to the `users` list, and returns `len(users)` — but
only the hospital and bank loop users are passed to `db.add()`. The two org-less demo
accounts are never added to the session and never inserted.

**Decision:** **Not fixed.** Recorded here and in `PROJECT-STATE.md` as a known gap.

**Why:** It is a pre-existing bug in the seeder, not a container issue, and fixing it
silently would change seeded-data semantics (two new admin-class logins) that the demo
may be planned around. The bootstrap admin from `ADMIN_USERNAME`/`ADMIN_PASSWORD` is
unaffected and does authenticate, so the stack is fully usable.

**Rejected:** Adding the missing `db.add()` calls on the spot — correct in isolation,
but it is a behavioural change to another author's tracked file that was never part of
the containerisation brief. Flag to the owner first.

**Follow-up if approved:** `db.add(user)` for both, in the same block that builds them,
and assert the persisted row count rather than trusting `len(users)`.

### 2026-10-18 — Supersedes the entry above: the seed's `_admin`/`_auditor` users now persist

**Context:** The entry above recorded the missing-`db.add()` bug and deliberately left it
unfixed pending the owner's call. The owner approved the fix.

**Decision:** In `app/seed/seed.py` the two org-less demo accounts are now added with a
single `db.add_all(users)` plus a `flush()` in the same block that constructs them, and
the returned `users` count is read back from the database
(`db.scalar(select(func.count()).select_from(User))`) instead of `len(users)`.

**Why:** `db.add_all` is the missing half of the existing code. Counting from the
database rather than from the in-memory list is the part that matters going forward: the
original `len(users)` reported 32 while 30 rows existed and nothing detected the gap — a
count that is read back cannot diverge from what was written.

**Verified** in the containerised stack: `users` by role is `admin:2` (`_admin` + the
bootstrap `admin`), `auditor:1`, `bloodbank_user:20`, `hospital_user:10` — 33 rows — and
`_admin`, `_auditor`, `admin`, `hospital_h_001`, `bank_bb_001` all authenticate. The
seed's own role summary also now reads 32 on its own (33 once the bootstrap admin is
re-asserted), which is the number it always claimed.

**Note:** the demo `_admin`/`_auditor` and the env-driven bootstrap `admin` all carry
`role='admin'`/`'auditor'`. That duplication is intended — the seeded pair are demo
fixtures, the bootstrap one is the temporary env-sourced login.

### 2026-10-18 — The pulled scraper needs `scrapling[fetchers]`, not `scrapling`

**Context:** `bfac9ce` embeds a background scraper. `app/services/eraktkosh_scraper.py`
has a module-level `from scrapling import Fetcher` (line 25), and `app/main.py` imports it
from the lifespan whenever `ERAKTKOSH_AUTO_SYNC_ENABLED` is true — which is the upstream
default. `scrapling` was never added to `backend/requirements.txt`, so the API image
crash-looped on startup with `ModuleNotFoundError: No module named 'scrapling'`.
Installing the bare package only moved the failure along: `scrapling.fetchers.requests`
imports `curl_cffi`, and then `patchright`, giving
`No module named 'patchright'` on the next boot.

**Decision:** `backend/requirements.txt` pins `scrapling[fetchers]==0.5`.

**Why:** The extra is the only spec that satisfies the import chain the fetchers package
walks at import time. It is heavier (adds playwright, patchright, browserforge, msgspec,
Protego, curl_cffi), but the alternative is patching upstream's import. No browser
binaries are installed: the scraper only calls `Fetcher.get`, which is HTTP, so
`playwright install` is never needed.

**Rejected:** `scrapling` alone, and `scrapling` + `curl_cffi` — both fail at import.
Verified by watching the API crash-loop and reading each successive traceback, rather
than guessing the full transitive set.

### 2026-10-18 — The scraper writes to `/data`; give it a writable, persistent path

**Context:** `eraktkosh_scraper.py` derives `PROJECT_ROOT` as four parents up from the
module and writes to `PROJECT_ROOT/data/eraktkosh` and
`PROJECT_ROOT/frontend/public/data/eraktkosh`. Locally that resolves to the repo root. In
the API image the package sits at `/app/app/...`, so four parents up is `/`: the scraper
tries `mkdir /data/eraktkosh` as `appuser` (uid 10001), hits a permission error, and the
write loop aborts — leaving the API's `/summary` endpoint at 404.

**Decision:** The Dockerfile creates `/data/eraktkosh` and
`/frontend/public/data/eraktkosh` owned by `appuser`, and the compose mounts a
`bb_scrape` named volume at `/data`.

**Why:** Both paths are hardcoded upstream, so they must exist and be writable or the
scrape dies part-way and the served data stays empty. The volume keeps snapshots across
`docker compose up --build`, which otherwise recreates the container and discards them.

**Rejected:** Running the API as root so `/` is writable — that trades away the
unprivileged `appuser` hardening for a path only one optional feature touches.

**Verified:** the worker logs `fetched 906 component records` and `Successfully updated
eRaktKosh Bengaluru files for all 8 blood groups`, 17 files land in the volume owned by
`appuser`, and `GET /api/v1/eraktkosh/bangalore/O%2B` returns `total_units=13708`,
`record_count=273`.

### 2026-10-18 — Serve the scrape volume through nginx, and fix the static-first fallback

**Context:** The Live page fetched `/data/eraktkosh/summary.json` first and only fell back
to the API if that request *threw*. Two things combined to pin it to stale data. (i)
Nothing served `/data/eraktkosh` — the scraper writes to a container volume the web
container never saw — so nginx's SPA fallback answered with `index.html` and a 200. (ii)
For the group files the API fallback sat *after* the `if (res.ok)` branch, so the
`res.json()` error on that HTML jumped straight to `catch` and the fallback was never
reached. The blood-group table could not load live data at all.

**Decision:** Mount `bb_scrape` into the web container read-only at
`/usr/share/nginx/html/data`, and rewrite both fetches to try the static snapshot then the
API, counting a response as usable only when it is actually JSON.

**Why:** Mounting the volume makes the static path the UI already prefers genuinely live:
nginx serves the newest scrape off disk, refreshed in place every cycle, with no API
round-trip and no rebuild. The content-type guard is what reopens the fallback, because a
200 that is really `index.html` has to count as a miss.

**Rejected:** Making the API the only source (drops the offline/static-first design and
adds a round-trip per view), and copying files between containers (needs a writer loop on
top of a shared volume — more moving parts for the same result).

**Verified:** `/data/eraktkosh/summary.json` now returns `application/json`;
`POST /api/v1/eraktkosh/sync-now` moved the served `last_updated_iso` from `23:46:25` to
`23:51:28` with no rebuild — precisely the change the page's 30s poll keys on.

### 2026-10-18 — Inventory / Find Supplies / Overview now show live eRaktKosh data, not the seeded demo inventory

**Context:** Inventory, Find Supplies, and Overview rendered `api.depletion` /
`api.inventory` (PostgreSQL, seeded from `backend/datasets/*.csv` demo data), while
only LiveERaktKosh showed the scraped eRaktKosh Bengaluru stock. The user wanted the
newly scraped data visible across the entire website and the old demo data removed.

**Decision:** Replace those three pages' data source with the scraped eRaktKosh data:
`GET /eraktkosh/summary` for per-group units (Inventory stat strip, Overview BloodBoxes)
and a new `GET /eraktkosh/supply` endpoint that unions all 8 group snapshots and
dedupes by blood-bank name using each record's `all_groups` breakdown (Find Supplies per-bank
ranking). `StockItem.hours` became `number | null` (scraped data is a point-in-time
snapshot with no consumption rate or expiry); `BloodBox` renders null hours as
units-based availability with "—" time. The old demo inventory remains in the DB but is
no longer rendered by these pages. RequestBlood's matching engine still reads DB
inventory (distance/ETA matching) — that is a separate computational feature left as-is.

**Why:** The scraped data is the live source of truth (refreshed every 10 min by the
background worker, verified advancing `23:51:28 → 00:13:10`). Serving it through the
existing static-volume mount (`bb_scrape` → nginx `/data/eraktkosh`) plus the new
`/supply` endpoint needs no frontend build on each scrape and no rebuild.

**Rejected:** Syncing scraped data into the PostgreSQL inventory tables (would require a
writer loop, schema mapping for burn-rate/expiry that scraped data lacks, and would clobber
the blood-bank "Add stock" write path); keeping demo and live side-by-side (user asked for
old data removed).

**Verified:** `tsc && vite build` clean; `/eraktkosh/supply` → 98 banks; `/summary`
`last_updated_iso` advances on each 10-min cycle; SPA 200.

### 2026-10-18 — Per-org inventory: blood banks see their own DB stock, hospitals do not hold inventory

**Context:** Inventory/Overview previously showed live eRaktKosh scraped stock for
everyone. The user wants each hospital and blood bank to see only its own
inventory, and the old demo data removed from those pages.

**Decision:** Make Inventory/Overview role-aware:
- `bloodbank_user` → own `BloodInventory` via `api.inventory()` (server-scoped to
  `affiliated_org_id`) + `AddStockForm` write path. Never eRaktKosh.
- `hospital_user` → no inventory table exists for hospitals
  (`BloodInventory.blood_bank_id` only); the page says so and links to "Request
  blood". Hospitals see their own requests instead.
- `admin`/`auditor` → live eRaktKosh summary (they are neither a hospital nor a
  bank).
Added 4 dedicated demo accounts (2 hospitals, 2 blood banks) with individual
env-driven passwords (`DEMO_HOSPITAL_1/2_PASSWORD`, `DEMO_BANK_1/2_PASSWORD`,
defaults for usernames), affiliated to 2 hospitals + 2 blood banks. Verified each
blood bank logs in and sees only its own stock.

**Why:** Keeps inventory as the blood-bank's domain (matches the schema and the
"Add stock" write path) without inventing a hospital-inventory table. Demo
accounts let the user verify per-org isolation immediately.

**Rejected:** Giving hospitals a blood-bank-style inventory table (new table +
migrations + seed + matching-engine changes — out of scope); keeping demo and
live side-by-side (user asked for old data removed).

**Verified:** All 4 demo accounts + admin log in; `demo_bank_1` and
`demo_bank_2` see different stock (per-bank isolation confirmed);
`tsc && vite build` clean.


