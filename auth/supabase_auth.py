from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import keyring

from config import VERCEL_API_URL


CREDENTIAL_SERVICE_NAME = "clicky-animator"
CREDENTIAL_JWT_KEY = "jwt"
AUTH_REQUEST_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class AuthResult:
    success: bool
    token: str = ""
    error: str = ""


def _api_url(path: str) -> str:
    base_url = VERCEL_API_URL.rstrip("/")
    return f"{base_url}{path}"


def _friendly_error(response_json: dict[str, Any], fallback: str) -> str:
    error = response_json.get("error") or response_json.get("message")
    if isinstance(error, str) and error.strip():
        return error.strip()
    return fallback


def _is_jwt_expired(token: str) -> bool:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return True

        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded_payload = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(decoded_payload.decode("utf-8"))
        expires_at = int(claims.get("exp", 0))
        return expires_at <= int(time.time()) + 60
    except Exception:
        return True


async def _post_auth(path: str, email: str, password: str) -> AuthResult:
    if not email.strip():
        return AuthResult(success=False, error="Please enter your email.")
    if not password:
        return AuthResult(success=False, error="Please enter your password.")

    payload = {"email": email.strip(), "password": password}

    try:
        async with httpx.AsyncClient(timeout=AUTH_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(_api_url(path), json=payload)
    except httpx.ConnectError:
        return AuthResult(
            success=False,
            error="Could not connect to Clicky. Check your internet connection.",
        )
    except httpx.TimeoutException:
        return AuthResult(
            success=False,
            error="Clicky took too long to respond. Try again.",
        )
    except httpx.HTTPError:
        return AuthResult(
            success=False,
            error="Clicky could not complete auth right now. Try again.",
        )

    try:
        response_json = response.json()
    except ValueError:
        response_json = {}

    if response.status_code >= 400:
        return AuthResult(
            success=False,
            error=_friendly_error(response_json, "Email or password was not accepted."),
        )

    token = response_json.get("jwt") or response_json.get("token")
    if not isinstance(token, str) or not token.strip():
        return AuthResult(
            success=False,
            error="Clicky signed in, but no session token was returned.",
        )

    try:
        store_jwt(token)
    except keyring.errors.KeyringError:
        return AuthResult(
            success=False,
            error="Could not save your session in Windows Credential Manager.",
        )

    return AuthResult(success=True, token=token)


async def signup(email: str, password: str) -> AuthResult:
    return await _post_auth("/api/auth/signup", email, password)


async def signin(email: str, password: str) -> AuthResult:
    return await _post_auth("/api/auth/signin", email, password)


def store_jwt(token: str) -> None:
    keyring.set_password(CREDENTIAL_SERVICE_NAME, CREDENTIAL_JWT_KEY, token)


def load_jwt() -> str | None:
    try:
        token = keyring.get_password(CREDENTIAL_SERVICE_NAME, CREDENTIAL_JWT_KEY)
    except keyring.errors.KeyringError:
        return None
    if not token or _is_jwt_expired(token):
        return None
    return token


def clear_jwt() -> None:
    try:
        keyring.delete_password(CREDENTIAL_SERVICE_NAME, CREDENTIAL_JWT_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    except keyring.errors.KeyringError:
        pass


def has_valid_jwt() -> bool:
    return load_jwt() is not None


def auth_headers() -> dict[str, str]:
    token = load_jwt()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}

