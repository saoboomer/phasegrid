"""Re-encode OpenCV mp4v output to H.264 for in-browser preview."""

import os
import shutil
import subprocess
import tempfile


class TranscodeError(Exception):
    pass


def _ffmpeg_executable() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise TranscodeError(
            "ffmpeg not found. Install API deps: pip install -r requirements.txt "
            "(includes imageio-ffmpeg)."
        ) from exc


def transcode_to_h264(src_path: str) -> bytes:
    """Return H.264 MP4 bytes playable in Chrome, Firefox, Safari, Edge."""
    ffmpeg = _ffmpeg_executable()
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
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "baseline",
                "-level",
                "3.0",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-movflags",
                "+faststart",
                out_path,
            ],
            capture_output=True,
            timeout=180,
            text=True,
        )
        if proc.returncode != 0 or not os.path.exists(out_path):
            err = (proc.stderr or proc.stdout or "unknown error")[-500:]
            raise TranscodeError(f"ffmpeg failed: {err}")

        with open(out_path, "rb") as f:
            data = f.read()
        if len(data) < 1000:
            raise TranscodeError("ffmpeg produced an empty file.")
        return data
    except subprocess.TimeoutExpired as exc:
        raise TranscodeError("ffmpeg timed out while transcoding.") from exc
    finally:
        if out_path and os.path.exists(out_path):
            os.unlink(out_path)


def make_browser_playable_mp4(src_path: str) -> bytes:
    """
    OpenCV writes mp4v (MPEG-4 Part 2), which HTML5 <video> rejects.
    Always transcode to H.264 for preview and download.
    """
    return transcode_to_h264(src_path)
