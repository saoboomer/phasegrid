import pytest

from phasegrid_security import (
    AuthenticationError,
    PayloadFormatError,
    ReplayDetected,
    SQLiteReplayLedger,
    bytes_to_phasegrid_letters,
    decrypt_text,
    encrypt_text,
)


def test_byte_symbol_mapping_round_trip():
    raw = bytes(range(256))
    from phasegrid_security import _letters_to_bytes_and_erasures
    decoded, erasures = _letters_to_bytes_and_erasures(bytes_to_phasegrid_letters(raw))
    assert decoded == raw
    assert erasures == []


def test_byte_mapping_marks_unrepresentable_pair_as_erasure():
    from phasegrid_security import _letters_to_bytes_and_erasures
    decoded, erasures = _letters_to_bytes_and_erasures("ZA")
    assert len(decoded) == 1
    assert erasures == [0]


def test_crypto_round_trip_and_replay(tmp_path):
    pytest.importorskip("reedsolo")
    ledger = SQLiteReplayLedger(tmp_path / "replay.sqlite3")
    payload = encrypt_text("Hello, secure PhaseGrid!", "a unique passphrase with entropy")
    assert decrypt_text(payload, "a unique passphrase with entropy", ledger) == "Hello, secure PhaseGrid!"
    with pytest.raises(ReplayDetected):
        decrypt_text(payload, "a unique passphrase with entropy", ledger)


def test_wrong_passphrase_is_rejected(tmp_path):
    pytest.importorskip("reedsolo")
    payload = encrypt_text("secret", "correct passphrase with entropy")
    ledger = SQLiteReplayLedger(tmp_path / "replay.sqlite3")
    with pytest.raises(AuthenticationError):
        decrypt_text(payload, "wrong passphrase with entropy", ledger)


def test_modified_payload_is_rejected(tmp_path):
    pytest.importorskip("reedsolo")
    payload = encrypt_text("secret", "correct passphrase with entropy")
    changed = ("B" if payload[10] != "B" else "C")
    tampered = payload[:10] + changed + payload[11:]
    ledger = SQLiteReplayLedger(tmp_path / "replay.sqlite3")
    with pytest.raises((AuthenticationError, PayloadFormatError)):
        decrypt_text(tampered, "correct passphrase with entropy", ledger)


def test_fec_corrects_bounded_symbol_error(tmp_path):
    pytest.importorskip("reedsolo")
    ledger = SQLiteReplayLedger(tmp_path / "replay.sqlite3")
    payload = encrypt_text("correctable optical noise", "correct horse battery staple 2026")
    # Alter one valid A-Z symbol; RS should repair the resulting byte error.
    changed = "A" if payload[20] != "A" else "B"
    noisy = payload[:20] + changed + payload[21:]
    assert decrypt_text(noisy, "correct horse battery staple 2026", ledger) == "correctable optical noise"


def test_replay_ledger_requires_persistent_storage():
    with pytest.raises(ValueError):
        SQLiteReplayLedger(":memory:")
