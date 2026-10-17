# LifeLink Blood Network — Frontend

React + Vite front-end for the LifeLink Blood Bank Management System. It ships
with a complete in-browser mock API so the whole app runs before the backend
exists, and swapping in the real server is a one-line environment change.

## Quick start

```powershell
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

### Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Hospital | `hospital@lifelink.test` | `hospital123` |
| Blood bank | `bloodbank@lifelink.test` | `bloodbank123` |
| Administrator | `admin@lifelink.test` | `admin123` |
| Auditor | `auditor@lifelink.test` | `auditor123` |

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Start the Vite dev server |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm test` | Run Vitest in watch mode |
| `npm run test:run` | Run the test suite once |

## Project structure

```
frontend/
├── index.html                 # Vite entry (mounts the React app)
├── dashboard.html             # Blank placeholder for a future dashboard
├── package.json
├── vite.config.js             # Vite + Vitest config, dev API proxy
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.jsx               # React entry point (router + auth provider)
│   ├── app.jsx                # Route table + role guards
│   ├── api/
│   │   ├── client.jsx         # fetch wrapper: base URL, bearer token, errors
│   │   ├── mock.js            # In-browser mock backend (dev/demo)
│   │   ├── auth.js            # login / logout / me / register
│   │   ├── requests.js        # blood requests
│   │   ├── inventory.js       # blood-bank stock
│   │   ├── matching.js        # unit matching
│   │   └── alerts.js          # operational alerts
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── HospitalDashboard.jsx
│   │   ├── BloodBankDashboard.jsx
│   │   ├── AdminDashboard.jsx
│   │   ├── AuditorDashboard.jsx
│   │   ├── RequestDetails.jsx
│   │   └── NotFound.jsx
│   ├── components/
│   │   ├── Header.jsx
│   │   ├── Sidebar.jsx
│   │   ├── RequestForm.jsx
│   │   ├── RequestTable.jsx
│   │   ├── MatchingResults.jsx
│   │   ├── AlertList.jsx
│   │   ├── InventoryTable.jsx
│   │   └── AuditLogTable.jsx
│   ├── hooks/
│   │   ├── useAuth.jsx        # auth context + provider
│   │   └── useFetch.js        # data-fetching hook
│   ├── utils/
│   │   ├── formatters.js      # dates, numbers, units, expiry
│   │   └── constants.js       # roles, blood groups, statuses, endpoints
│   └── styles/
│       ├── index.css          # Tailwind imports + shared component classes
│       └── custom.css         # login layout + app shell
└── tests/
    ├── setup.js
    ├── components/            # component unit tests
    └── pages/                 # page integration tests
```

## Connecting the backend

The API layer is deliberately the only place that knows about HTTP.

1. Copy `.env.example` to `.env.local`.
2. Set your server URL:

   ```
   VITE_API_BASE_URL=http://localhost:8080/api
   VITE_USE_MOCK=false
   ```

   Leave `VITE_API_BASE_URL` empty (or `VITE_USE_MOCK=true`) to keep using the
   built-in mock API.

3. In development you can instead use the Vite proxy already configured in
   `vite.config.js`:

   ```
   VITE_API_BASE_URL=/api
   VITE_PROXY_TARGET=http://localhost:8080
   ```

`src/api/client.jsx` attaches the bearer token from `localStorage` on every
request and clears it on a `401`, so no component needs to change.

### Expected REST contract

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/login` | `{ email, password }` → `{ token, user }` |
| `POST` | `/auth/logout` | End the session |
| `GET` | `/auth/me` | Current user profile |
| `GET` | `/requests` | List requests (`status`, `urgency`, `q`, `page`…) |
| `POST` | `/requests` | Create a request |
| `GET` | `/requests/:id` | Single request |
| `PATCH` / `DELETE` | `/requests/:id` | Update / remove |
| `GET` | `/requests/:id/matches` | Ranked matching candidates |
| `POST` | `/matches/:id/accept` | Reserve units behind a match |
| `GET` | `/inventory` | List stock (`bloodGroup`, `component`, `status`…) |
| `POST` | `/inventory` | Add a batch |
| `PATCH` / `DELETE` | `/inventory/:id` | Update / remove a batch |
| `GET` | `/alerts` | Operational alerts |
| `PATCH` | `/alerts/:id` | Mark read / dismiss |
| `POST` | `/alerts/read-all` | Mark every alert read |
| `GET` | `/audit` | Audit trail |
| `GET` | `/stats/overview` | Aggregate dashboard counters |

Path helpers live in `src/utils/constants.js` (`API_ENDPOINTS`). Adjust them
there if your backend uses different routes.

## Notes

- **Styling:** Tailwind utility classes are used in components; the shared
  class names (`.btn`, `.card`, `.badge`, `.data-table`, …) live in
  `src/styles/index.css`, and the bespoke login/app-shell layout lives in
  `src/styles/custom.css`.
- **Mock data:** persisted in `localStorage` under `lifelink.mockdb.v1`. From
  the browser console you can run `import('/src/api/mock.js').then(m => m.resetMockDb())`
  to restore the seed data.
- **`dashboard.html`:** intentionally blank — a canvas for a future standalone
  dashboard, with the exact backend endpoints documented in a comment inside.
