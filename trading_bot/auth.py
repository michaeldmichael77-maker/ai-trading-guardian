"""Password protection for the whole app.

When the app is exposed to the internet (e.g. on Render), it MUST require a
login — otherwise anyone who finds the URL could control your trading. This adds
a single-password gate:

  * Set your password in the GUARDIAN_PASSWORD environment variable.
  * A signed session cookie is issued on successful login (no password stored
    in the cookie; it's an HMAC token that can't be forged without the secret).
  * Every request except the login page/endpoint and health check is blocked
    until logged in.

If GUARDIAN_PASSWORD is NOT set, the app runs UNLOCKED (fine for your own
computer, unsafe for the internet) and prints a loud warning.
"""

import hashlib
import hmac
import os
import time

COOKIE_NAME = "guardian_session"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days


def get_password():
    return os.environ.get("GUARDIAN_PASSWORD", "")


def _secret():
    # Derive a signing secret from the password (+ optional explicit secret) so
    # tokens invalidate if the password changes.
    base = os.environ.get("GUARDIAN_SECRET", "") + "|" + get_password()
    return hashlib.sha256(base.encode()).digest()


def is_enabled():
    return bool(get_password())


def make_token():
    """Create a signed session token: '<expiry>.<hmac>'."""
    expiry = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def verify_token(token):
    if not token or "." not in token:
        return False
    expiry, sig = token.rsplit(".", 1)
    expected = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        return int(expiry) > time.time()
    except ValueError:
        return False


def check_password(candidate):
    pw = get_password()
    if not pw:
        return False
    return hmac.compare_digest(candidate or "", pw)
