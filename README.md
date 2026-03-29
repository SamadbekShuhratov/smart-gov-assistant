# Smart Gov Assistant MVP

Smart Gov Assistant helps residents find the right government services from life situations, not from official service names.

## Implemented MVP Scope

- Life scenario detection from free-text input
- Step-by-step service chain per scenario
- Comparison of similar services (when to choose A vs B)
- Required document checklist
- Multilingual UI and content (English, Russian, Uzbek)
- Clean, modern React + Tailwind interface

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: React + Tailwind (Vite)

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── data.py
│   │   ├── main.py
│   │   └── models.py
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── api.js
    │   ├── i18n.js
    │   ├── index.css
    │   └── main.jsx
    ├── package.json
    └── tailwind.config.js
```

## Run Locally

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Open http://localhost:5173.

## API Overview

### `POST /analyze`

Request:

```json
{
	"query": "Bizda bola tugildi, qanday xizmatlar kerak?"
}
```

Response (example):

```json
{
	"scenario": "birth",
	"steps": [
		{
			"id": 1,
			"title": "Register Birth",
			"description": "Register the newborn at the civil registry and receive a birth certificate.",
			"required_documents": ["Parent IDs", "Hospital birth notice"],
			"estimated_time": "1-2 days"
		}
	],
	"differences": [
		{
			"service1": "Child Benefit",
			"service2": "Maternity Benefit",
			"explanation": "Child Benefit supports child care costs, while Maternity Benefit is for pregnancy and childbirth period income support."
		}
	],
	"recommendations": [
		"Start with birth registration first to unlock all next services."
	],
	"message": ""
}
```

No-match response includes `scenario: "unknown"` and a helpful `message` with guidance.

### `GET /api/scenarios/{scenario_id}?language=en` (legacy helper endpoint)

Returns title, summary, service chain, required documents, and similar-service differences.

## Current Seeded Scenarios (`POST /analyze`)

- `birth`: `bola`, `tugildi`, `birth`, `child`
- `house`: `uy`, `home`, `house`
- `pension`: `nafaqa`, `pension`

## Notes

- Input normalization is applied before matching: lowercase + punctuation removal.
- Matching is deterministic and keyword-based for explainability and quick iteration.
- CORS is open in development for quick frontend/backend integration.