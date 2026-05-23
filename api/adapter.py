"""Thin wrappers around encode/decode — no crypto logic here."""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from encode import ALPHABET, SEED_DEF, T_CHAR, T_DELIM, T_SYNC, encode  # noqa: E402
from decode import decode  # noqa: E402
from transcode import make_browser_playable_mp4  # noqa: E402

_ALPHABET_SET = set(ALPHABET)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class AdapterError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _validate_plaintext(text: str) -> str:
    if not text or not text.strip():
        raise AdapterError("Message cannot be empty.", 422)
    upper = text.upper()
    chars = [c for c in upper if c in _ALPHABET_SET]
    if not chars:
        raise AdapterError("No encodable characters (A–Z only).", 400)
    invalid = {c for c in upper if c not in _ALPHABET_SET and c != " "}
    if invalid:
        raise AdapterError(
            f"Unsupported characters: {''.join(sorted(invalid))}. Use A–Z only.",
            400,
        )
    return upper


def encode_video(text: str, seed: int = SEED_DEF) -> tuple[bytes, str, float, float]:
    """Wrap encode() → raw MP4 bytes + metadata."""
    _validate_plaintext(text)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                _frames, fingerprint = encode(
                    text,
                    seed=seed,
                    output=tmp_path,
                    preview=False,
                    verbose=False,
                )
            except SystemExit as exc:
                raise AdapterError("Encoding failed.", 500) from exc

        video_bytes = make_browser_playable_mp4(tmp_path)

        if not video_bytes:
            raise AdapterError("Encoder produced empty output.", 500)

        chars = [c for c in text.upper() if c in _ALPHABET_SET]
        duration_sec = T_SYNC + len(chars) * (T_CHAR + T_DELIM) + 1.0

        return (
            video_bytes,
            fingerprint,
            round(duration_sec, 1),
            round(len(video_bytes) / 1024, 1),
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def decode_video(file_bytes: bytes, seed: int = SEED_DEF) -> dict:
    """Wrap decode() ← uploaded MP4 bytes."""
    if not file_bytes:
        raise AdapterError("No video file provided.", 422)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise AdapterError("File too large (max 50 MB).", 400)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                message, results = decode(
                    tmp_path,
                    seed=seed,
                    show_signal=False,
                    show_preview=False,
                )
            except SystemExit as exc:
                raise AdapterError("Decoding failed.", 500) from exc

        if not message:
            raise AdapterError("Decoder returned empty message.", 500)

        avg_conf = (
            sum(r["confidence"] for r in results) / len(results) if results else 0.0
        )
        fp = hashlib.sha256(message.encode()).hexdigest()

        return {
            "message": message,
            "fingerprint": fp,
            "charCount": len(results),
            "avgConfidence": round(avg_conf, 3),
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
