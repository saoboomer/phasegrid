import numpy as np
import pytest

from phasegrid_modulation import (
    FAST,
    ROBUST,
    PacketFormatError,
    _bits_to_bytes,
    _packet_bytes,
    _parse_packet,
    _payload_vectors,
    decode_information_block,
    decode_payload_from_frames,
    encode_information_block,
    encode_payload_to_frames,
    get_profile,
)


def _observations_from_codeword(data: int, profile):
    word = encode_information_block(data, profile)
    bits = np.array([(word >> i) & 1 for i in range(profile.n)], dtype=np.uint8)
    observations = np.zeros(26, dtype=np.float64)
    observations[1 : profile.n + 1] = np.where(bits > 0, 1.0, -1.0)
    return observations


def _temporal_blur(frames: np.ndarray, passes: int = 1) -> np.ndarray:
    result = np.asarray(frames, dtype=np.float64)
    for _ in range(passes):
        padded = np.pad(result, ((1, 1), (0, 0), (0, 0)), mode="edge")
        result = 0.25 * padded[:-2] + 0.5 * padded[1:-1] + 0.25 * padded[2:]
    return result


def _noisy_camera_copy(frames: np.ndarray, seed: int = 19) -> np.ndarray:
    blurred = _temporal_blur(frames, passes=1)
    rng = np.random.default_rng(seed)
    noisy = blurred + rng.normal(0.0, 0.02, size=blurred.shape)
    return np.clip(noisy, 0.0, 1.0).astype(np.float32)


@pytest.mark.parametrize(
    "profile,data,flips",
    [
        (FAST, 0x3A5B, (2, 17)),
        (ROBUST, 0x2A5, (4,)),
    ],
)
def test_bch_decoder_corrects_the_advertised_error_radius(profile, data, flips):
    observations = _observations_from_codeword(data, profile)
    for bit_index in flips:
        observations[bit_index + 1] *= -1.0
    decoded = decode_information_block(observations, profile)
    assert decoded.data == data
    assert decoded.corrected_errors == len(flips)


def test_dc_component_is_not_used_and_energy_norm_is_preserved():
    vectors, metadata = _payload_vectors(b"PhaseGrid modulation", FAST)
    assert all(vector[0] == 0.0 for vector in vectors)
    assert all(np.linalg.norm(vector) == pytest.approx(3.0, abs=1e-10) for vector in vectors)
    assert metadata["coded_bits_per_block"] == 25
    assert metadata["information_bits_per_block"] == 15


def test_profiles_have_the_expected_throughput():
    assert FAST.theoretical_bits_per_second == pytest.approx(6.0)
    assert ROBUST.theoretical_bits_per_second == pytest.approx(5.0)
    assert get_profile("fast") is FAST
    assert get_profile("robust") is ROBUST


@pytest.mark.parametrize("profile", [FAST, ROBUST])
def test_full_optical_frame_round_trip(profile):
    payload = b"PhaseGrid v2: binary coded modulation."
    frames, metadata = encode_payload_to_frames(payload, profile=profile, fps=30)
    decoded, stats = decode_payload_from_frames(np.stack(frames), fps=30, profile=profile)
    assert decoded == payload
    assert stats["crc32_ok"] is True
    assert stats["blocks_seen"] == metadata["blocks"]


@pytest.mark.parametrize("profile", [FAST, ROBUST])
def test_round_trip_with_temporal_blur_and_sensor_noise(profile):
    payload = b"camera channel regression payload"
    frames, _ = encode_payload_to_frames(payload, profile=profile, fps=30)
    noisy_frames = _noisy_camera_copy(np.stack(frames))
    decoded, stats = decode_payload_from_frames(
        noisy_frames, fps=30, profile=profile
    )
    assert decoded == payload
    assert stats["crc32_ok"] is True


def test_crc_rejects_a_modified_packet():
    packet = bytearray(_packet_bytes(b"integrity check", FAST))
    packet[10] ^= 0x01  # modify payload while leaving the transmitted CRC unchanged
    bits = np.unpackbits(np.frombuffer(bytes(packet), dtype=np.uint8), bitorder="big").tolist()
    with pytest.raises(PacketFormatError, match="CRC mismatch"):
        _parse_packet(bits, FAST)


def test_binary_packet_payload_limit_is_enforced():
    with pytest.raises(ValueError, match="exceeds"):
        _packet_bytes(b"x" * (1_000_001), FAST)
