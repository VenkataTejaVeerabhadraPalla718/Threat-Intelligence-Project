"""Dependency-light security helpers (no database or web framework imports).

Kept separate so they can be unit-tested without MongoDB or FastAPI.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone

from config import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

try:  # Argon2id is preferred; the legacy PBKDF2 path keeps old accounts working.
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHashError, VerificationError
    _ph = PasswordHasher()
except ImportError:  # pragma: no cover - exercised only when argon2-cffi is absent
    _ph = None

USERNAME_RE = re.compile(r"[A-Za-z0-9_.-]{3,40}")
LEGACY_ITERATIONS = 100_000


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Username must be 3-40 characters using letters, digits, dot, underscore or hyphen.")
    return username


def validate_password(password: str, username: str = "") -> None:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must contain at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must not exceed {PASSWORD_MAX_LENGTH} characters.")
    if username and username.lower() in password.lower():
        raise ValueError("Password must not contain the username.")
    if password.strip() == "" or len(set(password)) < 4:
        raise ValueError("Password is too simple. Use a more varied passphrase.")


def argon2_available() -> bool:
    return _ph is not None


def hash_pw(password: str, salt: str | None = None) -> str:
    """Hash a password. New hashes use Argon2id when available.

    The optional ``salt`` argument is kept only for backward compatibility with
    callers of the original helper; it forces the legacy PBKDF2 format.
    """
    if salt is None and _ph is not None:
        return _ph.hash(password)
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), LEGACY_ITERATIONS).hex()


def verify_pw(password: str, stored: str) -> tuple[bool, bool]:
    """Return (is_valid, needs_rehash)."""
    if not stored or not isinstance(stored, str):
        return False, False
    if stored.startswith("$argon2"):
        if _ph is None:
            return False, False
        try:
            _ph.verify(stored, password)
            return True, _ph.check_needs_rehash(stored)
        except (VerificationError, InvalidHashError):
            return False, False
    if "$" in stored:  # legacy "salt$hexdigest"
        salt = stored.split("$", 1)[0]
        ok = hmac.compare_digest(hash_pw(password, salt), stored)
        return ok, ok and _ph is not None
    return False, False


def check_pw(password: str, stored: str) -> bool:
    """Backward-compatible boolean check."""
    return verify_pw(password, stored)[0]


_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """Neutralise spreadsheet formula injection in exported cells."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    if text and text[0] in _DANGEROUS:
        return "'" + text
    return text


def parse_day(value: str | None, end_of_day: bool = False):
    """Parse YYYY-MM-DD (or full ISO) into an aware UTC datetime; None if blank."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("Dates must use YYYY-MM-DD format.")
    if len(value.strip()) <= 10 and end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_locked_out(recent_failures: int, max_failures: int) -> bool:
    return recent_failures >= max_failures
