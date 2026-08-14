# AgriVision AI

**One farmer, one application—complete crop and livestock health visibility.**

AgriVision AI is a complete, local-first hackathon platform that brings crop disease screening, practical crop advice, livestock health monitoring, medical records, vaccination reminders, alerts, and farm analytics into one farmer-friendly application.

The supplied crop model is not trained or embedded here. It connects through a replaceable inference adapter. Until that artifact arrives, deterministic demo mode keeps the entire workflow—including image upload, persistence, advice, history, and alerts—working offline.

## Problem

Marginal farmers often have to navigate separate agricultural and veterinary tools, inconsistent connectivity, and limited specialist access. AgriVision combines the most frequent crop and animal-health workflows in one low-bandwidth interface while being explicit that AI screening is preliminary guidance, not a substitute for a qualified agricultural officer or veterinarian.

## What works

- Secure registration, login, logout, and seeded demo account
- Multiple farms and crop cycles
- Validated JPG/PNG crop upload with local compression
- Mock, PyTorch/TorchScript, and Keras model adapters behind one result contract
- Top-three predictions, calibrated confidence wording, and low-confidence escalation
- Offline JSON crop advisory knowledge base
- Saved diagnosis history and crop analytics
- Livestock registry, health observations, and explainable JSON-driven risk scoring
- Medical timeline and vaccination reminders
- Automatic crop and animal-health alerts
- Dashboard KPIs and Plotly charts
- English interface plus Hindi and Tamil navigation examples
- Local SQLite storage and no required external services
- REST API and interactive OpenAPI documentation

## Architecture

```text
Farmer browser
    │
    ▼
Streamlit UI ── authenticated HTTP ──► FastAPI
                                         │
                 ┌───────────────────────┼────────────────────────┐
                 ▼                       ▼                        ▼
          SQLAlchemy / SQLite     Advisory & risk rules    Crop model adapter
          farms, crops, animals   local JSON knowledge     mock / PyTorch / Keras
                 │                                                │
                 └──────── local uploads and records ─────────────┘
```

The Streamlit layer contains presentation only. FastAPI owns authorization and workflows. SQLAlchemy relationships preserve farmer-level data boundaries. Model-specific tensors stop at `PredictionResult`; everything else consumes normalized labels, confidences, top predictions, version, and inference time.

## Technology

- Python 3.11+
- Streamlit and Plotly
- FastAPI, Pydantic, Uvicorn
- SQLAlchemy 2 and SQLite (change `DATABASE_URL` for PostgreSQL later)
- Pillow and NumPy
- bcrypt password hashing and signed JWT access tokens
- pytest and FastAPI TestClient

## Quick start

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\seed_database.py
python run.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_database.py
python run.py
```

Open [http://localhost:8501](http://localhost:8501). `run.py` seeds missing demo data, starts the API and interface, opens the browser, and stops both processes together on Ctrl+C.

### Run services separately

Terminal 1:

```bash
python -m uvicorn backend.main:app --reload
```

Terminal 2:

```bash
python -m streamlit run frontend/app.py
```

- Farmer interface: [http://localhost:8501](http://localhost:8501)
- API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

## Demo account

```text
Email: farmer@example.com
Password: demo123
```

The seed is idempotent and immediately provides Ravi Kumar, Green Valley Farm, three active crops, seven animals, medical history, vaccination tasks, a historical diagnosis, and two dashboard alerts.

## Environment variables

Copy `.env.example` to `.env`.

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./agri_vision.db` |
| `MODEL_PATH` | Supplied crop-model file or directory | `./models/crop_model.pt` |
| `MODEL_TYPE` | `pytorch` or `keras` | `pytorch` |
| `CLASS_NAMES_PATH` | Ordered model output labels | `./ml/class_names.json` |
| `USE_MOCK_MODEL` | Use deterministic demonstration inference | `true` |
| `IMAGE_SIZE` | Model input height/width | `224` |
| `MAX_UPLOAD_MB` | Backend upload limit | `8` |
| `SECRET_KEY` | JWT signing key; change outside local demo | development value |
| `API_BASE_URL` | URL used by Streamlit | `http://localhost:8000` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:8501` |

## Supplied model integration

1. Place the artifact at `models/crop_model.pt` or set `MODEL_PATH` to its location.
2. Put labels in `ml/class_names.json` in exact output-index order.
3. Add or alias those labels in `knowledge/crop_diseases.json`.
4. Install the model framework separately (PyTorch is deliberately not a large core dependency).
5. Set `USE_MOCK_MODEL=false` and the correct `MODEL_TYPE`.
6. Restart the application and confirm `/health` reports `model_loaded: true` and `mock_mode: false`.

Detailed artifact formats, preprocessing assumptions, state-dict handling, and Hugging Face extension guidance are in [ml/README_MODEL.md](ml/README_MODEL.md).

The default preprocessing resizes to `IMAGE_SIZE` and scales RGB pixels to `[0,1]`; it does not guess training normalization. Match the supplied model's documented preprocessing before real use.

## Hackathon demo flow

1. Sign in with the demo account and show the dashboard: 3 crops, 7 animals, and 2 active alerts.
2. Open **Check Crop**, select Green Valley Farm and Tomato, and upload any valid leaf JPG/PNG.
3. Demo mode returns Tomato Early Blight at 94.6% confidence with moderate severity.
4. Show immediate actions, prevention, urgency, and expert-escalation advice.
5. Save it, then open **Diagnosis History** to prove persistence.
6. Open **Animals & Health** and choose Lakshmi (`COW-101`).
7. In Health Observations enter 40.2 °C, Low appetite, and Low activity.
8. Save to produce score 7, High risk, veterinary guidance, and a new critical dashboard alert.

## API overview

| Area | Endpoints |
|---|---|
| System | `GET /health` |
| Authentication | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Farms | `GET/POST /farms`, `GET/PUT /farms/{id}` |
| Crops | `GET/POST /crops`, `GET /crops/{id}` |
| Diagnosis | `POST /diagnosis/predict`, `POST /diagnosis/save`, `GET /diagnosis/history`, `GET /diagnosis/{id}` |
| Livestock | `GET/POST /livestock`, `GET/PUT /livestock/{id}` |
| Animal care | observation, history, medical-record, and vaccination routes under `/livestock/{id}` |
| Alerts | `GET /alerts`, `PATCH /alerts/{id}/read` |
| Dashboard | `GET /dashboard/summary` |

Every farmer-data endpoint requires `Authorization: Bearer <token>`.

## Folder structure

```text
backend/             FastAPI routes, configuration, ORM models, schemas, services
frontend/            Streamlit app, farmer pages, shared UI, API client, translations
knowledge/           Crop advice, animal rules, and vaccination schedules
ml/                  Framework adapters, preprocessing, normalized inference contract
data/uploads/        Validated and compressed local images (gitignored)
scripts/             Idempotent demo database seeding
tests/               Unit and end-to-end API tests
models/              Supplied model location (artifacts gitignored)
run.py                One-command local launcher
```

## Tests

```bash
python -m pytest -q
```

Tests cover password-based authentication, API health, end-to-end crop prediction and persistence, adapter normalization, advisory mapping, low-confidence escalation, livestock score 7/high-risk behavior, vaccination due-date windows, and alert generation.

## Offline and safety behavior

- Core workflows use only the local database, local rules, and local inference.
- Uploaded files are extension checked, decoded as images, renamed with random identifiers, bounded to 8 MB, compressed, and never executed.
- Low-confidence crop results explicitly request expert verification.
- Chemical advice never provides hazardous dosing and directs farmers to approved labels or officers.
- Animal output is preliminary screening and clearly does not claim a veterinary diagnosis.
- User-facing errors avoid stack traces; server logs retain diagnostic detail.

## Screenshots

Add final presentation captures here after running on the target display:

- `docs/screenshots/dashboard.png`
- `docs/screenshots/crop-analysis.png`
- `docs/screenshots/animal-health.png`

## Future improvements

- Connect the supplied, validated crop model and its exact preprocessing
- Complete translations of all domain content and add voice guidance
- PostgreSQL migrations with Alembic for multi-device deployment
- Background vaccination-alert refresh and optional SMS delivery
- Role-based agricultural/veterinary expert review
- Optional record-grounded LLM assistant behind a disabled-by-default service
- Grad-CAM overlays for compatible vision architectures
- PWA/offline capture synchronization if a web client is later added

