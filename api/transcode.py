"""Re-encode OpenCV mp4v output to H.264 for in-browser preview."""

import os
import shutil
import subprocess
import tempfile


def _ffmpeg_executable() -> str | None:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def transcode_to_h264(src_path: str) -> bytes | None:
    """Return H.264 MP4 bytes, or None if transcoding failed."""
    ffmpeg = _ffmpeg_executable()
    if not ffmpeg:
        return None

    out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            out_path = tmp.name

        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                src_path,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "baseline",
                "-level",
                "3.0",
                "-movflags",
                "+faststart",
                "-an",
                out_path,
            ],
            capture_output=True,
            timeout=180,
        )
        if proc.returncode != 0 or not os.path.exists(out_path):
            return None

        with open(out_path, "rb") as f:
            data = f.read()
        return data if len(data) > 1000 else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        if out_path and os.path.exists(out_path):
            os.unlink(out_path)


def make_browser_playable_mp4(src_path: str) -> bytes:
    """
    OpenCV writes mp4v (MPEG-4 Part 2), which HTML5 video elements reject.
    Transcode to H.264; if that fails, return the original bytes (download/decode still work).
    """
    transcoded = transcode_to_h264(src_path)
    if transcoded:
        return transcoded

    with open(src_path, "rb") as f:
        return f.read()
