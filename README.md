# PhaseGrid Web UI

Production web interface for the PhaseGrid optical credential encoder/decoder. Cryptographic logic lives in `encode.py` and `decode.py` — unchanged. The UI talks to them through a thin FastAPI adapter.

## Prerequisites

- Python 3 with `numpy` and `opencv-python` (required by encode/decode)
- Node.js 18+

## Run (development)

**Terminal 1 — API** (from repo root):

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Web UI**:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

## Usage

1. **Encode:** Enter A–Z text → **Generate video** → preview plays in-browser → **Download MP4**.
2. **Decode:** Upload that MP4 (drag-and-drop or browse) → **Decode message** → read the recovered text.
3. **Advanced:** Toggle seed if you changed it during encode (must match for decode).

## Project layout

```
api/          FastAPI bridge (adapter only)
web/          React + Vite + Tailwind SPA
encode.py     Encoder (do not modify)
decode.py     Decoder (do not modify)
```

## API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/encode` | POST JSON `{ text, seed }` | Returns raw `video/mp4` with metadata headers |
| `/api/decode` | POST multipart `file` + `seed` | Returns `{ message, fingerprint, charCount, avgConfidence }` |
| `/api/health` | GET | Health check |
