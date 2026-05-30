from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from auth import supabase_auth
from config import VERCEL_API_URL


class PaywallError(Exception):
    pass


class AuthError(Exception):
    pass


class NetworkError(Exception):
    pass


REQUEST_TIMEOUT_SECONDS = 60.0
STREAM_TIMEOUT_SECONDS = 120.0
_last_remaining_uses: int | None = None
_last_total_limit: int | None = None


def _api_url(path: str) -> str:
    base_url = VERCEL_API_URL.rstrip("/")
    return f"{base_url}{path}"


def _auth_headers() -> dict[str, str]:
    headers = supabase_auth.auth_headers()
    if not headers:
        raise AuthError("Please sign in to use Clicky.")
    return headers


def _friendly_error(response_json: dict[str, Any], fallback: str) -> str:
    error = response_json.get("error") or response_json.get("message")
    if isinstance(error, str) and error.strip():
        return error.strip()
    return fallback


def _set_usage_from_values(remaining_uses: Any, total_limit: Any) -> None:
    global _last_remaining_uses, _last_total_limit
    try:
        _last_remaining_uses = int(remaining_uses)
        _last_total_limit = int(total_limit)
    except (TypeError, ValueError):
        return


def _set_usage_from_headers(headers: httpx.Headers) -> None:
    remaining_uses = headers.get("x-remaining-uses")
    total_limit = headers.get("x-total-limit") or headers.get("x-usage-limit")
    _set_usage_from_values(remaining_uses, total_limit)


def get_last_usage() -> tuple[int, int] | None:
    if _last_remaining_uses is None or _last_total_limit is None:
        return None
    return _last_remaining_uses, _last_total_limit


async def _read_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {}


async def send_chat_request(
    transcript: str,
    screenshot_base64: str | list[str],
    session_id: str,
) -> AsyncIterator[str]:
    headers = {
        **_auth_headers(),
        "Content-Type": "application/json",
    }
    payload = {
        "transcript": transcript,
        "screenshot_base64": screenshot_base64,
        "session_id": session_id,
    }

    timeout = httpx.Timeout(STREAM_TIMEOUT_SECONDS, connect=REQUEST_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                _api_url("/api/chat"),
                headers=headers,
                json=payload,
            ) as response:
                _set_usage_from_headers(response.headers)
                if response.status_code == 401:
                    raise AuthError("Please sign in again.")

                content_type = response.headers.get("content-type", "")
                if response.status_code == 402 or "application/json" in content_type:
                    response_text = await response.aread()
                    try:
                        response_json = json.loads(response_text.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        response_json = {}

                    if response_json.get("error") == "paywall":
                        _set_usage_from_values(
                            response_json.get("uses", 10),
                            response_json.get("limit", 10),
                        )
                        raise PaywallError("You've used your 10 free sessions.")
                    if response.status_code >= 400:
                        raise NetworkError(
                            _friendly_error(
                                response_json,
                                "Clicky could not complete this request.",
                            )
                        )

                    text = response_json.get("text") or response_json.get("response")
                    _set_usage_from_values(
                        response_json.get("remaining_uses"),
                        response_json.get("limit") or response_json.get("total_limit"),
                    )
                    if isinstance(text, str):
                        yield text
                    return

                if response.status_code >= 400:
                    raise NetworkError("Clicky could not complete this request.")

                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
    except (PaywallError, AuthError, NetworkError):
        raise
    except httpx.TimeoutException as error:
        raise NetworkError("Clicky took too long to respond. Try again.") from error
    except httpx.HTTPError as error:
        raise NetworkError(
            "Could not connect to Clicky. Check your internet connection."
        ) from error


async def get_tts_audio(text: str) -> bytes:
    headers = {
        **_auth_headers(),
        "Content-Type": "application/json",
    }
    payload = {"text": text}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _api_url("/api/tts"),
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException as error:
        raise NetworkError("Clicky took too long to create audio.") from error
    except httpx.HTTPError as error:
        raise NetworkError(
            "Could not connect to Clicky TTS. Check your internet connection."
        ) from error

    if response.status_code == 401:
        raise AuthError("Please sign in again.")
    if response.status_code >= 400:
        response_json = await _read_json_response(response)
        raise NetworkError(
            _friendly_error(response_json, "Clicky could not create audio.")
        )

    return response.content


async def get_status() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                _api_url("/api/status"),
                headers=_auth_headers(),
            )
    except httpx.TimeoutException as error:
        raise NetworkError("Clicky took too long to check your account.") from error
    except httpx.HTTPError as error:
        raise NetworkError(
            "Could not connect to Clicky. Check your internet connection."
        ) from error

    if response.status_code == 401:
        raise AuthError("Please sign in again.")
    if response.status_code >= 400:
        response_json = await _read_json_response(response)
        raise NetworkError(
            _friendly_error(response_json, "Clicky could not check your account.")
        )

    return await _read_json_response(response)


async def create_checkout_url() -> str:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _api_url("/api/checkout"),
                headers=_auth_headers(),
            )
    except httpx.TimeoutException as error:
        raise NetworkError("Clicky took too long to start checkout.") from error
    except httpx.HTTPError as error:
        raise NetworkError(
            "Could not connect to Stripe Checkout. Check your internet connection."
        ) from error

    if response.status_code == 401:
        raise AuthError("Please sign in again.")
    if response.status_code >= 400:
        response_json = await _read_json_response(response)
        raise NetworkError(
            _friendly_error(response_json, "Clicky could not start checkout.")
        )

    response_json = await _read_json_response(response)
    checkout_url = response_json.get("url")
    if isinstance(checkout_url, str) and checkout_url.strip():
        return checkout_url.strip()
    raise NetworkError("Clicky returned an invalid checkout response.")


async def get_version() -> str:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(_api_url("/api/version"))
    except httpx.TimeoutException as error:
        raise NetworkError("Clicky took too long to check for updates.") from error
    except httpx.HTTPError as error:
        raise NetworkError(
            "Could not check for updates. Check your internet connection."
        ) from error

    if response.status_code >= 400:
        raise NetworkError("Clicky could not check for updates.")

    response_json = await _read_json_response(response)
    version = response_json.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()
    raise NetworkError("Clicky returned an invalid version response.")

