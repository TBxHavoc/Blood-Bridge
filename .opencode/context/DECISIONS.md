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

