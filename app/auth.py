"""Password login with an HMAC-signed session cookie, plus simple brute-force throttling."""

import hashlib
import hmac
import time

COOKIE_NAME = "lt_session"

# After MAX_FAILURES wrong passwords from one IP, further attempts are refused for LOCKOUT_SECONDS.
MAX_FAILURES = 5
LOCKOUT_SECONDS = 300


def _sign(secret_key: str, payload: str) -> str:
    return hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(secret_key: str, password: str, days: int) -> str:
    expires = int(time.time()) + days * 86400
    # Binding the signature to the password means changing the password logs everyone out.
    return f"{expires}.{_sign(secret_key, f'{expires}:{password}')}"


def verify_token(secret_key: str, password: str, token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expires, signature = token.split(".", 1)
    if not expires.isdigit() or int(expires) < time.time():
        return False
    return hmac.compare_digest(signature, _sign(secret_key, f"{expires}:{password}"))


def check_password(expected: str, given: str) -> bool:
    return hmac.compare_digest(expected.encode(), given.encode())


class LoginThrottle:
    def __init__(self) -> None:
        self._failures: dict[str, tuple[int, float]] = {}

    def locked_for(self, ip: str) -> int:
        """Seconds until this IP may try again (0 = allowed)."""
        count, last = self._failures.get(ip, (0, 0.0))
        if count < MAX_FAILURES:
            return 0
        remaining = LOCKOUT_SECONDS - (time.time() - last)
        if remaining <= 0:
            del self._failures[ip]
            return 0
        return int(remaining) + 1

    def fail(self, ip: str) -> None:
        count, _ = self._failures.get(ip, (0, 0.0))
        self._failures[ip] = (count + 1, time.time())

    def succeed(self, ip: str) -> None:
        self._failures.pop(ip, None)
