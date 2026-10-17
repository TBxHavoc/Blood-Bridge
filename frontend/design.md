# HemoTrack — Design & Integration Spec

**Product:** HemoTrack — a hospital blood-bank stock dashboard.
**Reference implementation:** `hospital-home.html` (single file, no build step).
**Purpose of this document:** capture the look-and-feel, the design tokens, the component contracts and the data/DOM shapes so this prototype can be dropped into a real front end and wired to a real back end with minimal guesswork.

---

## 1. Look & feel

**One line:** a warm, clinical "medical ledger" — a deep burgundy sidebar against a soft off-white paper canvas, blood-red accents, and a serif touch reserved for names, titles and blood types.

| Aspect | Description |
|---|---|
| Mood | Calm, trustworthy, precise. Editorial rather than corporate-flat. |
| Density | Comfortable. Generous whitespace, hairline separators. |
| Colour usage | Restrained. Red is the only accent; status colours are small and tinted, never full-bleed. |
| Surfaces | Flat white cards with a 1px red-tinted border and a whisper of shadow. No gradients except the sidebar. |
| Type pairing | **Cormorant Garamond** (serif) for display/identity; **Inter** (sans) for everything functional. |
| Motion | Subtle and quick (150ms) for UI; one expressive moment — the status wash on the blood boxes (1.1s eased). |
| Decoration | Hand-drawn red scribbles + dots drifting behind content (SVG, ~17–20% opacity). Never interactive. |

### The two "signature" ideas
1. **Serif = identity, sans = data.** Blood types, the hospital name, and page titles (`h1`) are serif. Numbers, labels, tables and controls are Inter.
2. **The blood box is the gauge.** On the Overview page each blood type is a compact card whose background is a translucent status wash that fills left→right and *recedes right→left* as the stock level drops. The dropdown reveals the raw numbers.

---

## 2. Design tokens

All tokens live in `:root`. Mirror them 1:1 in your theme layer (CSS variables, Tailwind config, or a JS theme object).

### 2.1 Colour

**Neutrals / brand**

| Token | Value | Use |
|---|---|---|
| `--white` | `#ffffff` | Card surfaces, input backgrounds, active nav pill |
| `--paper` | `#f7f4f4` | Page canvas (`body`) |
| `--ink` | `#231a1c` | Primary text |
| `--muted` | `#6b5d60` | Secondary text, labels, table headers |
| `--line` | `#e6dedf` | Hairline separators, subtle borders |
| `--red` | `#a31424` | Primary accent: topline, buttons, links, count badges |
| `--red-deep` | `#7a0f1b` | Hover/active accent, `h1`, active nav text |
| `--red-tint` | `#f8e8ea` | Rank badge background |
| `--outline` | `rgba(163,20,36,.42)` | The standard border for **cards and inputs** |

**Status scale (time until a blood type runs out).** Each status has a strong text/fill colour and a pale tint.

| Status | Class | Colour token | Value | Tint token | Value | Meaning |
|---|---|---|---|---|---|---|
| Critical | `crit` | `--crit` | `#b3121f` | `--crit-bg` | `#fdecee` | Under 1 day |
| Low | `low` | `--low` | `#c2410c` | `--low-bg` | `#fff0e5` | 1–3 days |
| Watch | `warn` | `--warn` | `#a16207` | `--warn-bg` | `#fff6d9` | 3–7 days |
| Good | `good` | `--good` | `#1f7a4d` | `--good-bg` | `#e7f5ed` | Over 7 days |

**Sidebar gradient** (the only gradient in the UI):

```css
background:
  radial-gradient(ellipse at 40% 95%, rgba(255,120,130,.14), transparent 62%),
  linear-gradient(170deg, #8a1424 0%, #6e0e1c 55%, #560a15 100%);
```

**Decoration colour:** `#a31424` at `opacity: .17` (strokes) and `.2` (dots).

### 2.2 Typography

```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

| Role | Font | Weight | Size | Where |
|---|---|---|---|---|
| Brand | Cormorant Garamond, Georgia | 700 | 1.9rem | `.hospital` |
| Page title | Cormorant Garamond | 700 | 2.6rem | `h1` (page sections) |
| Greeting | Inter | 700 | 2.5rem | `.greeting` (Overview) |
| Blood type | Cormorant Garamond | 700 | 1.5rem | `.bt` (box header) |
| Blood type (table) | Cormorant Garamond | 700 | 1.7rem | `.tcol` (Inventory) |
| Blood bank (rail) | Cormorant Garamond | 700 | 1.6rem | `.rc-bank` |
| Body / UI | Inter | 400–600 | 0.8–1rem | everything else |

Base: `font-family: Inter, system-ui, sans-serif`. All numeric displays use `font-variant-numeric: tabular-nums`.

### 2.3 Space, shape, depth, motion

| Token | Value | Notes |
|---|---|---|
| Radius — cards | `12px` | `.card`, `.box`, `.blank` |
| Radius — controls | `8px` | inputs, selects, buttons, nav items |
| Radius — pills | `99px` | `.pill`, `.time`, `.count`, `.exp`, topline |
| Radius — round | `50%` | avatar, dots, rank badge |
| Card border | `1px solid var(--outline)` | standard |
| Subtle border | `1px solid var(--line)` | separators, `.box` rest state |
| Card shadow | `0 1px 2px rgba(60,10,16,.04)` | cards/boxes |
| Focus ring | `outline: 2px solid var(--red); outline-offset: 2px` | white ring in the sidebar |
| Input focus | `border-color: var(--red); box-shadow: 0 0 0 3px rgba(163,20,36,.14)` | |
| Transition | `background .15s, color .15s, border-color .15s` | UI hover |
| Wash transition | `width 1.1s cubic-bezier(.2,.8,.2,1)` | blood box fill |
| Reduced motion | `.fill { transition: none }` | honoured |

### 2.4 Z-index layers
`deco: 0` → `main content: 1` → `sidebar: 2`. Focus outlines and dropdowns never fight the decoration because the decoration is `pointer-events: none`.

---

## 3. Layout shell

```
body  →  grid: 270px | 1fr          (sidebar | main)
```

- **`.side`** — burgundy sidebar, fixed width 270px, flex column: `.top` (brand + profile), `.group` label, `nav` (workspace items), `.faq` (pinned to bottom via `margin-top:auto`).
- **`main`** — scroll container (`overflow: auto`), padding `34px 44px 44px`. Holds the 7px red **`.topline`** and the `.deco` SVG, then the page `<section>`s.
- **`.layout`** — two-column page body: `minmax(0,1fr) | 320px`, `align-items: start`. Left = primary content; `.rail` = stacked side cards (`.rail { display:grid; gap:20px }`).
- **`.types`** — blood box grid: `repeat(4, minmax(0,1fr))`, `align-items: start` (critical: keeps a collapsed box from stretching to match an expanded neighbour), gap `12px`.

**Section visibility contract:** every page is a `<section>` inside `main`; all but the active one carry the `hidden` attribute. `[hidden] { display:none !important }` is global. Only one section is visible at a time (see `go()` in §6.5).

---

## 4. Components

Each component lists its class, the markup contract, and its variants/states. Treat the classes as the public API.

### 4.1 Buttons

| Class | Variant | Rest | Hover | Focus |
|---|---|---|---|---|
| `.go` | Solid (submit) | `--red` bg, white text | `--red-deep` bg | red outline |
| `.restock` | Outline | white bg, `--red` text + 1px `--red` border | fills `--red` | red outline |
| `.submit` | Solid (form) | `--red` bg, white text | `--red-deep` bg | red outline |
| `.link` | Text | `--red`, underlined | — | red outline |
| `.banklink` | Text + arrow | `--red`, 600 weight, arrow hidden | underline, arrow fades/slides in | red outline |
| `.iconbtn` (`.profile`) | Round on sidebar | `rgba(255,255,255,.16)` | `.28` | white outline |

### 4.2 Card

```html
<div class="card">
  <h2>Title</h2>
  <div class="body">…</div>
</div>
```
- `.card` = white surface, `--outline` border, `12px` radius, soft shadow.
- `h2` padding `18px 20px 0`; `.body` padding `14px 20px 20px`.
- Variants: `.tablecard` (`overflow:hidden`) wraps tables.

### 4.3 List (activity, alerts, requests)

```html
<ul class="list">
  <li><span class="dot"></span><div>Title<small>meta</small></div></li>
</ul>
```
- Hairline separators between items; first/last trimmed.
- `.dot` (9px circle) colour is set by a status class on the `<li>`:
  - `.alert.crit|low|warn|good .dot` → status colour; `.alert.none` / default `.dot` → `#d98a93`.
- `<small>` = muted meta line under the item.

### 4.4 Blood type box — the gauge (Overview)

Compact, expandable, self-indicating.

```html
<div class="box good" data-…>
  <button class="boxhead" aria-expanded="false" aria-label="Blood type A+ details">
    <span class="fill" data-w="85"></span>          <!-- the wash, width = level % -->
    <span class="sdot"></span><span class="bt">A+</span>
    <span class="btime">8d 12h</span>               <!-- inline time; hidden when open -->
    <svg class="chev">…</svg>
  </button>
  <div class="boxbody" hidden>
    <div class="unitrow">
      <div class="units">68<small>units available</small></div>
      <span class="pill">Good</span>
    </div>
    <!-- optional expiry tag -->
    <span class="exp soon">…</span>
    <div class="runout"><small>Estimated time until we run out</small><b>8d 12h</b></div>
  </div>
</div>
```

**Behaviour**
- Collapsed: `sdot` (status dot), the serif blood type, an inline time-to-run-out label (`.btime`), a chevron, and the wash.
- **The wash (`.fill`)** is a translucent overlay inside the header band. Width = `min(hours/240, 1) × 100%` where `hours = units ÷ perDay × 24` (full at 10 days). It is confined to the header (not the dropdown) and re-animates from 0 each time the box opens.
- **Wipe edge:** the wash is softened with a mask — `-webkit-mask-image` / `mask-image: linear-gradient(to right, #000 calc(100% - 22px), transparent)` — so the right edge fades out instead of ending in a hard cut. Fills narrower than 22px fade almost entirely, which visually reinforces a near-empty box.
- **Inline time (`.btime`):** shows `duration(hours)` on the collapsed box; it is hidden (`.box.open .btime { display:none }`) once expanded, where the full run-out row takes over.
- **Dropdown:** the header `<button>` toggles `.box.open` on `.box`, flips `aria-expanded`, and toggles `hidden` on `.boxbody`. Independent per box.
- Status class on `.box` (`crit|low|warn|good`) sets `--c` (strong) and `--bg` (wash/pill tint).

### 4.5 Pills & tags

| Class | Purpose | Style |
|---|---|---|
| `.pill` | Status word (Good/Low/…) | status text colour on status tint, `99px` |
| `.time` | Time-to-run-out chip (Inventory, supplies, rail) | `padding:4px 11px`, `99px`, status tint |
| `.exp` / `.exp.soon` | "N expiring in D days" | warn tint, or `low` tint when `soon` (≤2 days) |
| `.count` | Red oval count (Alerts, Your requests) | `--red` bg, white text, `99px` |
| `.btime` | Inline time-to-run-out on a collapsed blood box | muted, 600 weight, tabular-nums; hidden while the box is open |

### 4.6 Stat strip (Inventory)

```html
<div class="card strip">
  <div class="cell"><span class="lbl">Total units in inventory</span>
    <b class="val">236<small> units</small></b></div>
  …
</div>
```
4 cells, left hairline separators (`--outline`); `.val.crit` / `.val.warn` colour overrides. Collapses to 2 columns < 800px.

### 4.7 Table

```html
<div class="card tablecard"><div class="tablewrap">
  <table><thead>…</thead><tbody>…</tbody></table>
</div></div>
```
- `th`: muted, `#fbf3f4` background, `--outline` bottom border.
- `td`: `--line` bottom border; row hover `#fdfafa`; tabular numbers.
- `.tablewrap { overflow-x: auto }`; tables have `min-width` (Inventory 780px, supplies 640px) so they scroll rather than squash.
- Blood-type cell: `.tcol` (serif) wrapping `.tc` (flex row with `.exp`).
- `.rank` = numbered circle; first row's rank is filled red.

### 4.8 Form controls (Request blood)

```html
<div class="field">
  <label for="rType">Blood type</label>
  <select id="rType">…</select>
</div>
```
- `.form` = 2-column grid, gap `16px 18px`; `.field.wide` spans both columns.
- Inputs/selects/textareas: white, `--outline` border, `8px` radius, red focus ring.
- Selects use a custom inline-SVG chevron (`appearance:none`).
- `.actions` row holds `.submit` + `.hint`.

### 4.9 Notice (success)

```html
<div class="notice" id="restockNotice" hidden>
  <svg>…check…</svg>
  <div><strong>Request submitted</strong><small>…</small></div>
</div>
```
Good-tint background, good-coloured border/text; `hidden` until a request is submitted.

### 4.10 Key/value rail rows

```html
<div class="kv"><span>Total units in stock</span><b>186 units</b></div>
```
Flex row, hairline bottom, muted label, tabular bold value. Used by the "Selected blood bank" card.

### 4.11 Legend

```html
<div class="legend"><span><i style="background:var(--crit)"></i>Under 1 day</span> … <em>Sample data</em></div>
```
Colour-key dots + labels; the `<em>` right-aligns (and wraps to its own line on small screens).

---

## 5. Pages

| View (`data-view`) | `<section id>` | Status | Summary |
|---|---|---|---|
| Overview | `home` | Built | Dateline + greeting, legend, blood box grid, Recent activity card (live `#activity`), Alerts rail (with live pending-requests counter) |
| Inventory | `inventory` | Built | Stat strip, legend, full stock table with per-type **Restock** buttons |
| Find supplies | `supplies` | Built | Search (blood type or bank name), status line, ranked blood-bank table |
| Request blood | `restock` | Built | Restock form + "Selected blood bank" rail + "Your requests" rail |
| Reports | `other` | Placeholder | `h1` + lead + dashed `.blank` panel |
| FAQ | `other` | Placeholder | same as Reports |

Nav is a `<button class="item" data-view="…">` list; the active item carries `aria-current="page"`.

---

## 6. Behaviour & data contracts

### 6.1 Live clock / greeting
`tick()` runs every 1s → `#dateline` = `"Saturday, October 17 · 9:41 PM / XYZ"`, `#greeting` = Good morning/afternoon/evening.

### 6.2 Derivation rules (business logic to port)

```
hoursToRunOut(units, perDay) = units / perDay * 24
status(hours):  <24 → crit "Critical";  <72 → low "Low";  <168 → warn "Watch";  else good "Good"
duration(hours): <24 → "N hrs"; else "Dd Hh"
levelPct(hours) = min(hours / 240, 1) * 100         // wash, full at 10 days
availabilityOf(units, specific):
    thresholds = specific ? [40, 15] : [250, 100]
    >= hi → good "High";  >= mid → warn "Medium";  else low "Limited"
```
`expTag(type)` returns a `.exp` (+`.soon` when ≤2 days) tag when the type has expiring units.

### 6.3 Sample data shapes (replace with API responses)

```js
// STOCK: [bloodType, unitsAvailable, avgUnitsUsedPerDay]
const STOCK = [['A+',68,8], ['A-',22,4], ['B+',54,9], ['B-',14,7],
               ['O+',81,12], ['O-',31,14], ['AB+',27,3], ['AB-',9,12]];

// EXPIRY: type -> [units, daysUntilExpiry]
const EXPIRY = { 'O+':[5,2], 'A+':[3,4], 'B+':[2,5], 'AB+':[2,6] };

// TYPES is the ordered key list: STOCK.map(([t]) => t)

// BANKS: [name, kmAway, unitsByType]  where unitsByType follows TYPES order
const BANKS = [
  ['City Central Blood Bank', 3.2, [40,12,35,8,55,18,14,4]],
  // … name, distance, [A+,A-,B+,B-,O+,O-,AB+,AB-]
];
```

### 6.4 Search (Find supplies)
`parseQuery(text)` → blood type when the text matches `^(ab|a|b|o)\s*(\+|-|pos|neg…)` (accepts `"O-"`, `"O negative"`, `"ab pos"`), otherwise a free-text bank-name query. Bank names use fuzzy matching (`nameScore` + `editDistance`, 1-char typo tolerance) and **all results are ranked closest→farthest**. If a name search matches nothing, the nearest bank is shown with a "showing the closest one" note.

### 6.5 Navigation — `go(name, opts)`
Single entry point for page switching:
```js
go('Find supplies', { type: 'O-' })   // open supplies pre-filtered
go('Request blood', { bank: 'City Central Blood Bank' })  // open restock pre-selected
```
It sets `aria-current` on the matching nav item, toggles every section's `hidden`, updates `document.title` to `HemoTrack | <name>`, and resets `main.scrollTop`.

### 6.6 Request blood
- Bank + type `<select id="rBank"|"rType">` are populated once from `BANKS` / `TYPES`.
- `renderBankSummary()` keeps the "Selected blood bank" rail in sync with the chosen bank + type.
- Submit: validates units ≥ 1, builds a `ref` (`REQ-1041…`), `unshift`s into `REQUESTS`, renders the "Your requests" list and shows the `.notice`. It also **updates the Overview live**: the request is prepended to `#activity` (its `.dot` coloured by urgency via `crit`/`low`/`good`) and `#pendingCount` is incremented. **Note:** this is client-side only — nothing is sent to a server yet.

### 6.7 DOM id reference (stable hooks; keep these in the real build)

| id | Page | Purpose |
|---|---|---|
| `dateline`, `greeting` | Overview | live date/time + greeting |
| `types` | Overview | container the blood boxes are appended to |
| `alertCount`, `alerts` | Overview | alerts count + list |
| `activity` | Overview | live "Recent activity" list — new requests are prepended |
| `pendingCount` | Overview | the "N requests awaiting approval" number, incremented on submit |
| `strip`, `invRows` | Inventory | stat strip + table body |
| `searchForm`, `searchInput`, `supplyStatus`, `supplyRows`, `unitsHead` | Find supplies | search + results |
| `rBank`, `rType`, `rUnits`, `rUrgency`, `rNote`, `restockForm`, `restockNotice`, `restockNoticeText`, `reqList`, `reqCount`, `rcBank`, `rcDist`, `rcTotal`, `rcType`, `rcAvail` | Request blood | form + rail |
| `title`, `lead`, `blank` | Reports/FAQ | placeholder content |

---

## 7. Integration guide

### 7.1 Front end
1. **Lift the tokens.** Copy the `:root` block into your global stylesheet / Tailwind `theme.extend.colors`. Keep the token *names*; they are used throughout the markup.
2. **Keep the class contracts.** Recreate the components in §4 as framework components (React/Vue/Svelte). The class names and DOM shape are the API — e.g. a `<BloodBox status units perDay type expiry/>` that renders §4.4.
3. **Replace sample data at these seams:**
   - `STOCK`, `EXPIRY`, `BANKS` → your data-fetch layer.
   - The seeded Overview "Recent activity" items (`<ul id="activity">`, 5 static entries) and the starting `pendingRequests = 5` → real feeds.
   - Submitted requests already prepend to `#activity` and bump `#pendingCount` locally (see §6.6); swap those two statements for your `POST` response once the endpoint exists.
   - `HOSPITAL = 'XYZ'` → tenant/hospital name from config or session.
4. **Reuse the derivation functions** in §6.2 in a shared `blood.js` module so the box gauge, the table chips and the alerts always agree.
5. **Keep `go()` (or its equivalent router).** All cross-page links call it with `{ type }` or `{ bank }`; the restock deep-link from a bank row depends on it.
6. **Two build-time cleanups:** the "Sample data" legends and the `.hint`/`note` "Sample data — nothing is sent" copy should be removed once live.

### 7.2 Back end — suggested API contract
The UI needs three reads and one write. Shapes below map directly onto the JS in §6.3.

**`GET /api/stock` → blood types + levels**
```json
[
  { "type": "A+", "units": 68, "perDay": 8, "expiring": [ { "units": 3, "days": 4 } ] },
  { "type": "AB-", "units": 9, "perDay": 12, "expiring": [] }
]
```
*(`hoursToRunOut`, `status`, `levelPct` are derived client-side per §6.2 so the gauge stays consistent.)*

**`GET /api/banks?type=O-` → ranked blood banks**
```json
[
  { "name": "Riverside Regional Blood Center", "km": 7.8, "units": 60,
    "unitsByType": { "A+": 64, "A-": 28, "B+": 50, "B-": 22, "O+": 90, "O-": 60, "AB+": 26, "AB-": 22 } }
]
```
Return closest-first (or sort client-side by `km`).

**`GET /api/alerts` → alerts rail**
```json
[ { "level": "crit", "title": "O- is critically low", "note": "31 units left, about 2d 3h remaining" } ]
```
`level ∈ crit|low|warn|good|none`.

**`POST /api/replenishment-requests` → create a restock request**
```json
{ "bank": "Riverside Regional Blood Center", "type": "O-", "units": 25,
  "urgency": "Urgent", "note": "Ship to ward 4" }
```
Respond with `{ "ref": "REQ-1041", "status": "pending", "createdAt": "…" }` and echo it into the `.notice` + "Your requests" list. Suggested `urgency` enum: `Routine | Urgent | Emergency`.

**Optional:** `GET /api/activity` for the Overview "Recent activity" feed.

### 7.3 Mapping table (UI element → data)
| UI element | Source | Derivation |
|---|---|---|
| Blood box status class + dot | `/api/stock` | `status(hours)` |
| Blood box wash width | `/api/stock` | `levelPct(hours)` |
| Blood box dropdown numbers | `/api/stock` | units, `duration(hours)` |
| Expiry tag | `/api/stock`.expiring | `.exp` / `.exp.soon` |
| Inventory strip | `/api/stock` | totals/sums |
| Inventory table chips | `/api/stock` | `status`, `duration` |
| Find supplies rows | `/api/banks` | `availabilityOf` |
| Alerts | `/api/alerts` | verbatim (+ `.count` = length) |
| Recent activity | `/api/activity` + request echo | newest first |
| Requests-awaiting counter | pending requests | count |
| Your requests | `POST` response | verbatim |

---

## 8. Accessibility

- Every action is a real `<button>` (nav, box header, bank link, submit, restock). No clickable `<div>`s for interactive controls.
- The box header exposes `aria-expanded`; `boxbody` uses the `hidden` attribute.
- `#supplyStatus` is an `aria-live="polite"` region so search results announce.
- Nav uses `<nav aria-labelledby="workspace">`; the decorative SVG is `aria-hidden="true"`.
- Focus is always visible: red ring on light surfaces, white ring in the sidebar. `:focus-visible` is used so mouse clicks don't flash a ring; the box header uses an inset outline so it is never clipped by the card's `overflow:hidden`.
- Status is never colour-only: each coloured dot/pill is paired with a text label (Critical / Low / Watch / Good, High / Medium / Limited).
- `prefers-reduced-motion` disables the wash transition.

---

## 9. Responsive

| Breakpoint | Change |
|---|---|
| ≤ 1180px | `.layout` → single column; `.rail` → 2-up grid |
| ≤ 1060px | `.types` → 2 columns |
| ≤ 800px | `body` → stacked (sidebar becomes a horizontal top bar; nav scrolls horizontally, `.group` hidden); `main` padding tightens; `.deco` spans full width; `.rail` → 1 column; greeting shrinks; stat strip → 2 columns |
| ≤ 640px | `.form` → 1 column |

Tables keep a `min-width` and scroll horizontally inside `.tablewrap` rather than collapsing.

---

## 10. Conventions (do / don't)

**Do**
- Reach for a token (`var(--…)`) before any literal colour.
- Use serif only for identity/display (names, titles, blood types); Inter for data.
- Keep cards to `1px var(--outline)` + `12px` radius; keep pills `99px`.
- Pair every status colour with a text label.
- Add a new page as a hidden `<section>` + a `data-view` nav button, then extend `go()`.

**Don't**
- Don't introduce a second accent hue — red is the only brand accent; green/orange/yellow exist *only* as status.
- Don't use gradients or heavy shadows (sidebar gradient and the 1px card shadow are the whole budget).
- Don't let the blood-box wash bleed into the dropdown (it is intentionally clipped to the header).
- Don't hard-code sample figures in a component — pull from the data layer so derivation stays single-sourced.

---

*Reference file: `hospital-home.html`. Sections, ids and class names in this document are the current contract; if you rename them in the real build, update §4 and §6.7 together.*
