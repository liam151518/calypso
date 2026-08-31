"""Account credential validator.

After you fill in .env with API tokens, run this to verify each one works.
This is the dry-run API call Adam uses to confirm everything is wired up.

Usage:
    python -m scripts.validate_accounts
    python -m scripts.validate_accounts --only minimax,fal
    python -m scripts.validate_accounts --strict  # exit 1 on any failure
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"


@dataclass
class Check:
    name: str
    env_var: str
    ok: bool
    detail: str = ""


def load_env_file(path: Path) -> None:
    """Lightweight .env loader — does NOT override existing env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def check_http(
    name: str,
    env_var: str,
    url: str,
    *,
    headers: dict | None = None,
    method: str = "GET",
    body: dict | None = None,
    expect_json_keys: list[str] | None = None,
    timeout: float = 10.0,
) -> Check:
    """Make an HTTP request and validate the response."""
    token = os.environ.get(env_var, "")
    if not token:
        return Check(name=name, env_var=env_var, ok=False, detail="not set in env")

    hdrs = dict(headers or {})
    if "Authorization" not in hdrs and "authorization" not in {h.lower() for h in hdrs}:
        # Heuristic: Bearer token if the env var looks like one
        if "BEARER" in env_var.upper() or "TOKEN" in env_var.upper() or "KEY" in env_var.upper():
            hdrs["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    if body is not None and "Content-Type" not in hdrs:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode()
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = None
            ok = True
            if expect_json_keys:
                ok = parsed is not None and all(k in parsed for k in expect_json_keys)
            return Check(name=name, env_var=env_var, ok=ok, detail=str(resp.status))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()[:200] if exc.fp else ""
        return Check(name=name, env_var=env_var, ok=False, detail=f"HTTP {exc.code}: {body_text}")
    except urllib.error.URLError as exc:
        return Check(name=name, env_var=env_var, ok=False, detail=f"unreachable: {exc.reason}")


def check_telegram(env_var_token: str = "TELEGRAM_BOT_TOKEN") -> Check:
    """Validate Telegram bot token via getMe."""
    token = os.environ.get(env_var_token, "")
    if not token:
        return Check(name="telegram", env_var=env_var_token, ok=False, detail="not set in env")
    return check_http(
        name="telegram",
        env_var=env_var_token,
        url=f"https://api.telegram.org/bot{token}/getMe",
        expect_json_keys=["ok"],
    )


def check_minimax(env_var: str = "MINIMAX_API_TOKEN") -> Check:
    """Validate MiniMax API token. Uses the user-info endpoint."""
    return check_http(
        name="minimax",
        env_var=env_var,
        url="https://api.minimax.io/v1/user/info",
        headers={"Authorization": f"Bearer {os.environ.get(env_var, '')}"},
        expect_json_keys=["user_id"],
        timeout=15.0,
    )


def check_fal(env_var: str = "FAL_API_KEY") -> Check:
    """Validate fal.ai API key."""
    return check_http(
        name="fal",
        env_var=env_var,
        url="https://fal.run/user",
        headers={"Authorization": f"Key {os.environ.get(env_var, '')}"},
        expect_json_keys=["id"],
        timeout=15.0,
    )


def check_elevenlabs(env_var: str = "ELEVENLABS_API_KEY") -> Check:
    """Validate ElevenLabs API key."""
    return check_http(
        name="elevenlabs",
        env_var=env_var,
        url="https://api.elevenlabs.io/v1/user",
        headers={"xi-api-key": os.environ.get(env_var, "")},
        timeout=15.0,
    )


def check_cloudflare_r2(
    account_var: str = "CLOUDFLARE_ACCOUNT_ID",
    access_var: str = "CLOUDFLARE_R2_ACCESS_KEY",
) -> Check:
    """R2 access keys are harder to validate without a signed request. Just check they're set."""
    account = os.environ.get(account_var, "")
    access = os.environ.get(access_var, "")
    if not account or not access:
        return Check(
            name="cloudflare_r2",
            env_var=f"{account_var}, {access_var}",
            ok=False,
            detail="not set",
        )
    # R2 uses S3-compatible API. Skip the network call — just confirm the keys are non-empty.
    return Check(
        name="cloudflare_r2",
        env_var=f"{account_var}, {access_var}",
        ok=True,
        detail="keys present (network check skipped)",
    )


def check_x_bearer(env_var: str = "X_BEARER_TOKEN") -> Check:
    """Validate X bearer token via a simple /2/users/me call."""
    return check_http(
        name="x_bearer",
        env_var=env_var,
        url="https://api.twitter.com/2/users/me",
        headers={"Authorization": f"Bearer {os.environ.get(env_var, '')}"},
        expect_json_keys=["data"],
        timeout=15.0,
    )


CHECKS = [
    check_minimax,
    check_fal,
    check_telegram,
    check_cloudflare_r2,
    check_elevenlabs,
    check_x_bearer,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .env account credentials.")
    parser.add_argument("--only", help="Comma-separated list of check names to run")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any failure")
    args = parser.parse_args()

    load_env_file(ENV_FILE)

    selected = CHECKS
    if args.only:
        wanted = set(args.only.split(","))
        # Match either by exact name ("check_minimax") or by suffix starting with the name
        def _matches(name: str) -> bool:
            for w in wanted:
                if name == f"check_{w}" or name.startswith(f"check_{w}_") or name.startswith(f"check_{w}"):
                    return True
            return False
        selected = [c for c in CHECKS if _matches(c.__name__)]

    print("Validating account credentials...\n")
    results: list[Check] = []
    for check_fn in selected:
        result = check_fn()
        results.append(result)
        status = "OK  " if result.ok else "FAIL"
        print(f"  [{status}] {result.name:20s} ({result.env_var})")
        if result.detail:
            print(f"         {result.detail}")

    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")

    if failed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
