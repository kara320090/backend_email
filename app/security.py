import base64
import hashlib
import hmac
import json
import time

from .config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def create_unsubscribe_token(subscriber_id: int) -> str:
    payload = {
        "subscriber_id": subscriber_id,
        "exp": int(time.time()) + 60 * 60 * 24 * 365,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_bytes)

    signature = hmac.new(
        settings.unsubscribe_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    signature_part = _b64url_encode(signature)
    return f"{payload_part}.{signature_part}"


def verify_unsubscribe_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid token format") from exc

    expected_signature = hmac.new(
        settings.unsubscribe_secret.encode("utf-8"),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    actual_signature = _b64url_decode(signature_part)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("invalid token signature")

    payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))

    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")

    return payload