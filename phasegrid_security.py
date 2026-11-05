"""Authenticated envelope for PhaseGrid's A-Z optical symbol channel.

The optical encoder remains a transport layer. This module provides:
- Argon2id password-based key derivation (fresh salt per message)
- AES-256-GCM confidentiality and authenticated integrity
- Reed-Solomon RS(255,239) error correction over encrypted bytes
- Strict A-Z pair encoding compatible with the existing 26-symbol alphabet
- Persistent replay rejection using an atomic SQLite primary-key insert

The receiver releases plaintext only after FEC decoding, AEAD verification, and
successful persistence of the replay token.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Protocol

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"PGS2"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
TAG_BYTES = 16
HEADER_BYTES = len(MAGIC) + SALT_BYTES + NONCE_BYTES
REPLAY_TOKEN_BYTES = SALT_BYTES + NONCE_BYTES
RS_PARITY_BYTES = 16
RS_MAX_DATA_BYTES = 255 - RS_PARITY_BYTES
MAX_PLAINTEXT_BYTES = RS_MAX_DATA_BYTES - HEADER_BYTES - TAG_BYTES  # 191 bytes

# RFC 9106 memory-constrained Argon2id profile: 64 MiB, 3 passes, 4 lanes.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 65_536
ARGON2_PARALLELISM = 4


class PhaseGridSecurityError(Exception):
    """Base class for secure-transport errors."""


class PayloadFormatError(PhaseGridSecurityError):
    """Malformed or unsupported secure payload."""


class AuthenticationError(PhaseGridSecurityError):
    """Wrong passphrase or modified authenticated payload."""


class ReplayDetected(PhaseGridSecurityError):
    """This authenticated transmission has already been accepted."""


class ReplayStoreError(PhaseGridSecurityError):
    """Replay state could not be durably persisted."""


class FECUnavailable(PhaseGridSecurityError):
    """The reedsolo dependency is missing."""


class ReplayLedger(Protocol):
    def claim(self, token: bytes) -> None:
        """Atomically persist a token once; raise ReplayDetected on duplicates."""


class SQLiteReplayLedger:
    """Persistent, single-host replay ledger.

    The database must live on durable storage. For multi-instance deployments,
    replace this with shared storage providing an atomic unique constraint.
    """

    def __init__(self, database_path: str | os.PathLike[str]) -> None:
        raw_path = os.fspath(database_path)
        if raw_path == ":memory:":
            raise ValueError("Replay protection requires persistent storage")
        self.path = Path(raw_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.path, timeout=30) as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS accepted_messages (
                        replay_token BLOB PRIMARY KEY,
                        accepted_at INTEGER NOT NULL
                    )"""
                )
        except sqlite3.Error as exc:
            raise ReplayStoreError("Could not initialize replay storage") from exc

    def claim(self, token: bytes) -> None:
        if len(token) != REPLAY_TOKEN_BYTES:
            raise ValueError("Invalid replay-token length")
        try:
            with sqlite3.connect(
                self.path, timeout=30, isolation_level="IMMEDIATE"
            ) as connection:
                connection.execute(
                    "INSERT INTO accepted_messages(replay_token, accepted_at) VALUES (?, ?)",
                    (sqlite3.Binary(token), int(time.time())),
                )
        except sqlite3.IntegrityError as exc:
            raise ReplayDetected("This video has already been accepted") from exc
        except sqlite3.Error as exc:
            # Fail closed: no plaintext if replay state cannot be committed.
            raise ReplayStoreError("Could not persist replay state") from exc


def _rs_codec():
    try:
        from reedsolo import RSCodec
    except ImportError as exc:
        raise FECUnavailable(
            "Secure mode requires reedsolo; install backend requirements"
        ) from exc
    return RSCodec(RS_PARITY_BYTES)


def _validate_passphrase(passphrase: str) -> bytes:
    if not isinstance(passphrase, str):
        raise ValueError("A passphrase is required")
    encoded = passphrase.encode("utf-8")
    if len(encoded) < 14:
        raise ValueError("Use a unique passphrase of at least 14 UTF-8 bytes")
    if len(encoded) > 1024:
        raise ValueError("Passphrase is too long")
    return encoded


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=_validate_passphrase(passphrase),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Type.ID,
        version=19,
    )


def bytes_to_phasegrid_letters(data: bytes) -> str:
    """Map each byte to two A-Z symbols; the pair uniquely represents 0..255."""
    output = bytearray(2 * len(data))
    for index, value in enumerate(data):
        high, low = divmod(value, 26)
        output[2 * index] = 65 + high
        output[2 * index + 1] = 65 + low
    return output.decode("ascii")


def _letters_to_bytes_and_erasures(letters: str) -> tuple[bytes, list[int]]:
    if not isinstance(letters, str) or len(letters) % 2:
        raise PayloadFormatError("Optical payload must contain an even number of A-Z symbols")
    try:
        raw = letters.encode("ascii")
    except UnicodeEncodeError as exc:
        raise PayloadFormatError("Payload contains non-ASCII symbols") from exc
    if any(symbol < 65 or symbol > 90 for symbol in raw):
        raise PayloadFormatError("Payload must contain only uppercase A-Z symbols")

    output = bytearray(len(raw) // 2)
    erasures: list[int] = []
    for index in range(0, len(raw), 2):
        high = raw[index] - 65
        low = raw[index + 1] - 65
        value = high * 26 + low
        byte_index = index // 2
        if value > 255:
            # Mark impossible pairs as erasures so RS can reconstruct them.
            output[byte_index] = 0
            erasures.append(byte_index)
        else:
            output[byte_index] = value
    return bytes(output), erasures


def encrypt_bytes(plaintext: bytes, passphrase: str) -> str:
    """AEAD-encrypt bytes, add RS parity, and return A-Z symbols.

    FEC is applied after encryption: it repairs bounded channel errors, while
    AES-GCM remains the authority for authenticity and integrity.
    """
    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise ValueError(
            f"Secure messages are limited to {MAX_PLAINTEXT_BYTES} UTF-8 bytes"
        )

    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    header = MAGIC + salt + nonce
    key = _derive_key(passphrase, salt)
    encrypted = AESGCM(key).encrypt(nonce, plaintext, header)
    envelope = header + encrypted

    codeword = bytes(_rs_codec().encode(envelope))
    return bytes_to_phasegrid_letters(codeword)


def decrypt_bytes(
    encoded_letters: str,
    passphrase: str,
    replay_ledger: ReplayLedger,
) -> bytes:
    """FEC-decode, authenticate, reject replays, then return plaintext."""
    if replay_ledger is None:
        raise ValueError("A persistent replay ledger is required")

    codeword, erasures = _letters_to_bytes_and_erasures(encoded_letters)
    if not (HEADER_BYTES + TAG_BYTES + RS_PARITY_BYTES
            <= len(codeword) <= 255):
        raise PayloadFormatError("Invalid secure payload length")

    try:
        decoded = _rs_codec().decode(
            codeword,
            erase_pos=erasures if erasures else None,
        )
        envelope = bytes(decoded[0] if isinstance(decoded, tuple) else decoded)
    except FECUnavailable:
        raise
    except Exception as exc:
        # Reed-Solomon may reject an uncorrectable codeword. Never pass it on.
        raise PayloadFormatError("Optical errors exceed the correction capacity") from exc

    if len(envelope) < HEADER_BYTES + TAG_BYTES:
        raise PayloadFormatError("Secure envelope is too short")
    if envelope[:len(MAGIC)] != MAGIC:
        raise PayloadFormatError("Unknown secure-envelope version")

    header = envelope[:HEADER_BYTES]
    cursor = len(MAGIC)
    salt = envelope[cursor:cursor + SALT_BYTES]
    cursor += SALT_BYTES
    nonce = envelope[cursor:cursor + NONCE_BYTES]
    ciphertext_and_tag = envelope[HEADER_BYTES:]

    key = _derive_key(passphrase, salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext_and_tag, header)
    except InvalidTag:
        raise AuthenticationError(
            "Authentication failed: wrong passphrase or modified payload"
        ) from None

    # Salt+nonce uniquely identifies this independently-derived message key
    # and nonce pair. The DB insert is atomic and committed before plaintext.
    replay_ledger.claim(salt + nonce)
    return plaintext


def encrypt_text(plaintext: str, passphrase: str) -> str:
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be text")
    return encrypt_bytes(plaintext.encode("utf-8"), passphrase)


def decrypt_text(
    encoded_letters: str,
    passphrase: str,
    replay_ledger: ReplayLedger,
) -> str:
    plaintext = decrypt_bytes(encoded_letters, passphrase, replay_ledger)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PayloadFormatError("Authenticated payload is not valid UTF-8") from exc
