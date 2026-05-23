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

Encoded videos are transcoded to **H.264** (`imageio-ffmpeg`) so they play in the browser preview. Decoding still accepts the downloaded MP4.

## Deploy to Vercel (frontend only)

Vercel hosts the **React UI** in `web/`. The Python API (`numpy`, `opencv`) must run elsewhere (Render, Railway, Fly.io, etc.).

### Fix 404 NOT_FOUND

If Vercel shows `404: NOT_FOUND`, the project was likely built from the repo root (no `index.html` there). Use one of these:

**Option A — Root Directory (recommended)**  
In Vercel → Project → Settings → General:

| Setting | Value |
|---------|--------|
| Root Directory | `web` |
| Framework Preset | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |

**Option B — Repo root**  
A root [`vercel.json`](vercel.json) is included; it builds `web/` and outputs `web/dist`.

### Environment variable

After you deploy the API somewhere, add in Vercel → Settings → Environment Variables:

```
VITE_API_URL = https://your-api-host.example.com
```

Redeploy. Without this, encode/decode API calls will fail (the static site has no `/api` routes).

### Redeploy

Push to GitHub, or in Vercel click **Redeploy** after changing Root Directory / env vars.
