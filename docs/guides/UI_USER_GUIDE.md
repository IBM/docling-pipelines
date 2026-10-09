# Docpipe UI User Guide

> **⚠️ Beta notice:** The web UI is experimental and **not production-ready**. It is under active
> development and may change significantly between releases. For production workloads use the CLI,
> Python API (`DocpipeFlowManager`), or REST API instead.

The Docpipe web UI is a visual tool for building, running, and monitoring document processing pipelines.
It is served by the FastAPI backend and is accessible at `/ui` on whichever host you have deployed Docpipe to.

- **Development**: `http://localhost:3000/ui`
- **Wheel / Docker**: `http://localhost:8080/ui`
- **OpenShift / Kubernetes**: `https://<your-route-host>/ui`

---

## Navigation

The application header contains four primary navigation items:

| Item | URL pattern | Purpose |
|------|-------------|---------|
| **Home** | `/ui/home` | Overview dashboard — recent projects, flows, and runs |
| **Projects** | `/ui/projects` | Manage projects and their flows |
| **Canvas** | `/ui/canvas/:flowId` | Visual pipeline editor (opened from a flow) |
| **Runs** | (accessible from a project) | Job run history and status |

---

## Pages

### Home

The Home page provides an at-a-glance overview with three summary cards:

- **Projects card** — lists your most recently modified projects.
- **Flows card** — lists your most recently modified flows across all projects.
- **Runs card** — lists recent job runs and their status.

Click any item in a card to navigate directly to it.

---

### Projects

The Projects page lists all projects. A **project** is a logical container for one or more pipelines (flows).

**Creating a project**

Click **Create project** in the top-right corner of the page. Enter a name and an optional description. The project appears in the list immediately after creation.

**Opening a project**

Click on any project card to open its detail view, which shows the flows that belong to it.

**Editing or deleting a project**

Use the overflow menu (⋮) on the project card to rename, edit the description, or delete the project.

---

### Project detail — Flows

Inside a project you see the list of flows. A **flow** is a directed pipeline of operators: it defines which operators run, in what order, and with what configuration.

**Creating a flow**

Click **Create flow**. Enter a name and optional description. The flow is saved to the project.

**Opening a flow in the canvas**

Click on any flow card to open the visual canvas editor for that flow.

**Editing or deleting a flow**

Use the overflow menu (⋮) on the flow card.

---

### Canvas

The Canvas is the visual pipeline editor. It opens when you click a flow.

#### Operator palette

The left panel lists all available operators grouped by category (Ingest, Extract, Functional, Quality, VectorDB, Storage). Drag an operator from the palette onto the canvas to add it to your pipeline.

#### Building a pipeline

1. **Add operators**: drag them from the palette onto the canvas.
2. **Connect operators**: drag from the output port of one operator to the input port of the next. Pipelines must have exactly one root operator (an ingest node with no incoming connections).
3. **Configure an operator**: double-click a node (or right-click → **Edit**) to open the properties panel on the right. Fill in the operator's parameters and click **Save**.
4. **Delete a node or link**: select it and press Delete, or use the right-click context menu.

#### Running a pipeline

Click **Run** in the canvas toolbar. The pipeline is submitted to the backend as a job. A notification appears when the run starts. Click **View run** (or navigate to the Runs page) to follow progress.

#### Flow run history

Click the **Flow run history** button in the toolbar to see all past runs for this flow with their status and duration.

#### About flow

Click **About flow** in the toolbar to view and edit the flow name and description without leaving the canvas.

---

### Runs

The Runs page (accessible from within a project) lists all job runs for that project. Each row shows:

- **Flow name**
- **Status** — `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`
- **Start time** and **duration**

Click any row to open the **Run details** page, which shows per-operator status, document counts, and error messages.

---

## Concepts

| Term | Meaning |
|------|---------|
| **Project** | A logical container for one or more flows |
| **Flow** | A directed acyclic graph (DAG) of operators that defines a pipeline |
| **Operator** | A single processing step (ingest, extract, chunk, embed, store, etc.) |
| **Node** | An operator instance placed on the canvas |
| **Link** | A connection between two nodes that defines data flow |
| **Job run** | A single execution of a flow |

---

## Typical workflow

```
1. Create a project
2. Create a flow inside the project
3. Open the flow in the canvas
4. Drag an Ingest operator onto the canvas and configure the file path or source
5. Add downstream operators (Extract, Chunker, Embeddings, VectorDB)
6. Connect them in order
7. Click Run
8. Monitor progress on the Runs page
```

---

## Troubleshooting

Symptoms can have different causes depending on how you started the UI. Find your deployment mode below.

---

### Local dev (`npm run dev`)

**Blank page or nothing loads at `http://localhost:3000/ui`**

- Check that both processes started: the terminal running `npm run dev` should show output from both `BFF` and `VITE` prefixes.
- Check that `frontend/.env` exists. If not, run `cp .env.example .env` from the `frontend/` directory and restart.
- Check that `BACKEND_API_URL` in `frontend/.env` points to where FastAPI is actually running (default: `http://localhost:8080`).

**Canvas shows no operators in the palette**

The browser cannot reach the backend API through the BFF. Open the browser developer console (F12) and check for errors on the Network tab.

- `net::ERR_CONNECTION_REFUSED` on `/api/*` — the BFF is not running. Check the `BFF` prefix output in the terminal; if it exited, re-run `npm run dev`.
- `404` from the BFF — the FastAPI backend is not running. Start it: `uvicorn docpipe.api.main:app --host 0.0.0.0 --port 8080`.
- CORS errors — the FastAPI backend is running on a different port than `BACKEND_API_URL` in `frontend/.env`.

**BFF exits immediately with `BACKEND_API_URL is not set`**

`frontend/.env` is missing or empty. Run `cp .env.example .env` from the `frontend/` directory.

---

### Wheel install (`uvicorn docpipe.api.main:app`)

**UI not accessible at `http://localhost:8080/ui`**

The frontend assets were not bundled into the wheel. Rebuild them manually and restart:
```bash
cd frontend && npm install && npm run build
python scripts/build_frontend.py
uvicorn docpipe.api.main:app --host 0.0.0.0 --port 8080
```

**Canvas shows no operators — backend logs show "BFF not started: node not found"**

`node` is not in `PATH`. Install Node.js (any version ≥ 18) and ensure it is on the system `PATH`, then restart the server.

**Canvas shows no operators — backend logs show "BFF not started: bff/server.cjs not found"**

The BFF bundle was not included in the wheel. Run `python scripts/build_frontend.py` from the project root to rebuild the assets and bundle, then restart.

---

### Docker Compose

**A service is not healthy**

```bash
docker compose -f docker/all-in-one-deployment/docker-compose.yml ps
docker compose -f docker/all-in-one-deployment/docker-compose.yml logs bff
docker compose -f docker/all-in-one-deployment/docker-compose.yml logs docpipe
```

**Canvas shows no operators after the stack is healthy**

The `docpipe` container depends on `bff` being healthy before it starts. If the BFF container restarted after `docpipe` came up, FastAPI may have lost its BFF URL. Restart the `docpipe` container:
```bash
docker compose -f docker/all-in-one-deployment/docker-compose.yml restart docpipe
```

---

### OpenShift / Kubernetes

**UI route returns 502 or connection refused**

Check that the BFF pod is running and healthy, and that `BFF_URL` is set correctly on the backend deployment:
```bash
oc get pods -l app=docpipe-bff
oc logs deployment/docpipe-bff
oc get env deployment/docpipe-backend | grep BFF_URL
```

---

### All modes

**A run stays in PENDING forever**

The backend started the job but an operator cannot reach an external service. Check the FastAPI logs for connection errors to Ollama, OpenSearch, or other configured services.

**Page loads but all API calls return 401 Unauthorized**

Authentication is not yet enforced in the UI. If you are seeing 401 responses, the backend JWT configuration may be misconfigured. Check `JWT_SECRET_KEY` in your `.env` file.
