"""Quick auth connectivity check — run: python scripts/test_auth.py"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from config import SUPABASE_ANON_KEY, SUPABASE_URL, VERCEL_API_URL


async def main() -> None:
    base_url = VERCEL_API_URL.rstrip("/")
    print(f"VERCEL_API_URL: {base_url}")

    async with httpx.AsyncClient(timeout=20.0) as client:
        version_response = await client.get(f"{base_url}/api/version")
        print(f"GET /api/version -> {version_response.status_code}")
        if version_response.status_code == 200:
            print(f"  body: {version_response.text[:120]}")
        else:
            print(f"  body: {version_response.text[:200]}")

        signin_response = await client.post(
            f"{base_url}/api/auth/signin",
            json={"email": "test@example.com", "password": "wrong-password"},
        )
        print(f"POST /api/auth/signin -> {signin_response.status_code}")

    if SUPABASE_URL.strip() and SUPABASE_ANON_KEY.strip():
        print(f"SUPABASE_URL: {SUPABASE_URL.strip()}")
        print("Direct Supabase fallback: configured")
    else:
        print("Direct Supabase fallback: not configured (add SUPABASE_URL + SUPABASE_ANON_KEY to .env)")


if __name__ == "__main__":
    asyncio.run(main())
