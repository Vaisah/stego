#!/usr/bin/python3
# -*- encoding: utf-8 -*-
"""Shared cryptographic primitives for the file encryption tool.

Container format (self-describing, "STG1"):

    magic(4)='STG1' | version(1) | algo(1) | salt(16) | nonce_prefix(4) |
    chunk_size(4, big-endian u32) | name_len(2, big-endian u16) | name(name_len)

followed by a sequence of chunks, each:

    ct_len(4, big-endian u32) | ciphertext

Key derivation is PBKDF2-HMAC-SHA256 (600k iterations) over a random 16-byte
per-file salt stored in the header. Each chunk is authenticated and bound to its
position with additional-authenticated-data ``struct.pack(">Q?", index, last)``,
which defeats chunk reordering, duplication and truncation.

``decrypt_dispatch`` also transparently reads the *legacy* Fernet-per-chunk format
produced by earlier versions of the tool (detected when the magic bytes are absent).
"""

import base64
import hashlib
import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"STG1"
VERSION = 1

ALGO_AES_GCM = 1
ALGO_CHACHA = 2
ALGO_FERNET = 3

# Accepted algorithm form values -> internal id
ALGO_NAMES = {
    "aes-256-gcm": ALGO_AES_GCM,
    "aes256gcm": ALGO_AES_GCM,
    "aes": ALGO_AES_GCM,
    "chacha20-poly1305": ALGO_CHACHA,
    "chacha20": ALGO_CHACHA,
    "chacha": ALGO_CHACHA,
    "fernet": ALGO_FERNET,
}
ALGO_LABELS = {
    ALGO_AES_GCM: "AES-256-GCM",
    ALGO_CHACHA: "ChaCha20-Poly1305",
    ALGO_FERNET: "Fernet",
}

PBKDF2_ITERATIONS = 600_000
SALT_LEN = 16
NONCE_PREFIX_LEN = 4
HEADER_FIXED_LEN = 32  # bytes up to and including name_len
CHUNK_SIZE = 64 * 1024  # plaintext chunk size
AAD = struct.Struct(">Q?")  # (chunk_index, is_last)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Exceptions raised when a key is wrong or the ciphertext was tampered with.
DecryptError = (InvalidTag, InvalidToken, ValueError)


def resolve_algo(name, default=ALGO_AES_GCM):
    """Map a user-supplied algorithm name to an internal id."""
    if not name:
        return default
    return ALGO_NAMES.get(str(name).strip().lower(), default)


def derive_key(passphrase, salt, length=32):
    """PBKDF2-HMAC-SHA256 key derivation."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def _make_aead(algo_id, key):
    if algo_id == ALGO_AES_GCM:
        return AESGCM(key)
    if algo_id == ALGO_CHACHA:
        return ChaCha20Poly1305(key)
    return None  # Fernet handled separately


def _fernet_for(key):
    return Fernet(base64.urlsafe_b64encode(key))


def _read_exact(read_fn, n):
    """Read exactly ``n`` bytes or raise ValueError on truncation."""
    buf = bytearray()
    while len(buf) < n:
        chunk = read_fn(n - len(buf))
        if not chunk:
            raise ValueError("Truncated ciphertext")
        buf.extend(chunk)
    return bytes(buf)


def pack_header(algo_id, salt, nonce_prefix, filename):
    name_bytes = (filename or "").encode("utf-8")[:65535]
    return (
        MAGIC
        + bytes([VERSION, algo_id])
        + salt
        + nonce_prefix
        + struct.pack(">I", CHUNK_SIZE)
        + struct.pack(">H", len(name_bytes))
        + name_bytes
    )


def encrypt_generator(stream, passphrase, algo_id, filename):
    """Yield the STG1 header then framed, authenticated ciphertext chunks.

    ``stream`` only needs a ``.read(n)`` method, so the upload is never fully
    buffered in memory.
    """
    salt = os.urandom(SALT_LEN)
    nonce_prefix = os.urandom(NONCE_PREFIX_LEN)
    key = derive_key(passphrase, salt)
    aead = _make_aead(algo_id, key)
    fernet = _fernet_for(key) if algo_id == ALGO_FERNET else None

    yield pack_header(algo_id, salt, nonce_prefix, filename)

    index = 0
    prev = stream.read(CHUNK_SIZE)
    while True:
        nxt = stream.read(CHUNK_SIZE)
        last = len(nxt) == 0
        aad = AAD.pack(index, last)
        if aead is not None:
            nonce = nonce_prefix + struct.pack(">Q", index)
            ct = aead.encrypt(nonce, prev, aad)
        else:
            ct = fernet.encrypt(aad + prev)
        yield struct.pack(">I", len(ct)) + ct
        index += 1
        if last:
            break
        prev = nxt


def _iter_raw_chunks(read_fn):
    """Yield raw ciphertext chunks framed as u32-length + bytes."""
    while True:
        lenb = read_fn(4)
        if len(lenb) == 0:
            return
        if len(lenb) != 4:
            raise ValueError("Truncated chunk length")
        clen = struct.unpack(">I", lenb)[0]
        yield _read_exact(read_fn, clen)


def decrypt_dispatch(stream, passphrase):
    """Return a generator yielding plaintext, auto-selecting new/legacy format.

    Reads the first 4 bytes to decide: STG1 => new container, otherwise the
    bytes are treated as the first little-endian chunk length of the legacy
    Fernet-per-chunk format. Raises on truncation; per-chunk auth failures are
    raised lazily while iterating (the caller should validate the first chunk).
    """
    read_fn = stream.read
    sig = read_fn(4)
    if len(sig) < 4:
        raise ValueError("File too short to be a valid encrypted file")

    if sig == MAGIC:
        return _new_format_generator(read_fn, passphrase)
    return _legacy_generator(read_fn, passphrase, first_len_bytes=sig)


def _new_format_generator(read_fn, passphrase):
    rest = _read_exact(read_fn, HEADER_FIXED_LEN - 4)
    header = MAGIC + rest
    algo_id = header[5]
    salt = header[6:22]
    nonce_prefix = header[22:26]
    name_len = struct.unpack(">H", header[30:32])[0]
    if name_len:
        _read_exact(read_fn, name_len)

    key = derive_key(passphrase, salt)
    aead = _make_aead(algo_id, key)
    fernet = _fernet_for(key) if algo_id == ALGO_FERNET else None

    chunks = _iter_raw_chunks(read_fn)
    index = 0
    prev_ct = next(chunks, None)
    if prev_ct is None:
        return
    while True:
        try:
            nxt_ct = next(chunks)
            last = False
        except StopIteration:
            nxt_ct = None
            last = True
        aad = AAD.pack(index, last)
        if aead is not None:
            nonce = nonce_prefix + struct.pack(">Q", index)
            yield aead.decrypt(nonce, prev_ct, aad)
        else:
            full = fernet.decrypt(prev_ct)
            if full[:AAD.size] != aad:
                raise InvalidToken("Chunk order mismatch")
            yield full[AAD.size:]
        index += 1
        if last:
            break
        prev_ct = nxt_ct


def legacy_fernet_key(passphrase):
    """Reproduce the weak key derivation used by the original tool."""
    _key = hashlib.md5(passphrase.encode()).hexdigest()
    return base64.urlsafe_b64encode(_key.encode())


def _legacy_generator(read_fn, passphrase, first_len_bytes):
    """Legacy format: <u32 little-endian len><fernet token> repeated."""
    fernet = Fernet(legacy_fernet_key(passphrase))
    clen = struct.unpack("<I", first_len_bytes)[0]
    token = _read_exact(read_fn, clen)
    yield fernet.decrypt(token)
    while True:
        lenb = read_fn(4)
        if len(lenb) == 0:
            return
        if len(lenb) != 4:
            raise ValueError("Truncated legacy chunk length")
        clen = struct.unpack("<I", lenb)[0]
        token = _read_exact(read_fn, clen)
        yield fernet.decrypt(token)
