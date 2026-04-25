# WatchTower Platform: Developer Manual & Walkthrough

Welcome to the WatchTower Observability Platform! If you are returning to this project after a few months and need a refresher on how the entire monitoring ecosystem operates, this document contains absolutely everything you need to know.

---

## 1. ARCHITECTURE OVERVIEW

**What WatchTower Is:**
WatchTower is a standalone Python (FastAPI) observability application. It acts as an autonomous sentry that constantly monitors the health, logs, and frontend errors of your main project. When things break, it groups the errors into "Incidents" and sends you an email. When things recover, it sends you a recovery email.

**How it relates to the main-project:**
WatchTower runs completely independently on `port 8888`. It monitors the main project (Frontend on `3000` and Backend on `8001`) via HTTP pings, reads the backend's physical log files, and exposes an HTTP endpoint (`/ingest`) that the frontend's browser SDK sends data to.

**The 3 Signal Sources:**
1. **Endpoint Monitoring:** A background job (APScheduler) pings the frontend and backend URLs every 60 seconds to see if they return HTTP 200 OK.
2. **Backend Log Parser:** A background job scans the backend's `app.log` file every minute looking for lines containing `ERROR`, `Exception`, or `Traceback`.
3. **Frontend SDK:** A lightweight JavaScript file (`watchtower.js`) injected into the frontend catches browser crashes, unhandled promises, and failed API calls, instantly POSTing them to WatchTower.

**The Data Flow:**
`Signal Source` ➔ `Event Normalizer` ➔ `Deduplication (Fingerprinting)` ➔ `Incident Engine` ➔ `SQLite Database` ➔ `Alert Dispatcher (SMTP)` ➔ `Your Email Inbox`

**Architecture Diagram:**
```text
      [Browser / User Client]
                 |
                 v
      [Main Frontend (Port 3000)] ------ SDK POSTs Errors -----> [WatchTower (Port 8888)]
                 |                                                          ^
                 v                                                          |
      [Main Backend (Port 8001)]  ------ Writes to app.log -----------------+
                 ^                                                          |
                 +---------------------- (Endpoint Pings) ------------------+
```

---

## 2. FOLDER STRUCTURE

Here is how the repository is laid out:

```text
pager/
├── watchtower/                 ← The standalone monitoring application
│   ├── api/
│   │   ├── dashboard.py        ← Serves the HTML dashboard page and computes system stats
│   │   ├── ingest.py           ← The HTTP endpoint that receives errors from the Frontend SDK
│   │   ├── health.py           ← Simple health check for WatchTower itself
│   │   ├── status.py           ← [NEW] Serves the public status page (GET /status, GET /status/data)
│   │   └── main.py             ← FastAPI entry point, starts the APScheduler background jobs
│   ├── core/
│   │   ├── config.py           ← Loads config.yaml
│   │   ├── database.py         ← SQLite SQLAlchemy connection setup
│   │   ├── enums.py            ← Standardized states (OPEN, RESOLVED, FAILURE, RECOVERY)
│   │   └── models.py           ← Database table schemas (Incidents, AlertDelivery, etc.)
│   ├── services/
│   │   ├── alerter.py          ← Handles the SMTP logic to physically send the emails
│   │   └── dedup.py            ← Generates hashes for errors so duplicates are grouped
│   ├── templates/
│   │   ├── dashboard.html      ← The Jinja2 HTML layout for the dashboard dark-mode UI
│   │   ├── status.html         ← [NEW] The Jinja2 HTML layout for the public status page
│   │   ├── email_failure.html  ← [NEW] HTML template rendered for failure alert emails
│   │   └── email_recovery.html ← [NEW] HTML template rendered for recovery alert emails
│   ├── sdk/
│   │   └── watchtower.js       ← [SOURCE] The canonical SDK source file (~4 KB)
│   ├── workers/
│   │   ├── endpoint_worker.py  ← Background job that pings localhost:3000 and 8001
│   │   ├── log_parser.py       ← Background job that tails backend app.log
│   │   └── incident_engine.py  ← The brain: transitions states, handles cooldowns, triggers emails
│   ├── config.yaml             ← Main configuration (which URLs to ping, log paths, cooldowns)
│   ├── watchtower.db           ← The SQLite database file (auto-generated)
│   └── .env                    ← Secrets file (SMTP passwords, alert emails)
│
└── main-project/               ← Your actual SaaS application
    ├── frontend/
    │   └── public/
    │       ├── watchtower.js   ← [DEPLOYED COPY] The SDK script that listens for window.onerror
    │       └── index.html      ← [MODIFIED] Added the <script> tag to load watchtower.js
    └── backend/
        └── logs/
            └── app.log         ← [MONITORED] WatchTower scans this file for backend crashes
```

---

## 3. HOW TO START EVERYTHING

To boot the entire stack from scratch, you must start the three discrete systems in their own terminal windows.

**Step 1: Start WatchTower**
```powershell
cd %USERPROFILE%/pager/watchtower
.\venv\Scripts\activate
python -m uvicorn watchtower.api.main:app --host 0.0.0.0 --port 8888 --reload
```
*Verification: Open `http://localhost:8888/dashboard`. You should see the UI load.*

**Step 2: Start the Main Backend**
```powershell
cd %USERPROFILE%/pager/main-project/backend
.\venv\Scripts\activate
python -m uvicorn backend.server:app --port 8001 --host 0.0.0.0
```
*Verification: Open `http://localhost:8001/health`. It should return `{"status":"ok"}`.*

**Step 3: Start the Main Frontend**
```powershell
cd %USERPROFILE%/pager/main-project/frontend
yarn start
```
*Verification: Open `http://localhost:3000`. The Track My Academy platform should load.*

---

## 4. HOW TO STOP EVERYTHING

To safely halt the systems:
1. Go to each of the three terminal windows.
2. Press `Ctrl + C`.
3. No special cleanup is required. The SQLite database permanently saves all incident histories automatically.

---

## 5. WHAT WATCHTOWER MONITORS

WatchTower is currently tracking two endpoints:
1. **Main Project Backend** (`http://localhost:8001/health`) - Pinged every 60 seconds.
2. **Main Project Frontend** (`http://localhost:3000`) - Pinged every 60 seconds.

- **Configuration:** This lives in `watchtower/config.yaml`. To add a new target, just append it to the `targets` list in that file.
- **Log Parsing:** The parser tails `%USERPROFILE%\pager\main-project\backend\logs\app.log`.
- **Frontend SDK:** Captures global `window.onerror`, `unhandledrejection` events, failed `fetch` calls, and optionally `console.error` calls.

---

## 6. HOW ALERTS WORK

The incident engine dictates when you receive emails.
- **Failure Email:** Sent the exact moment an endpoint fails its ping, or when Frontend errors spike over the threshold (default 10 errors in 5 mins).
- **Recovery Email:** Sent the exact moment a previously failing endpoint returns HTTP 200 again.
- **Cooldown (Spam Prevention):** If an endpoint stays DOWN, WatchTower will **not** send you an email every 60 seconds. It checks the `alert_deliveries` table. If a failure email was sent less than 30 minutes ago for that specific incident, it suppresses the duplicate email.
- **Settings:**
  - Change email recipients in `watchtower/.env` (`ALERT_EMAIL=user1@gmail.com,user2@gmail.com`)
  - Change the cooldown timer in `watchtower/config.yaml` (`cooldown_minutes: 30`)

---

## 7. THE DASHBOARD

- **URL:** `http://localhost:8888/dashboard`
- **Auto-Refresh:** The page automatically reloads every 30 seconds to show live data.
- **"Status Page →" link:** Added to the top-right of the dashboard header. Clicking it navigates to the public status page at `/status`.

### Targets Status Table
Shows every monitored target with the following columns:
- **NAME** — friendly name from `config.yaml`
- **URL** — the endpoint being pinged
- **STATUS** — `UP` (green) or `DOWN` (red) based on the most recent check result
- **LAST CHECKED** — *(added)* exact timestamp of the most recent ping
- **HTTP CODE / ERROR** — the HTTP response code or the Python exception class (e.g., `ConnectError`)

### System Stats Panel
Five rolling-window metrics are displayed:
| Metric | Window | What it counts |
|---|---|---|
| Frontend Events | Last 1 hour | Events POSTed to `/ingest/frontend` |
| Backend Errors | Last 1 hour | Log-parser error events |
| Open Incidents | All time | Incidents with `state = OPEN` |
| Resolved Today | Today (UTC) | Incidents resolved since midnight |
| Alerts Sent Today | Today (UTC) | Rows inserted into `alert_deliveries` today |

### Recent Incidents Table
Shows the latest 10 incidents — both **OPEN** and **RESOLVED**. Previously this only showed OPEN incidents.

### Recent Alert Deliveries Table
An audit log at the bottom showing every email dispatched. Columns:
- **SENT AT** — timestamp the email was dispatched
- **ALERT TYPE** — `FAILURE` or `RECOVERY`
- **INCIDENT TITLE** — the incident name linked to this delivery
- **SUCCESS** — `True` / `False` (False means SMTP failed)

---

## 8. THE STATUS PAGE *(NEW)*

- **URL:** `http://localhost:8888/status`
- **Auto-Refresh:** The page refreshes its data every **60 seconds** via JavaScript (no full page reload).
- **Purpose:** A clean, public-facing status page you can share with users or stakeholders. Provides an at-a-glance health snapshot without exposing internal incident details.

### Overall Status Banner
A large coloured bar at the top of the page communicates the system-wide health:
| Colour | Meaning |
|---|---|
| 🟢 Green | All monitored targets are currently UP |
| 🟠 Orange | At least one target is DOWN (degraded state) |
| 🔴 Red | All targets are DOWN (major outage) |

### 90-Day Uptime Bars
One section per monitored service. Each section renders 90 individual vertical bars — one per calendar day. Bar colours:
| Colour | Meaning |
|---|---|
| 🔵 Blue (solid) | Service was UP for the entire day (100% checks passed) |
| 🟠 Orange | Mixed day — some checks passed, some failed |
| 🔴 Red | Service was DOWN for the entire day (0% checks passed) |
| ⬜ Gray | No data recorded for that day (e.g., before monitoring started) |

**Hover tooltip:** Hovering any bar reveals a tooltip showing:
- The calendar date
- Number of checks performed that day
- Number of failures
- Uptime percentage for that day

### Dual Uptime Percentages
Below the bars, two uptime numbers are displayed side-by-side for each service:
- **7-day uptime** — rolling last 7 days (most useful for "is it healthy right now?")
- **90-day uptime** — rolling last 90 days (useful for SLA-style reporting)

Both are computed from rows in `endpoint_check_results`. Note: if the service was intentionally stopped during initial setup/testing, this number will be lower than real-world production uptime. A disclaimer label `* Includes test downtime from initial setup` is shown beneath each service.

### Monitoring Start Label
`Monitoring started: Apr 22, 2026` is displayed beneath the bars. This is the date of the oldest row in the `monitor_targets` table — useful context for interpreting gray (no-data) bars at the start of the timeline.

### Recent Incidents Table
Shows the 5 most recent incidents (OPEN and RESOLVED), sorted newest first. Columns: **Title**, **State**, **First Seen**, **Resolved At**.

### New Files Added
- `watchtower/api/status.py` — two routes: `GET /status` (renders the HTML) and `GET /status/data` (returns JSON used by the page's JavaScript).
- `watchtower/templates/status.html` — the Jinja2 template with all the visual logic described above.

---

## 9. ADMIN ENDPOINT *(NEW)*

A maintenance route was added to clean up stale OPEN incidents that were created during testing sessions.

**Endpoint:**
```
POST http://localhost:8888/admin/resolve-stale-incidents
```

**Request body (JSON):**
```json
{
  "older_than_hours": 24,
  "source_type": "FRONTEND"
}
```
- `older_than_hours` — any OPEN incident older than this many hours will be marked RESOLVED.
- `source_type` — one of `"FRONTEND"`, `"BACKEND"`, or `"ENDPOINT"`.

**When to use it:**
After a testing session (e.g., intentionally stopping services to test alerts), run this to clear out the fake OPEN incidents so the status page and dashboard show a clean state.

**PowerShell command:**
```powershell
Invoke-WebRequest -Uri "http://localhost:8888/admin/resolve-stale-incidents" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"older_than_hours": 2, "source_type": "FRONTEND"}'
```

**Fallback (curl on Windows):**
```powershell
curl -X POST http://localhost:8888/admin/resolve-stale-incidents `
  -H "Content-Type: application/json" `
  -d '{"older_than_hours": 2, "source_type": "FRONTEND"}'
```

**Response:**
```json
{ "resolved": 3 }
```
The number indicates how many incidents were resolved.

---

## 10. DATABASE

- **Location:** `%USERPROFILE%/pager/watchtower/watchtower.db`
- **Inspection:** You can open this file using DB Browser for SQLite or any standard SQL client.
- **Tables:**
  - `monitor_targets`: Cached from config.yaml.
  - `endpoint_check_results`: The raw history of every single 60s ping.
  - `backend_error_events`: Events raised by the log parser.
  - `frontend_error_events`: Events received via the SDK ingest endpoint.
  - `incidents`: The grouped issues (Open/Resolved).
  - `incident_events`: Individual events linked to each incident.
  - `alert_deliveries`: Tracks timestamps of sent emails to enforce cooldowns.
- **Cleanup:** If the DB gets too large, you can safely delete the `watchtower.db` file while WatchTower is stopped. It will auto-recreate a fresh one on the next startup. Run `alembic upgrade head` afterwards to re-apply schema migrations.

---

## 11. ENVIRONMENT VARIABLES

The `watchtower/.env` file controls secrets:
- `WT_SECRET_KEY`: (Required) API key for the `/ingest` route to prevent unauthorized error spam.
- `SMTP_PASSWORD`: (Required for emails) Your Google App Password (16-characters, no spaces). If this changes, update it here and restart WatchTower.
- `ALERT_EMAIL`: (Required) Comma-separated list of who receives the pages.
- `WATCHTOWER_INGEST_KEY`: The ingest API key that must match the `apiKey` set in `index.html`.

---

## 12. FRONTEND SDK REFERENCE

The SDK is loaded dynamically in `main-project/frontend/public/index.html`.
It initializes with:
```javascript
WatchTower.init({
    ingestUrl: 'http://localhost:8888/ingest/frontend',
    appId: 'main-project-frontend',
    environment: 'development',
    releaseVersion: '1.0.0',
    apiKey: 'wt_changeme_secret_key' // Must match WT_SECRET_KEY in backend .env
});
```
- **Manual Error Capture:** `WatchTower.captureError(new Error("Database offline"));`
- **Manual Message Capture:** `WatchTower.captureMessage("User failed checkout", "warning");`
- **Verification:** Open the browser Network Tab. When an error occurs, you will see a `POST` request to `localhost:8888` returning `202 Accepted`.
- **Batching:** The SDK queues events in memory and flushes either when 10 events accumulate **or** every 5 seconds — whichever comes first.
- **Silent-fail:** If WatchTower is unreachable, the SDK catches the network error silently. The main app is never affected. You may see `net::ERR_CONNECTION_REFUSED` in the Network tab, but users see nothing.

---

## 13. KNOWN BEHAVIOR & EDGE CASES *(NEW)*

These behaviors were verified through live tests. Knowing these prevents confusion when operating WatchTower in real scenarios.

### Detection Timing
| Scenario | Detection Speed |
|---|---|
| Endpoint check (worst case) | ~70 seconds (60s interval + 10s timeout) |
| Endpoint check (best case) | ~5–10 seconds (check fires shortly after failure) |
| Frontend SDK (error caught) | Sub-second (immediate POST) |

### Flapping Behavior (verified)
- **1 failure email** is sent per 30-minute cooldown window per incident.
- **Recovery emails bypass the cooldown** — you will always receive a recovery email when a service comes back up.
- The **same incident row** is reused across flap cycles (no duplicates created).
- **Example:** A service flaps 4 times (down → up → down → up) within 30 minutes → you receive **1 failure email + 2 recovery emails**.

### Restart Behavior (verified)
- All incident state is **persisted in SQLite** and survives restarts.
- WatchTower does **NOT** re-send failure emails for already-OPEN incidents when it boots up.
- The cooldown window **survives restarts** — it is calculated from the `sent_at` timestamp in `alert_deliveries`, not from in-memory state.
- The APScheduler **resumes automatically** within ~70 seconds of startup (first interval fires after the configured delay).

### WatchTower Going Down (verified)
- The Frontend SDK **fails silently** when WatchTower is unreachable.
- The main project frontend remains **fully functional** — no user-visible errors.
- The browser's Network tab will show `net::ERR_CONNECTION_REFUSED` on the SDK POST, but no JS exception is thrown in the main thread.
- Events queued during the downtime are **dropped** (the SDK does not persist them to localStorage).

### Both Services Down Simultaneously (verified)
- **2 separate incidents** are created — one per target.
- **2 separate failure emails** are sent (one per incident).
- Each incident's **cooldown is tracked independently** — resolving one does not affect the other's cooldown.

### Frontend SDK as Early-Warning System
- If a user's browser makes an API call that fails (e.g., backend returns 500 or times out), the SDK captures the failed `fetch` sub-second.
- This means WatchTower can detect backend problems **through the frontend** before the 60-second endpoint checker even fires.
- Failed fetch calls appear in the `frontend_error_events` table.
- If 10+ pile up in 5 minutes, a separate **FRONTEND incident** is opened and an alert is sent.

---

## 14. COMMON ISSUES & HOW TO FIX THEM

- **WatchTower won't start:** You probably forgot to activate the virtual environment (`.\\venv\\Scripts\\activate`) or port 8888 is already in use (see port fix below).

- **Dashboard shows all targets DOWN but apps are working:** Check `config.yaml`. Ensure the URLs are correct (`http://localhost:3000`). If they are correct, WatchTower might be resolving `localhost` to IPv6 while your app is bound to IPv4.

- **No emails being received:** Your `SMTP_PASSWORD` is missing or invalid. Note: Standard Google passwords do not work; you MUST use a generated "Google App Password" with 2FA enabled.

- **Emails arriving but going to spam:**
  Add your `SMTP_USER` address (e.g., `noreply@watchtower.dev` or the Gmail address in `.env`) to your Gmail contacts. Also verify that the `From:` address in `alerter.py` matches `SMTP_USER` exactly.

- **Frontend SDK not sending events (401 error in Network tab):**
  The `apiKey` value in `index.html` does not match `WATCHTOWER_INGEST_KEY` in `.env`. They must be identical strings. Update one to match the other and hard-refresh the browser (`Ctrl + Shift + R`).

- **Frontend SDK not sending events (CORS error in Network tab):**
  Open `watchtower/api/main.py` and find the `CORSMiddleware` configuration. Ensure `http://localhost:3000` is in the `allow_origins` list. Restart WatchTower after editing.

- **Duplicate spam emails:** Check the `alert_deliveries` table. If it's empty, the DB is failing to record deliveries, meaning the 30-minute cooldown logic bypasses.

- **Log parser not detecting errors:** Ensure the path to `app.log` in `config.yaml` is absolute and perfectly correct for your Windows machine.

- **Status page shows wrong (low) uptime percentage:**
  The low percentage likely reflects intentional downtime during initial testing. A disclaimer `* Includes test downtime from initial setup` is shown on the page. To fully reset: stop WatchTower, delete `watchtower/watchtower.db`, run `alembic upgrade head`, and restart.

- **APScheduler not running (no checks firing after startup):**
  Check `api/main.py` for the `lifespan()` context manager. The scheduler must be started **inside** the lifespan function, not at module level. Add a `print` or `logging` statement inside `run_endpoint_checks()` and restart to confirm it fires.

- **SQLite database locked error:**
  Only one process should access `watchtower.db` at a time. Make sure you are not running two instances of WatchTower simultaneously. If you have **DB Browser for SQLite** open, close it before starting WatchTower.

- **WatchTower port 8888 already in use:**
  ```powershell
  netstat -ano | findstr :8888
  taskkill /PID <pid_from_above> /F
  ```
  Then restart WatchTower normally.

---

## 15. HOW TO INTEGRATE WATCHTOWER INTO A NEW PROJECT

If you build a new microservice and want to monitor it:
1. Open `watchtower/config.yaml`
2. Add a new block under `targets`:
```yaml
  - name: "New Microservice"
    url: "http://localhost:5000/ping"
    method: "GET"
    expected_status: 200
```
3. Copy `watchtower/sdk/watchtower.js` into your new project's public folder.
4. Add the `<script> WatchTower.init({...}) </script>` block to its HTML index.
5. Restart WatchTower. It will instantly begin tracking the new architecture.

---

## 16. QUICK REFERENCE CHEATSHEET

```text
=== WATCHTOWER QUICK REFERENCE ===

START:
    1. cd %USERPROFILE%/pager/watchtower
     venv\Scripts\activate
     python -m uvicorn watchtower.api.main:app --host 0.0.0.0 --port 8888 --reload

    2. cd %USERPROFILE%/pager/main-project/backend
     venv\Scripts\activate
     python -m uvicorn backend.server:app --port 8001 --host 0.0.0.0

    3. cd %USERPROFILE%/pager/main-project/frontend
     yarn start

URLS:
  WatchTower Dashboard  → http://localhost:8888/dashboard
  WatchTower Status     → http://localhost:8888/status
  WatchTower Status API → http://localhost:8888/status/data
  WatchTower Health     → http://localhost:8888/health
  Ingest Endpoint       → http://localhost:8888/ingest/frontend
  Main App Backend      → http://localhost:8001
  Main App Frontend     → http://localhost:3000

KEY FILES:
  Monitor targets       → watchtower/config.yaml
  Environment vars      → watchtower/.env
  Database              → watchtower/watchtower.db
  SDK source            → watchtower/sdk/watchtower.js
  Frontend SDK (deploy) → main-project/frontend/public/watchtower.js
  SDK injection         → main-project/frontend/public/index.html
  Backend log file      → main-project/backend/logs/app.log
  Alert email           → watchtower/.env → ALERT_EMAIL

ADMIN COMMANDS:
  Resolve stale FRONTEND incidents (PowerShell):
    Invoke-WebRequest -Uri "http://localhost:8888/admin/resolve-stale-incidents" `
      -Method POST -ContentType "application/json" `
      -Body '{"older_than_hours": 2, "source_type": "FRONTEND"}'

  Resolve stale BACKEND incidents:
    Invoke-WebRequest -Uri "http://localhost:8888/admin/resolve-stale-incidents" `
      -Method POST -ContentType "application/json" `
      -Body '{"older_than_hours": 2, "source_type": "BACKEND"}'

  Resolve stale ENDPOINT incidents:
    Invoke-WebRequest -Uri "http://localhost:8888/admin/resolve-stale-incidents" `
      -Method POST -ContentType "application/json" `
      -Body '{"older_than_hours": 2, "source_type": "ENDPOINT"}'

DETECTION SPEED:
  Worst case  → 70 seconds (60s interval + 10s timeout)
  Best case   → 5-10 seconds
  SDK channel → sub-second

COOLDOWN:
  30 min between duplicate FAILURE emails (per incident)
  Recovery emails bypass cooldown — always sent immediately

ALERT EMAILS → you@example.com, team@example.com
DASHBOARD    → http://localhost:8888/dashboard

RESET (nuclear option — clears all history):
  1. Stop WatchTower
  2. Delete watchtower/watchtower.db
  3. cd watchtower && alembic upgrade head
  4. Restart WatchTower

===================================
```
