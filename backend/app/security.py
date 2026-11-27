import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + h.hex()


def check_password(password: str, stored: str) -> bool:
    salt_hex, hash_hex = stored.split(":")
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 100_000)
    return hmac.compare_digest(h.hex(), hash_hex)
