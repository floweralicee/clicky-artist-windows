from __future__ import annotations

from collections.abc import Callable

from client import vercel_client
from config import APP_VERSION


def _version_parts(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_newer_version(latest_version: str, current_version: str) -> bool:
    latest = _version_parts(latest_version)
    current = _version_parts(current_version)
    max_len = max(len(latest), len(current))
    latest += (0,) * (max_len - len(latest))
    current += (0,) * (max_len - len(current))
    return latest > current


async def check_for_updates(
    notify: Callable[[str, str], None] | None = None,
) -> bool:
    latest_version = await vercel_client.get_version()
    if not _is_newer_version(latest_version, APP_VERSION):
        return False

    # PyUpdater can be wired here once update artifacts are published. For now,
    # the app surfaces the ready state without blocking startup.
    if notify:
        notify(
            "Clicky update ready",
            "Restart Clicky to apply the latest version.",
        )
    return True

