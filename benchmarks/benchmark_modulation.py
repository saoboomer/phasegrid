#!/usr/bin/env python3
"""Repeatable synthetic-channel benchmark for PhaseGrid modulation profiles.

This deliberately models only coarse effects (temporal integration, local
spatial mixing, and additive brightness noise). It is not a substitute for
recorded screen-to-camera measurements.
"""
from __future__ import annotations

import argparse
import math

import numpy as np

from phasegrid_modulation import (
    FAST,
    ROBUST,
    decode_payload_from_frames,
    encode_payload_to_frames,
)


def _channel(
    frames: np.ndarray,
    *,
    temporal_passes: int,
    spatial_passes: int,
    noise_sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    result = np.asarray(frames, dtype=np.float32)

    for _ in range(temporal_passes):
        padded = np.pad(result, ((1, 1), (0, 0), (0, 0)), mode="edge")
        result = (
            0.25 * padded[:-2]
            + 0.50 * padded[1:-1]
            + 0.25 * padded[2:]
        )

    for _ in range(spatial_passes):
        padded = np.pad(result, ((0, 0), (1, 1), (1, 1)), mode="edge")
        result = (
            0.60 * padded[:, 1:-1, 1:-1]
            + 0.10 * padded[:, :-2, 1:-1]
            + 0.10 * padded[:, 2:, 1:-1]
            + 0.10 * padded[:, 1:-1, :-2]
            + 0.10 * padded[:, 1:-1, 2:]
        )

    if noise_sigma:
        result = result + rng.normal(0.0, noise_sigma, size=result.shape)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def run(trials: int, payload_bytes: int, seed: int) -> None:
    if trials < 1 or payload_bytes < 1:
        raise ValueError("trials and payload-bytes must be positive")

    rng = np.random.default_rng(seed)
    scenarios = (
        ("clean", 0, 0, 0.0),
        ("mild-camera-model", 1, 1, 0.02),
        ("stronger-camera-model", 1, 1, 0.05),
    )

    legacy_symbol_rate = math.log2(26) / 4.5
    legacy_byte_rate = 8.0 / 9.0
    print(f"Legacy 26-ary upper bound : {legacy_symbol_rate:.3f} bit/s")
    print(f"Legacy two-symbol byte   : {legacy_byte_rate:.3f} bit/s")
    print("All results below are synthetic software-channel measurements.\n")
    print(
        f"{'profile':<9} {'scenario':<25} {'success':>10} "
        f"{'rate(bit/s)':>12} {'video(s)':>10}"
    )
    print("-" * 72)

    for profile in (FAST, ROBUST):
        for name, temporal, spatial, noise in scenarios:
            successes = 0
            duration = 0.0
            for _ in range(trials):
                payload = rng.integers(0, 256, size=payload_bytes, dtype=np.uint8).tobytes()
                frames, metadata = encode_payload_to_frames(payload, profile=profile)
                duration = float(metadata["duration_seconds"])
                received_frames = _channel(
                    np.stack(frames),
                    temporal_passes=temporal,
                    spatial_passes=spatial,
                    noise_sigma=noise,
                    rng=rng,
                )
                try:
                    decoded, _ = decode_payload_from_frames(
                        received_frames, fps=30, profile=profile
                    )
                    successes += decoded == payload
                except Exception:
                    # A failed sync, uncorrectable block, or bad CRC counts as
                    # a failed packet; do not hide it from the packet success rate.
                    pass

            ratio = successes / trials
            print(
                f"{profile.name:<9} {name:<25} {ratio:>9.1%} "
                f"{profile.theoretical_bits_per_second:>12.2f} "
                f"{duration:>10.1f}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--payload-bytes", type=int, default=24)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    run(args.trials, args.payload_bytes, args.seed)


if __name__ == "__main__":
    main()
