"""Version 1 envelope: strict limits, authenticated header and two DEK wrappers."""
import base64
import binascii
import json
import secrets
import uuid
from dataclasses import dataclass, field

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import InvalidVault, VaultError

MAX_FILE = 16 * 1024 * 1024
MIN_MASTER_PASSWORD = 8
MAX_MASTER_PASSWORD = 128
KDF = {"name": "argon2id", "memory": 65536, "time": 3, "parallelism": 4}


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidVault()
        result[key] = value
    return result


def parse(data: bytes):
    if len(data) > MAX_FILE:
        raise InvalidVault()
    try:
        return json.loads(data, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(InvalidVault()))
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidVault() from None


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value, size=None) -> bytes:
    try:
        if not isinstance(value, str):
            raise InvalidVault()
        result = base64.b64decode(value, validate=True)
        if size is not None and len(result) != size:
            raise InvalidVault()
        return result
    except (ValueError, binascii.Error):
        raise InvalidVault() from None


def validate_password(password: str):
    if not isinstance(password, str) or not MIN_MASTER_PASSWORD <= len(password) <= MAX_MASTER_PASSWORD:
        raise VaultError(f"Мастер-пароль должен содержать от {MIN_MASTER_PASSWORD} до {MAX_MASTER_PASSWORD} символов.")


def derive(password: str, salt: bytes) -> bytes:
    validate_password(password)
    return hash_secret_raw(password.encode("utf-8"), salt, time_cost=3,
                           memory_cost=65536, parallelism=4, hash_len=32, type=Type.ID, version=19)


def recovery_secret() -> str:
    return base64.b32encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def recovery_bytes(secret: str) -> bytes:
    try:
        if not isinstance(secret, str) or len(secret) != 52:
            raise InvalidVault()
        raw = base64.b32decode(secret.upper() + "====")
        if len(raw) != 32 or base64.b32encode(raw).decode().rstrip("=") != secret.upper():
            raise InvalidVault()
        return raw
    except (ValueError, binascii.Error):
        raise InvalidVault() from None


def seal(key: bytes, plaintext: bytes, aad: bytes) -> dict:
    nonce = secrets.token_bytes(12)
    return {"nonce": b64(nonce), "ciphertext": b64(AESGCM(key).encrypt(nonce, plaintext, aad))}


def unseal(key, box, aad):
    if not isinstance(box, dict) or set(box) != {"nonce", "ciphertext"}:
        raise InvalidVault()
    try:
        return AESGCM(key).decrypt(unb64(box["nonce"], 12), unb64(box["ciphertext"]), aad)
    except (InvalidTag, ValueError):
        raise InvalidVault() from None


@dataclass(repr=False)
class Access:
    header: dict
    key: bytes = field(repr=False)

    @classmethod
    def create(cls, password: str, recovery: str | None = None, vault_id: str | None = None, epoch: int = 1):
        recovery = recovery or recovery_secret()
        salt = secrets.token_bytes(16)
        key = secrets.token_bytes(32)
        base = {"format": "PMVAULT", "version": 1, "vault_id": vault_id or str(uuid.uuid4()),
                "epoch": epoch, "kdf": dict(KDF), "salt": b64(salt)}
        aad = canonical(base)
        return cls({**base, "master": seal(derive(password, salt), key, aad + b"/master"),
                    "recovery": seal(recovery_bytes(recovery), key, aad + b"/recovery")}, key), recovery

    def encode(self, document: dict) -> bytes:
        data = canonical({"header": self.header, "payload": seal(self.key, canonical(document), canonical(self.header))})
        if len(data) > MAX_FILE:
            raise VaultError("Хранилище превышает допустимый размер 16 МиБ.")
        return data

    def decode(self, data: bytes) -> dict:
        envelope = checked_envelope(data)
        if envelope["header"] != self.header:
            raise InvalidVault()
        doc = parse(unseal(self.key, envelope["payload"], canonical(self.header)))
        if not isinstance(doc, dict):
            raise InvalidVault()
        return doc

    def change_password(self, password: str):
        salt = secrets.token_bytes(16)
        base = {k: v for k, v in self.header.items() if k not in ("master", "recovery")}
        base["salt"] = b64(salt)
        # Recovery wrapper authenticates the original base, so preserve its base explicitly.
        recovery_box = self.header["recovery"]
        recovery_base = self.header.get("recovery_base") or {k: v for k, v in self.header.items() if k not in ("master", "recovery", "recovery_base")}
        base.pop("recovery_base", None)
        return Access({**base, "recovery_base": recovery_base, "recovery": recovery_box,
                       "master": seal(derive(password, salt), self.key, canonical(base) + b"/master")}, self.key)


def checked_envelope(data: bytes) -> dict:
    obj = parse(data)
    if not isinstance(obj, dict) or set(obj) != {"header", "payload"}:
        raise InvalidVault()
    h = obj["header"]
    required = {"format", "version", "vault_id", "epoch", "kdf", "salt", "master", "recovery"}
    if not isinstance(h, dict) or set(h) not in (required, required | {"recovery_base"}):
        raise InvalidVault()
    if h["format"] != "PMVAULT" or type(h["version"]) is not int or h["version"] != 1 or h["kdf"] != KDF:
        raise InvalidVault()
    if type(h["epoch"]) is not int or not 1 <= h["epoch"] <= 2**31:
        raise InvalidVault()
    try:
        if str(uuid.UUID(h["vault_id"])) != h["vault_id"]:
            raise InvalidVault()
    except (ValueError, TypeError, AttributeError):
        raise InvalidVault() from None
    unb64(h["salt"], 16)
    return obj


def unlock(data: bytes, secret: str, *, recovery=False) -> tuple[Access, dict]:
    obj = checked_envelope(data)
    h = obj["header"]
    base = {k: v for k, v in h.items() if k not in ("master", "recovery", "recovery_base")}
    if recovery:
        key = unseal(recovery_bytes(secret), h["recovery"], canonical(h.get("recovery_base", base)) + b"/recovery")
    else:
        key = unseal(derive(secret, unb64(h["salt"], 16)), h["master"], canonical(base) + b"/master")
    if len(key) != 32:
        raise InvalidVault()
    access = Access(h, key)
    return access, access.decode(data)
