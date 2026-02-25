# Deploying Project SC on a Windows PC

This guide covers packaging and running the application on a separate Windows machine. You handle PostgreSQL installation; below are the other steps.

---

## 1. Prerequisites on the target PC

Install on the target Windows PC:

| Requirement | Purpose |
|-------------|---------|
| **Python 3.11+** | Backend (FastAPI). Ensure `python` and `pip` are on PATH. |
| **Node.js 18+** (includes npm) | Build the frontend and/or run dev server. |
| **PostgreSQL** | You are installing this; see section 2. |

Optional for production-style run: a simple static file server (e.g. `npx serve`) to serve the built frontend, or use the Vite dev server.

---

## 2. PostgreSQL (you’re doing this)

- Create the database: **`GYG-CT-Helper`** (or another name; then set `pgDatabase` in backend `.env`).
- Create a user with access to that database; you’ll use it for `pgName` / `pgPassword`.
- Run these SQL scripts **in order** (from `backend/sql/`):

  1. **`cth_auto_allocation_tables.sql`** – schema `CTH`, Auto Allocation tables  
  2. **`migrate_scheduled_po_columns.sql`** – if the Auto Allocation tables already existed without these columns  
  3. **`cth_product_catalogue_tables.sql`** – product catalogue tables  
  4. **`migrate_companyproduct_updated_at.sql`** – if the catalogue tables already existed (adds `updated_at` if missing)  
  5. **`migrate_drop_vendorCode_from_dtl.sql`** – if your detail table still has `vendorCode`  

Use the same DB name, user, and password when configuring the backend (step 5).

---

## 3. What to copy to the target PC

Copy the whole project (or a clean export) so the target PC has at least:

- **`backend/`** – all app code, `requirements.txt`, `sql/`, `.env.example`
- **`frontend/`** – all app code, `package.json`, `package-lock.json` (if present), `.env.example`

You can exclude:

- `backend/venv/` and `frontend/node_modules/` (recreate on the target)
- `.git/` (optional)
- Dev-only files (e.g. `.cursor`, agent transcripts) if you want a lean package

---

## 4. Backend setup and run

On the target PC:

1. Open a terminal and go to the project **backend** folder:
   ```powershell
   cd "C:\path\to\Project SC\backend"
   ```

2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

4. Create `.env` from the example and edit it:
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Set at least:
   - **Crunchtime:** `CT_ENV`, `CRUNCHTIME_LOCATION_TOKEN_TEST`, `CRUNCHTIME_HIERARCHY_TOKEN_TEST`, `CRUNCHTIME_VENDOR_TOKEN_TEST`, `CRUNCHTIME_VENDOR_LOCATION_TOKEN_TEST`, `sitename`, `userid`, `password`
   - **Phase 1 (if using products/POs):** `CRUNCHTIME_COMPANY_PRODUCT_ENHANCED_TOKEN_TEST`, `CRUNCHTIME_VENDOR_PRODUCT_PRICING_TOKEN_TEST`, `CRUNCHTIME_PURCHASE_ORDERS_TOKEN_TEST`, and optionally `CRUNCHTIME_CATEGORY_TOKEN_TEST`
   - **Holidays:** `API_NINJAS_KEY`
   - **PostgreSQL:** `pgName`, `pgPassword`, and if not using defaults: `pgHost`, `pgPort`, `pgDatabase`

5. Run the API (default port 8000):
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   For production you can drop `--reload` and use a process manager or Windows Service (see section 4b).

The API will be at `http://localhost:8000`; docs at `http://localhost:8000/docs`.

---

## 4b. Run the backend as a Windows service (scheduler keeps running)

To keep the backend (and its APScheduler job for scheduled POs) running after logout and across reboots, install it as a Windows service. Two options:

### Option A – NSSM (recommended; no code changes)

**NSSM** (Non-Sucking Service Manager) runs your existing uvicorn command as a service.

1. Download NSSM from [nssm.cc](https://nssm.cc/download) and extract it (e.g. `C:\nssm`).
2. Open **Command Prompt or PowerShell as Administrator**.
3. Install the service (replace paths with your actual paths). Use **nssm.exe** (the executable inside the win64 folder):
   ```powershell
   cd "C:\path\to\Project SC\backend"
   C:\nssm\win64\nssm.exe install ProjectSCBackend "C:\path\to\Project SC\backend\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
   ```
4. Set the working directory so the app and `.env` are found:
   ```powershell
   C:\nssm\win64\nssm.exe set ProjectSCBackend AppDirectory "C:\path\to\Project SC\backend"
   ```
5. Start the service:
   ```powershell
   C:\nssm\win64\nssm.exe start ProjectSCBackend
   ```
   Or use **Services** (Win + R → `services.msc`): find **ProjectSCBackend**, Start, and set Startup type to **Automatic**.

**Useful NSSM commands:** (prefix with your NSSM path, e.g. `C:\GYG\nssm\win64\nssm.exe`)
- `nssm.exe stop ProjectSCBackend` / `nssm.exe start ProjectSCBackend`
- `nssm.exe remove ProjectSCBackend confirm` – remove the service

### Option B – Python Windows service (pywin32)

A script in the repo can register the backend as a native Windows service.

1. In the backend venv, install pywin32:
   ```powershell
   cd "C:\path\to\Project SC\backend"
   .\venv\Scripts\activate
   pip install pywin32
   ```
2. Open **Command Prompt or PowerShell as Administrator**, activate the venv, and install the service:
   ```powershell
   cd "C:\path\to\Project SC\backend"
   .\venv\Scripts\activate
   python scripts\win_service.py install
   ```
3. Start the service:
   ```powershell
   python scripts\win_service.py start
   ```
   Or use **Services** (`services.msc`): **Project SC Backend API** → Start, set to **Automatic** if desired.

**Useful commands:**
- `python scripts\win_service.py stop`
- `python scripts\win_service.py start`
- `python scripts\win_service.py remove` – remove the service

The service runs `uvicorn app.main:app --host 0.0.0.0 --port 8000` with the backend directory as the working directory, so the scheduler (APScheduler) runs inside the same process and keeps running.

---

## 5. Frontend: two options

### Option A – Development server (quick)

In a **second** terminal:

```powershell
cd "C:\path\to\Project SC\frontend"
npm install
copy .env.example .env
notepad .env
```

Set `VITE_API_BASE_URL` to the backend URL (e.g. `http://localhost:8000`). If the frontend runs on another machine, use that machine’s hostname or IP and ensure the backend is started with `--host 0.0.0.0`.

Start the dev server:

```powershell
npm run dev
```

App: **http://localhost:5175** (or the port Vite prints).

### Option B – Production build (single PC or shared folder)

Build once:

```powershell
cd "C:\path\to\Project SC\frontend"
npm install
copy .env.example .env
notepad .env
```

Set `VITE_API_BASE_URL` to the backend URL users will use (e.g. `http://localhost:8000` or `http://THE-PC-NAME:8000`).

```powershell
npm run build
```

Serve the built files, for example:

```powershell
npx serve -s dist -l 5175
```

Or copy the contents of `frontend/dist/` to IIS or any static file server; ensure the server is configured so that `/api` is proxied to the backend if you use the same origin, or keep `VITE_API_BASE_URL` pointing at the backend.

---

## 6. Quick start script (optional)

You can add a batch file on the target PC to start both backend and frontend, e.g. **`start-app.bat`** in the project root:

```batch
@echo off
start "Project SC Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "Project SC Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo Backend and frontend starting. Frontend: http://localhost:5175  Backend: http://localhost:8000
pause
```

Adjust paths and commands if you use a production build (e.g. `npx serve -s dist -l 5175` instead of `npm run dev`).

---

## 7. Checklist

- [ ] Python 3.11+ and Node.js 18+ installed on target PC  
- [ ] PostgreSQL installed; database `GYG-CT-Helper` (or chosen name) created  
- [ ] SQL scripts run in order (section 2)  
- [ ] Project (or backend + frontend) copied to target PC  
- [ ] Backend: `venv` created, `pip install -r requirements.txt`, `.env` configured  
- [ ] Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000` runs without errors  
- [ ] (Optional) Backend installed as Windows service (section 4b) so scheduler runs continuously  
- [ ] Frontend: `npm install`, `.env` with `VITE_API_BASE_URL`, then `npm run dev` or `npm run build` + serve  
- [ ] Browser: open frontend URL (e.g. http://localhost:5175), confirm API and DB (e.g. schedules, locations) work  

---

## Firewall

If other PCs need to reach this one, allow:

- **TCP 8000** – backend API  
- **TCP 5175** – frontend (if using dev server or `serve` on 5175)  

Windows Firewall: “Allow an app” for the relevant Python/Node executables or add inbound rules for these ports.
