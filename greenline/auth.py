"""Authentication and password security for Greenline Pharmacy.

The client specifically asked that passwords be protected so staff and
competitors cannot read sensitive supplier pricing (Appendix 1 point 7).
To honour that, passwords are never stored or compared in plain text. Instead
each password is run through PBKDF2-HMAC-SHA256 with a unique random salt and
many iterations, and only the resulting hash plus the salt are saved. Verifying
a login re-hashes the typed password with the stored salt and compares hashes.
"""

import hashlib
import hmac
import os

# Number of hashing rounds. A high count makes brute-forcing a stolen hash slow
# while staying instant for a single login.
_PBKDF2_ITERATIONS = 200_000


def hash_password(password, salt=None):
    """Return a (hash_hex, salt_hex) pair for the given password.

    If no salt is supplied a fresh 16-byte random salt is generated, which is
    what happens when a brand-new account is created. Passing an existing salt
    is how verify_password reproduces a stored hash.
    """
    if salt is None:
        # os.urandom gives cryptographically strong random bytes for the salt.
        salt = os.urandom(16)
    elif isinstance(salt, str):
        # When checking a login the salt arrives as hex text from the database,
        # so convert it back to raw bytes first.
        salt = bytes.fromhex(salt)

    # Derive the hash from the UTF-8 encoded password and the salt.
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return derived.hex(), salt.hex()


def verify_password(password, salt_hex, expected_hash_hex):
    """Return True if "password" hashes (with the stored salt) to the stored
    hash. hmac.compare_digest is used for a constant-time comparison so an
    attacker cannot learn the hash by timing the check."""
    candidate_hash, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(candidate_hash, expected_hash_hex)


def authenticate(db, username, password):
    """Look the user up by name and verify the password. Returns the full user
    row (a dict) on success or None on any failure (unknown user or wrong
    password). The caller treats None as "invalid credentials"."""
    user = db.fetch_one(
        "SELECT * FROM users WHERE username = %s", (username,)
    )
    if user is None:
        return None
    if verify_password(password, user["salt"], user["password_hash"]):
        return user
    return None


def create_user(db, username, password, full_name, role="representative"):
    """Create a new staff account with a freshly salted+hashed password and
    return its new user_id."""
    import datetime

    pw_hash, salt = hash_password(password)
    return db.execute(
        "INSERT INTO users (username, password_hash, salt, full_name, role, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (username, pw_hash, salt, full_name, role, datetime.datetime.now()),
    )
