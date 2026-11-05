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

## Experimental binary multi-dimensional modulation

The repository now includes an **optional research CLI** in
\`phasegrid_modulation.py\`. It leaves the legacy A-Z encoder, decoder, and web
UI unchanged.

### Profiles

| Profile | Code | Information bits / trajectory | Trajectory + delimiter | Ideal payload rate |
|---|---|---:|---:|---:|
| \`fast\` | Shortened BCH(31,21,5) → (25,15,≥5) | 15 | 2.0 s + 0.5 s | 6.0 bit/s |
| \`robust\` | Shortened BCH(15,11,3) → (14,10,≥3) | 10 | 1.5 s + 0.5 s | 5.0 bit/s |

The 26-dimensional basis has one DC/DC component that is removed by the
existing decoder's per-cell zero-mean normalization. The new modulation leaves
that component unused and maps code bits onto the remaining basis components.
Each transmitted coefficient vector has L2 norm 3.0, matching the legacy
codebook's coefficient energy.

Both profiles use bounded Chase-style soft list decoding around their BCH
hard-decision decoder. The FAST profile corrects up to two hard bit errors per
block; ROBUST corrects one. CRC-32 checks packet integrity against accidental
decoding errors. CRC is **not** cryptographic authentication.

The new binary preamble holds each full-grid sync level for two frames (7.5 Hz
at 30 fps), instead of toggling on every frame at the 30 fps Nyquist limit.
The decoder expects the complete two-second opening preamble.

### Use the CLI

From the repository root:

\`\`\`bash
python phasegrid_modulation.py encode "HELLO PHASEGRID" hello-fast.mp4 --profile fast
python phasegrid_modulation.py decode hello-fast.mp4 --profile auto
\`\`\`

Use \`--profile robust\` when camera exposure or temporal integration is
expected to be less favourable. \`auto\` tries both profiles and accepts only a
packet with a matching profile id and valid CRC.

### Throughput interpretation

The ideal coded rates are 6.0 bit/s (FAST) and 5.0 bit/s (ROBUST), compared
with the legacy 26-ary symbol-channel upper bound of
\`log2(26) / 4.5 ≈ 1.04 bit/s\`. A raw byte stream represented as two A-Z
symbols per byte carries 8 bits in 9 seconds (0.89 bit/s). These are framing
calculations, not measured camera throughput.

Run the software-only channel benchmark with:

\`\`\`bash
python benchmarks/benchmark_modulation.py --trials 20
\`\`\`

The benchmark applies synthetic temporal blur, spatial mixing, and sensor
noise. Its results are repeatable engineering checks, **not camera evidence**.
Real screen-to-camera recordings are still required to measure BER, packet
error rate, false acceptance, synchronization tolerance, and the actual
throughput on target devices.

The new CLI is not yet wired into the FastAPI endpoints or React UI. The
existing application continues using the legacy A-Z profile until the new
channel has been validated and integrated deliberately.
