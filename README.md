# PhaseGrid Web UI

Production web interface for the PhaseGrid optical credential encoder/decoder. Cryptographic logic lives in `encode.py` and `decode.py` — unchanged. The UI talks to them through a thin FastAPI adapter.

## Prerequisites

- Python 3 with `numpy` and `opencv-python` (required by encode/decode)
- Node.js 18+

## Run (development)

From the **repo root** (not inside `web/` alone):

```bash
npm install
npm run install:all
npm run dev
```

That starts the API on port **8000** and the UI on **http://localhost:5173**.

Or run separately:

```bash
# Terminal 1
npm run dev:api

# Terminal 2
npm run dev:web
```

**API deps** (required for in-browser video preview):

```bash
pip install -r requirements.txt
```

`imageio-ffmpeg` bundles ffmpeg and transcodes output to H.264 so `<video>` preview works.

## Usage

1. **Encode:** Enter A–Z text → **Generate video** → preview plays in-browser → **Download MP4**.
2. **Decode:** Upload that MP4 (drag-and-drop or browse) → **Decode message** → read the recovered text.
3. **Advanced:** Toggle seed if you changed it during encode (must match for decode).

## Project layout

```
backend/      FastAPI bridge (adapter only)
api/          Vercel serverless proxy to backend (TypeScript only)
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

## Deploy to production (Vercel + Render)

The **UI** goes on Vercel. The **API** must run on a Python host (we recommend [Render](https://render.com)) because encode/decode need OpenCV.

### Step 1 — Deploy the API on Render (required)

1. Push this repo to GitHub.
2. [Render](https://dashboard.render.com) → **New** → **Blueprint** → connect repo → uses [`render.yaml`](render.yaml).
3. Wait until **phasegrid-api** is live. Test: `https://phasegrid-api.onrender.com/api/health` should return `{"status":"ok"}`.

If that URL returns **404**, the API is not deployed yet — Vercel cannot encode/decode until this works.

### Step 2 — Vercel frontend

1. Import the repo in Vercel (repo root is fine).
2. Optional env var if your Render URL differs:

   ```
   PHASEGRID_API_URL = https://phasegrid-api.onrender.com
   ```

3. Redeploy.

[`vercel.json`](vercel.json) proxies `/api/*` to Render and sets `VITE_API_URL` at build time. [`api/[...path].ts`](api/[...path].ts) is the serverless fallback proxy.

### Why you saw 405

Vercel was sending `POST /api/encode` to the static SPA (`index.html`), which returns **405 Method Not Allowed**. The proxy + `VITE_API_URL` fixes route traffic to the real API.

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
