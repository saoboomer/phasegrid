"""PhaseGrid binary multi-dimensional coded modulation (experimental).

Profiles:
- fast: shortened BCH(31,21,5) -> (25,15,>=5), 15 data bits per 2.0 s trajectory.
- robust: shortened BCH(15,11,3) -> (14,10,>=3), 10 data bits per 1.5 s trajectory.

The 26-dimensional optical basis has one unobservable DC/DC component under
per-cell zero-mean normalization. This module leaves coefficient 0 unused and
maps code bits to coefficients 1..n. Every emitted vector has L2 norm 3.0,
matching the energy norm of the legacy 26-ary codebook.

This is an experimental binary packet layer. Its CRC detects accidental
corruption; it is not cryptographic authentication. Use an AEAD envelope for
confidentiality/authenticity. Camera performance must be measured empirically.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations
import hashlib
import math
import os
import sys
import zlib
from typing import Any

import numpy as np

PACKET_MAGIC = b"PGM1"
PACKET_HEADER_BYTES = 9  # magic(4) + profile id(1) + payload length(4)
CRC_BYTES = 4
MAX_PAYLOAD_BYTES = 1_000_000
VECTOR_ENERGY_NORM = 3.0
DC_COMPONENT_INDEX = 0


class ModulationError(Exception):
    """Base class for modulation and packet errors."""


class SyncError(ModulationError):
    """Could not find the optical opening synchronisation burst."""


class UncorrectableBlockError(ModulationError):
    """A received codeword is outside the configured correction search."""


class PacketFormatError(ModulationError):
    """Malformed packet, unsupported profile, or CRC mismatch."""


@dataclass(frozen=True)
class ModulationProfile:
    name: str
    profile_id: int
    n: int
    k: int
    generator: int
    correction_radius: int
    char_seconds: float
    chase_depth: int

    @property
    def parity_bits(self) -> int:
        return self.n - self.k

    @property
    def theoretical_bits_per_second(self) -> float:
        # The 0.5 s delimiter remains part of the legacy optical framing.
        return self.k / (self.char_seconds + 0.5)


FAST = ModulationProfile(
    name="fast",
    profile_id=1,
    n=25,
    k=15,
    generator=0x769,  # BCH(31,21,5), shortened by 6 information bits.
    correction_radius=2,
    char_seconds=2.0,
    chase_depth=8,
)
ROBUST = ModulationProfile(
    name="robust",
    profile_id=2,
    n=14,
    k=10,
    generator=0x13,  # BCH(15,11,3), shortened by 1 information bit.
    correction_radius=1,
    char_seconds=1.5,
    chase_depth=6,
)
PROFILES = {FAST.name: FAST, ROBUST.name: ROBUST}
PROFILES_BY_ID = {profile.profile_id: profile for profile in PROFILES.values()}


@dataclass(frozen=True)
class BlockDecodeResult:
    data: int
    codeword: int
    corrected_errors: int
    soft_margin: float


def get_profile(profile: str | ModulationProfile) -> ModulationProfile:
    if isinstance(profile, ModulationProfile):
        return profile
    try:
        return PROFILES[str(profile).lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown profile {profile!r}; choose fast or robust") from exc


def _poly_mod(value: int, generator: int) -> int:
    """Polynomial remainder over GF(2), with bit i representing x**i."""
    remainder = int(value)
    degree = generator.bit_length() - 1
    while remainder and remainder.bit_length() - 1 >= degree:
        remainder ^= generator << (remainder.bit_length() - 1 - degree)
    return remainder


def encode_information_block(data: int, profile: str | ModulationProfile = FAST) -> int:
    """Systematically encode one k-bit information word into an n-bit word."""
    p = get_profile(profile)
    value = int(data)
    if value < 0 or value >= (1 << p.k):
        raise ValueError(f"data must fit in {p.k} bits")
    parity_degree = p.generator.bit_length() - 1
    if parity_degree != p.parity_bits:
        raise RuntimeError("Profile generator degree does not match n-k")
    shifted = value << parity_degree
    return shifted ^ _poly_mod(shifted, p.generator)


def _syndrome_table(profile: ModulationProfile) -> dict[int, int]:
    table: dict[int, int] = {}
    for weight in range(profile.correction_radius + 1):
        for positions in combinations(range(profile.n), weight):
            error_mask = sum(1 << position for position in positions)
            syndrome = _poly_mod(error_mask, profile.generator)
            previous = table.get(syndrome)
            if previous is not None and previous != error_mask:
                raise RuntimeError(
                    f"{profile.name} syndrome collision at weight {weight}; "
                    "the stated correction radius is invalid"
                )
            table[syndrome] = error_mask
    return table


@lru_cache(maxsize=4)
def _cached_syndrome_table(profile_name: str) -> dict[int, int]:
    return _syndrome_table(get_profile(profile_name))


def _word_bits_lsb(word: int, count: int) -> np.ndarray:
    return np.fromiter(((word >> i) & 1 for i in range(count)), dtype=np.uint8, count=count)


def _bits_to_int_msb(bits: np.ndarray | list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def decode_information_block(
    observations: np.ndarray,
    profile: str | ModulationProfile = FAST,
) -> BlockDecodeResult:
    """Decode soft feature observations with bounded Chase-style list decoding.

    observations[0] is intentionally ignored: it is the unobservable DC/DC mode.
    The sign is the hard decision; |observation| ranks reliability. Candidate
    codewords are generated by flipping up to t least-reliable hard decisions,
    then applying the shortened BCH syndrome decoder. The candidate with the
    highest signed correlation against the soft observations wins.
    """
    p = get_profile(profile)
    vector = np.asarray(observations, dtype=np.float64)
    if vector.ndim != 1 or vector.size < p.n + 1:
        raise ValueError(f"observations must contain at least {p.n + 1} features")
    soft = vector[1 : p.n + 1]
    if not np.all(np.isfinite(soft)):
        raise ValueError("feature observations must be finite")

    hard_bits = (soft > 0).astype(np.uint8)
    received_word = sum(int(bit) << i for i, bit in enumerate(hard_bits))
    reliability_order = np.argsort(np.abs(soft))[: min(p.chase_depth, p.n)]
    table = _cached_syndrome_table(p.name)

    candidates: set[int] = set()
    # Chase-II search: test the hard word and combinations of the least-reliable
    # positions up to the BCH correction radius.
    masks = [0]
    for weight in range(1, p.correction_radius + 1):
        for positions in combinations(reliability_order.tolist(), weight):
            masks.append(sum(1 << int(position) for position in positions))

    for flip_mask in masks:
        trial_word = received_word ^ flip_mask
        error_mask = table.get(_poly_mod(trial_word, p.generator))
        if error_mask is None:
            continue
        corrected = trial_word ^ error_mask
        if _poly_mod(corrected, p.generator) == 0:
            candidates.add(corrected)

    if not candidates:
        raise UncorrectableBlockError(
            f"Could not decode {p.name} block within the configured list search"
        )

    def score(candidate: int) -> float:
        bits = _word_bits_lsb(candidate, p.n).astype(np.float64)
        signs = 2.0 * bits - 1.0
        return float(np.dot(signs, soft))

    ranked = sorted(((score(word), word) for word in candidates), reverse=True)
    best_score, best_word = ranked[0]
    if len(ranked) > 1:
        margin = (best_score - ranked[1][0]) / (float(np.sum(np.abs(soft))) + 1e-12)
    else:
        margin = 1.0

    errors_corrected = (received_word ^ best_word).bit_count()
    data = best_word >> p.parity_bits
    return BlockDecodeResult(
        data=data,
        codeword=best_word,
        corrected_errors=errors_corrected,
        soft_margin=float(max(0.0, min(1.0, margin))),
    )


def _packet_bytes(payload: bytes, profile: ModulationProfile) -> bytes:
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
    body = (
        PACKET_MAGIC
        + bytes([profile.profile_id])
        + len(payload).to_bytes(4, "big")
        + payload
    )
    checksum = (zlib.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big")
    return body + checksum


def _payload_vectors(
    payload: bytes,
    profile: ModulationProfile,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    packet = _packet_bytes(payload, profile)
    stream = np.unpackbits(np.frombuffer(packet, dtype=np.uint8), bitorder="big").tolist()
    padding_bits = (-len(stream)) % profile.k
    stream.extend([0] * padding_bits)

    vectors: list[np.ndarray] = []
    amplitude = VECTOR_ENERGY_NORM / math.sqrt(profile.n)
    for offset in range(0, len(stream), profile.k):
        information = _bits_to_int_msb(stream[offset : offset + profile.k])
        codeword = encode_information_block(information, profile)
        code_bits = _word_bits_lsb(codeword, profile.n)
        vector = np.zeros(26, dtype=np.float64)
        vector[1 : profile.n + 1] = (2.0 * code_bits.astype(np.float64) - 1.0) * amplitude
        vectors.append(vector)

    metadata = {
        "profile": profile.name,
        "profile_id": profile.profile_id,
        "payload_bytes": len(payload),
        "packet_bytes": len(packet),
        "padding_bits": padding_bits,
        "blocks": len(vectors),
        "information_bits_per_block": profile.k,
        "coded_bits_per_block": profile.n,
        "char_seconds": profile.char_seconds,
        "delimiter_seconds": 0.5,
        "theoretical_bits_per_second": profile.theoretical_bits_per_second,
        "coefficient_energy_norm": VECTOR_ENERGY_NORM,
    }
    return vectors, metadata


def encode_payload_to_frames(
    payload: bytes,
    profile: str | ModulationProfile = FAST,
    fps: int = 30,
    cell_px: int = 50,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Render a binary packet using the repository's existing optical renderer."""
    p = get_profile(profile)
    if fps < 10 or fps > 120:
        raise ValueError("fps must be between 10 and 120")
    if cell_px < 8:
        raise ValueError("cell_px must be at least 8")

    from encode import (
        CELL_DEF,
        GRID_N,
        K,
        T_DELIM,
        T_SYNC,
        build_spatial_dct_bases,
        build_temporal_bases,
        compute_fingerprint,
        frame_to_image,
        make_delimiter_frames,
        make_sync_frames,
        render_trajectory,
    )

    vectors, metadata = _payload_vectors(payload, p)
    frame_count_per_block = int(round(p.char_seconds * fps))
    spatial_bases = build_spatial_dct_bases(K, GRID_N)
    temporal_bases = build_temporal_bases(
        K, frame_count_per_block, fps, p.char_seconds
    )

    all_frames: list[np.ndarray] = []
    all_frames.extend(make_sync_frames(fps, T_SYNC))
    for vector in vectors:
        trajectory = render_trajectory(
            vector, spatial_bases, temporal_bases, frame_count_per_block
        )
        all_frames.extend(list(trajectory))
        all_frames.extend(make_delimiter_frames(fps, T_DELIM))
    all_frames.extend(make_sync_frames(fps, 1.0))

    duration_seconds = len(all_frames) / float(fps)
    metadata.update(
        {
            "fps": fps,
            "cell_px": cell_px,
            "frame_count": len(all_frames),
            "duration_seconds": round(duration_seconds, 3),
            "fingerprint": compute_fingerprint(all_frames),
        }
    )
    return all_frames, metadata


def encode_payload_to_video(
    payload: bytes,
    output_path: str,
    profile: str | ModulationProfile = FAST,
    fps: int = 30,
    cell_px: int = 50,
) -> dict[str, Any]:
    """Encode bytes to an MP4 with the same 10x10 grid visual format."""
    import cv2

    from encode import GRID_N, frame_to_image

    frames, metadata = encode_payload_to_frames(payload, profile, fps, cell_px)
    size = GRID_N * cell_px
    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (size, size),
        isColor=False,
    )
    if not writer.isOpened():
        raise ModulationError(f"Could not open video writer for {output_path!r}")
    try:
        for frame in frames:
            writer.write(frame_to_image(frame, cell_px))
    finally:
        writer.release()

    metadata["output_path"] = os.path.abspath(output_path)
    metadata["size_kb"] = round(os.path.getsize(output_path) / 1024.0, 1)
    return metadata


def _find_opening_sync(global_means: np.ndarray, fps: float, threshold: float = 50.0) -> int:
    """Find the end frame of the initial alternating black/white sync burst.

    The legacy detector smooths differences and returns one or two frames late
    for short profiles. This detector uses the first sustained run of raw large
    frame-to-frame differences; the returned index is the first payload frame.
    """
    if global_means.ndim != 1 or global_means.size < 2:
        raise SyncError("Video is too short to contain a synchronisation burst")
    diffs = np.abs(np.diff(global_means * 255.0))
    active = diffs > threshold
    min_run = max(8, int(round(fps * 0.4)))
    for start in range(0, len(active) - min_run + 1):
        if not np.all(active[start : start + min_run]):
            continue
        end = start
        while end < len(active) and active[end]:
            end += 1
        return end
    raise SyncError("Opening sync burst not found; keep the complete video frame")


def _bits_to_bytes(bits: list[int] | np.ndarray) -> bytes:
    values = np.asarray(bits, dtype=np.uint8)
    if values.size % 8:
        raise ValueError("bit count must be a multiple of eight")
    return np.packbits(values, bitorder="big").tobytes()


def _parse_packet(data_bits: list[int], profile: ModulationProfile) -> tuple[bytes, dict[str, Any]]:
    if len(data_bits) < PACKET_HEADER_BYTES * 8:
        raise PacketFormatError("Not enough decoded data to read the packet header")
    header = _bits_to_bytes(data_bits[: PACKET_HEADER_BYTES * 8])
    if header[:4] != PACKET_MAGIC:
        raise PacketFormatError("Packet magic/version mismatch")
    if header[4] != profile.profile_id:
        raise PacketFormatError(
            f"Video uses profile id {header[4]}, but decoder was configured for {profile.name}"
        )

    payload_length = int.from_bytes(header[5:9], "big")
    if payload_length > MAX_PAYLOAD_BYTES:
        raise PacketFormatError("Declared payload length exceeds the configured limit")
    packet_length = PACKET_HEADER_BYTES + payload_length + CRC_BYTES
    required_bits = packet_length * 8
    if len(data_bits) < required_bits:
        raise PacketFormatError(
            f"Incomplete packet: need {required_bits} decoded bits, got {len(data_bits)}"
        )

    packet = _bits_to_bytes(data_bits[:required_bits])
    body = packet[:-CRC_BYTES]
    received_crc = int.from_bytes(packet[-CRC_BYTES:], "big")
    expected_crc = zlib.crc32(body) & 0xFFFFFFFF
    if received_crc != expected_crc:
        raise PacketFormatError("Packet CRC mismatch; optical decoding is unreliable")

    payload = body[PACKET_HEADER_BYTES:]
    stats = {
        "profile": profile.name,
        "payload_bytes": len(payload),
        "packet_bytes": packet_length,
        "blocks_decoded": math.ceil(required_bits / profile.k),
        "crc32_ok": True,
    }
    return payload, stats


def decode_payload_from_cell_signals(
    cell_signals: np.ndarray,
    fps: float,
    profile: str | ModulationProfile = FAST,
) -> tuple[bytes, dict[str, Any]]:
    """Decode a sequence of per-cell brightness values (frames x 100)."""
    p = get_profile(profile)
    signals = np.asarray(cell_signals, dtype=np.float32)
    if signals.ndim != 2 or signals.shape[1] != 100 or signals.shape[0] < 10:
        raise ValueError("cell_signals must have shape (frame_count, 100)")
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive")

    from decode import (
        FPS_DEF,
        GRID_N,
        K,
        T_DELIM,
        build_spatial_dct_bases,
        build_temporal_bases,
        extract_features,
    )

    global_means = signals.mean(axis=1)
    sync_end = _find_opening_sync(global_means, float(fps))

    mean = signals.mean(axis=0, keepdims=True)
    std = signals.std(axis=0, keepdims=True)
    normalized = (signals - mean) / (std + 1e-6)

    actual_frames = int(round(p.char_seconds * fps))
    delimiter_frames = int(round(T_DELIM * fps))
    canonical_frames = int(round(p.char_seconds * FPS_DEF))
    if actual_frames < 8 or delimiter_frames < 1:
        raise ModulationError("Video fps is too low for this modulation profile")

    spatial_bases = build_spatial_dct_bases(K, GRID_N)
    temporal_bases = build_temporal_bases(
        K, canonical_frames, FPS_DEF, p.char_seconds
    )

    data_bits: list[int] = []
    block_errors: list[int] = []
    block_margins: list[float] = []
    position = sync_end

    while position + actual_frames <= signals.shape[0]:
        current_means = global_means[position : position + actual_frames] * 255.0
        global_diffs = np.abs(np.diff(current_means))
        # Closing sync alternates the entire grid on every frame; payload
        # trajectories do not. Detect it by the fraction of large differences.
        if global_diffs.size and np.mean(global_diffs > 80.0) > 0.65:
            break

        window = normalized[position : position + actual_frames]
        observations = extract_features(window, spatial_bases, temporal_bases)
        decoded = decode_information_block(observations, p)
        block_errors.append(decoded.corrected_errors)
        block_margins.append(decoded.soft_margin)
        data_bits.extend(
            (decoded.data >> shift) & 1 for shift in range(p.k - 1, -1, -1)
        )
        position += actual_frames + delimiter_frames

        # The packet header tells us exactly how many code blocks are required.
        if len(data_bits) >= PACKET_HEADER_BYTES * 8:
            header = _bits_to_bytes(data_bits[: PACKET_HEADER_BYTES * 8])
            if header[:4] == PACKET_MAGIC and header[4] == p.profile_id:
                payload_length = int.from_bytes(header[5:9], "big")
                if payload_length <= MAX_PAYLOAD_BYTES:
                    expected_bytes = PACKET_HEADER_BYTES + payload_length + CRC_BYTES
                    expected_blocks = math.ceil(expected_bytes * 8 / p.k)
                    if len(block_errors) >= expected_blocks:
                        break

    payload, packet_stats = _parse_packet(data_bits, p)
    packet_stats.update(
        {
            "sync_end_frame": sync_end,
            "blocks_seen": len(block_errors),
            "blocks_corrected": sum(error > 0 for error in block_errors),
            "corrected_bit_errors": sum(block_errors),
            "mean_soft_margin": (
                float(np.mean(block_margins)) if block_margins else 0.0
            ),
        }
    )
    return payload, packet_stats


def decode_payload_from_frames(
    frames: np.ndarray,
    fps: float = 30.0,
    profile: str | ModulationProfile = "auto",
) -> tuple[bytes, dict[str, Any]]:
    """Decode in-memory 10x10 cell frames; useful for tests and simulations."""
    array = np.asarray(frames, dtype=np.float32)
    if array.ndim != 3 or array.shape[1:] != (10, 10):
        raise ValueError("frames must have shape (frame_count, 10, 10)")
    signals = array.reshape(array.shape[0], 100)
    if profile == "auto":
        failures = []
        for candidate in (FAST, ROBUST):
            try:
                return decode_payload_from_cell_signals(signals, fps, candidate)
            except ModulationError as exc:
                failures.append(f"{candidate.name}: {exc}")
        raise PacketFormatError("No profile decoded this video. " + " | ".join(failures))
    return decode_payload_from_cell_signals(signals, fps, get_profile(profile))


def decode_payload_from_video(
    video_path: str,
    profile: str | ModulationProfile = "auto",
) -> tuple[bytes, dict[str, Any]]:
    """Decode an MP4 using the repository's existing OpenCV cell extractor."""
    from decode import extract_cell_signals, load_frames

    frames, fps, width, height = load_frames(video_path)
    if not frames or width <= 0 or height <= 0:
        raise ModulationError("Video contains no readable frames")
    signals = extract_cell_signals(frames, width, height)

    if profile == "auto":
        failures = []
        for candidate in (FAST, ROBUST):
            try:
                return decode_payload_from_cell_signals(signals, fps, candidate)
            except ModulationError as exc:
                failures.append(f"{candidate.name}: {exc}")
        raise PacketFormatError("No profile decoded this video. " + " | ".join(failures))
    return decode_payload_from_cell_signals(signals, fps, get_profile(profile))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experimental PhaseGrid binary multi-dimensional modulation"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    encode_parser = commands.add_parser("encode", help="Encode UTF-8 text into an optical MP4")
    encode_parser.add_argument("message")
    encode_parser.add_argument("output")
    encode_parser.add_argument("--profile", choices=tuple(PROFILES), default="fast")

    decode_parser = commands.add_parser("decode", help="Decode an optical MP4")
    decode_parser.add_argument("video")
    decode_parser.add_argument("--profile", choices=("auto", *PROFILES), default="auto")
    decode_parser.add_argument("--output", help="Write decoded bytes to this file")

    args = parser.parse_args()
    if args.command == "encode":
        metadata = encode_payload_to_video(
            args.message.encode("utf-8"), args.output, profile=args.profile
        )
        print(metadata)
        return

    payload, metadata = decode_payload_from_video(args.video, profile=args.profile)
    if args.output:
        with open(args.output, "wb") as output_file:
            output_file.write(payload)
        print(f"Wrote {len(payload)} bytes to {args.output}")
    else:
        try:
            print(payload.decode("utf-8"))
        except UnicodeDecodeError:
            print(payload.hex())
    print(metadata)


if __name__ == "__main__":
    main()
