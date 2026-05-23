"""FastAPI bridge for PhaseGrid encode/decode."""

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from adapter import AdapterError, MAX_UPLOAD_BYTES, SEED_DEF, decode_video, encode_video

app = FastAPI(
    title="PhaseGrid API",
    description="Optical credential encoder/decoder bridge",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Fingerprint", "X-Duration-Sec", "X-Size-Kb"],
)


class EncodeRequest(BaseModel):
    text: str
    seed: int = Field(default=SEED_DEF, ge=0)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/encode")
def api_encode(body: EncodeRequest):
    try:
        video_bytes, fingerprint, duration_sec, size_kb = encode_video(
            body.text, seed=body.seed
        )
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "X-Fingerprint": fingerprint,
                "X-Duration-Sec": str(duration_sec),
                "X-Size-Kb": str(size_kb),
                "Content-Disposition": 'attachment; filename="phasegrid.mp4"',
            },
        )
    except AdapterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Encoding failed.") from exc


@app.post("/api/decode")
async def api_decode(
    file: UploadFile = File(...),
    seed: int = Form(default=SEED_DEF),
):
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(
            status_code=400,
            detail="Upload an .mp4 video file.",
        )

    content_type = file.content_type or ""
    if content_type and content_type not in ("video/mp4", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Use video/mp4.",
        )

    try:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="File too large (max 50 MB).")
        return decode_video(file_bytes, seed=seed)
    except AdapterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Decoding failed.") from exc
